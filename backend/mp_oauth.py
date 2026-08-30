"""
MercadoPago OAuth2 token manager with automatic refresh.
Stores and rotates access_token + refresh_token pairs.
"""
import os
import time
import httpx
from datetime import datetime, timedelta
from database import database


# ─── Constants ───────────────────────────────────────────────────────────────

MP_OAUTH_URL = "https://api.mercadopago.com/oauth/token"
# Refresh 30 min before expiry (access_token dura 6h, refresh_token dura 6 meses)
TOKEN_EXPIRY_BUFFER = 1800


async def get_mp_credentials() -> dict:
    """Get MP client credentials from DB (saas_settings) or env vars"""
    cid_row = await database.fetch_one("SELECT value FROM saas_settings WHERE id = 'mp_client_id'")
    csec_row = await database.fetch_one("SELECT value FROM saas_settings WHERE id = 'mp_client_secret'")
    pub_row = await database.fetch_one("SELECT value FROM saas_settings WHERE id = 'mp_public_key'")
    tok_row = await database.fetch_one("SELECT value FROM saas_settings WHERE id = 'mp_access_token'")

    client_id = (cid_row["value"] if cid_row and cid_row["value"] else "") or os.environ.get("MERCADOPAGO_CLIENT_ID", "")
    client_secret = (csec_row["value"] if csec_row and csec_row["value"] else "") or os.environ.get("MERCADOPAGO_CLIENT_SECRET", "")
    public_key = (pub_row["value"] if pub_row and pub_row["value"] else "") or os.environ.get("MERCADOPAGO_PUBLIC_KEY", "")
    access_token = (tok_row["value"] if tok_row and tok_row["value"] else "") or os.environ.get("MERCADOPAGO_ACCESS_TOKEN", "")

    return {
        "client_id": client_id,
        "client_secret": client_secret,
        "public_key": public_key,
        "access_token": access_token
    }


async def get_mp_access_token() -> str:
    """
    Get a valid MercadoPago access token.
    1. Checks saas_settings for manually configured static access token.
    2. Checks env var MERCADOPAGO_ACCESS_TOKEN.
    3. Checks mp_oauth_tokens table (OAuth flow) and auto-refreshes if needed.
    """
    creds = await get_mp_credentials()
    if creds["access_token"]:
        return creds["access_token"]

    # Try from DB (stored from OAuth flow)
    token_row = await database.fetch_one(
        "SELECT access_token, refresh_token, expires_at FROM mp_oauth_tokens ORDER BY id DESC LIMIT 1"
    )

    if not token_row:
        raise Exception("MercadoPago no configurado. Configura las credenciales en el Panel SaaS Master.")

    now = time.time()

    # Token still valid with buffer?
    if token_row["expires_at"] and token_row["expires_at"] > now + TOKEN_EXPIRY_BUFFER:
        return token_row["access_token"]

    # Token expired or about to expire — refresh
    if token_row["refresh_token"]:
        try:
            new_tokens = await _refresh_token(token_row["refresh_token"])
            await _store_tokens(new_tokens)
            return new_tokens["access_token"]
        except Exception as e:
            print(f"[MP Token] Refresh failed: {e}, falling back to expired token")
            return token_row["access_token"]  # Will likely fail, but best effort

    # No refresh token available
    raise Exception("MercadoPago token expired and no refresh token available")


async def _refresh_token(refresh_token: str) -> dict:
    """
    Exchange refresh_token for new access_token + refresh_token.
    Returns: { access_token, refresh_token, expires_at }
    """
    creds = await get_mp_credentials()
    client_id = creds["client_id"]
    client_secret = creds["client_secret"]

    if not client_id or not client_secret:
        raise Exception("MERCADOPAGO_CLIENT_ID y MERCADOPAGO_CLIENT_SECRET requeridos para refresh")

    async with httpx.AsyncClient() as client:
        response = await client.post(
            MP_OAUTH_URL,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            data={
                "client_id": client_id,
                "client_secret": client_secret,
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
            }
        )

    if response.status_code != 200:
        raise Exception(f"MP OAuth error {response.status_code}: {response.text}")

    data = response.json()
    expires_in = data.get("expires_in", 15552000)  # Default 180 days

    return {
        "access_token": data["access_token"],
        "refresh_token": data["refresh_token"],
        "expires_at": time.time() + expires_in,
    }


async def _store_tokens(tokens: dict) -> None:
    """Store new token pair in DB"""
    await database.execute(
        """
        INSERT INTO mp_oauth_tokens (access_token, refresh_token, expires_at)
        VALUES (:at, :rt, :exp)
        """,
        {
            "at": tokens["access_token"],
            "rt": tokens["refresh_token"],
            "exp": tokens["expires_at"],
        }
    )


async def complete_oauth_flow(authorization_code: str) -> dict:
    """
    Complete the initial OAuth flow (first-time setup).
    Call this after user authorizes your app on MercadoPago.
    """
    client_id = os.environ.get("MERCADOPAGO_CLIENT_ID", "")
    client_secret = os.environ.get("MERCADOPAGO_CLIENT_SECRET", "")
    redirect_uri = os.environ.get("MERCADOPAGO_REDIRECT_URI", "")

    async with httpx.AsyncClient() as client:
        response = await client.post(
            MP_OAUTH_URL,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            data={
                "client_id": client_id,
                "client_secret": client_secret,
                "code": authorization_code,
                "redirect_uri": redirect_uri,
                "grant_type": "authorization_code",
            }
        )

    if response.status_code != 200:
        raise Exception(f"MP OAuth error {response.status_code}: {response.text}")

    data = response.json()
    expires_in = data.get("expires_in", 15552000)

    tokens = {
        "access_token": data["access_token"],
        "refresh_token": data["refresh_token"],
        "expires_at": time.time() + expires_in,
    }

    await _store_tokens(tokens)
    return tokens


async def scheduled_token_refresh():
    """
    Called from APScheduler every 5 hours.
    Proactively refreshes before the 6-hour access_token expiry.
    """
    print("[MP Token] Verificando refresh del token...")

    env_token = os.environ.get("MERCADOPAGO_ACCESS_TOKEN", "")
    if env_token:
        print("[MP Token] Token estático detectado en .env — no requiere refresh")
        return

    token_row = await database.fetch_one(
        "SELECT access_token, refresh_token, expires_at FROM mp_oauth_tokens ORDER BY id DESC LIMIT 1"
    )

    if not token_row:
        print("[MP Token] No hay tokens guardados en DB")
        return

    now = time.time()

    # Token válido por más de 1 hora? Skip
    if token_row["expires_at"] and token_row["expires_at"] > now + TOKEN_EXPIRY_BUFFER:
        remaining = int((token_row["expires_at"] - now) / 60)
        print(f"[MP Token] Token válido por {remaining} min más — skip")
        return

    # Necesita refresh
    if token_row["refresh_token"]:
        try:
            new_tokens = await _refresh_token(token_row["refresh_token"])
            await _store_tokens(new_tokens)
            remaining = int((new_tokens["expires_at"] - time.time()) / 60)
            print(f"[MP Token] Token refrescado exitosamente. Válido por {remaining} min.")
        except Exception as e:
            print(f"[MP Token] ERROR refrescando: {e}")
    else:
        print("[MP Token] No hay refresh_token disponible")
