import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, Request, Response, status
from fastapi.security import OAuth2PasswordBearer
from config import settings
from database import database

logger = logging.getLogger(__name__)

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Name of the httpOnly cookie that carries the JWT for browser clients.
AUTH_COOKIE_NAME = "urucheck_token"


class OAuth2PasswordBearerWithCookie(OAuth2PasswordBearer):
    """
    Auth scheme that reads the token from the Authorization header first
    (mobile app / API clients) and falls back to the httpOnly auth cookie
    (admin web panel). Keeps the Bearer flow fully functional.
    """

    def __init__(self, tokenUrl: str, cookie_name: str = AUTH_COOKIE_NAME):
        super().__init__(tokenUrl=tokenUrl, auto_error=False)
        self.cookie_name = cookie_name

    async def __call__(self, request: Request) -> Optional[str]:
        header_token = await super().__call__(request)
        if header_token:
            return header_token
        return request.cookies.get(self.cookie_name)


oauth2_scheme = OAuth2PasswordBearerWithCookie(tokenUrl="/api/auth/login")


def set_auth_cookie(response: Response, token: str) -> None:
    """Attach the JWT as an httpOnly cookie (browser sessions).

    httpOnly makes the token unreachable from JavaScript (XSS cannot steal
    the session). SameSite=Lax blocks cross-site requests carrying the
    cookie, which mitigates CSRF for state-changing endpoints.
    """
    response.set_cookie(
        key=AUTH_COOKIE_NAME,
        value=token,
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        httponly=True,
        secure=not settings.DEBUG,
        samesite="lax",
        path="/",
    )


def clear_auth_cookie(response: Response) -> None:
    """Remove the auth cookie (logout)."""
    response.delete_cookie(key=AUTH_COOKIE_NAME, path="/", httponly=True, samesite="lax")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES))
    if "jti" not in to_encode:
        to_encode["jti"] = uuid.uuid4().hex
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


async def revoke_token(token: str) -> bool:
    """Add token's jti to revoked_tokens table to prevent reuse"""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        jti = payload.get("jti")
        exp_ts = payload.get("exp")
        if not jti:
            return False
        expires_at = datetime.fromtimestamp(exp_ts, tz=timezone.utc) if exp_ts else datetime.now(timezone.utc) + timedelta(days=1)
        await database.execute(
            """
            INSERT INTO revoked_tokens (jti, expires_at)
            VALUES (:jti, :exp)
            ON CONFLICT (jti) DO NOTHING
            """,
            {"jti": jti, "exp": expires_at}
        )
        return True
    except Exception as e:
        # A failed revocation means the token REMAINS valid — must be visible
        # in logs, never silent.
        logger.error("[auth] Fallo al revocar token (el token seguirá siendo válido): %s", e)
        return False


async def get_current_user(token: Optional[str] = Depends(oauth2_scheme)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="No autorizado",
        headers={"WWW-Authenticate": "Bearer"},
    )
    # Token may now come from the Authorization header OR the httpOnly cookie
    if not token:
        raise credentials_exception
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise credentials_exception
        jti: Optional[str] = payload.get("jti")
        if jti:
            revoked = await database.fetch_one(
                "SELECT jti FROM revoked_tokens WHERE jti = :jti",
                {"jti": jti}
            )
            if revoked:
                raise credentials_exception
    except JWTError:
        raise credentials_exception

    # ─── Tenant binding from the DATABASE (never from JWT claims):
    #  - INNER JOIN drops legacy employees with NULL company_id
    #  - c.active = true drops soft-deleted companies
    #  - the company's live status is returned so callers can act on it
    user = await database.fetch_one(
        """SELECT e.id, e.company_id, e.name, e.email, e.role, e.active,
                  e.is_super_admin, e.expo_push_token, e.device_id,
                  c.status AS company_status
           FROM employees e
           JOIN companies c ON e.company_id = c.id
           WHERE e.id = :id AND e.active = true AND c.active = true""",
        {"id": user_id}
    )
    if user is None:
        raise credentials_exception

    # ─── Defense-in-depth: suspending/cancelling a company must cut API
    # access IMMEDIATELY, not when the (up to 24h) JWT expires. Without
    # this, a suspended company kept full service for the token's lifetime.
    # Platform super-admins keep access to manage the SaaS panel.
    if not user["is_super_admin"] and user.get("company_status") in ("suspended", "cancelled"):
        if user["company_status"] == "suspended":
            raise HTTPException(
                status_code=403,
                detail="Cuenta suspendida. Contacta a soporte para reactivar."
            )
        raise HTTPException(
            status_code=403,
            detail="Cuenta cancelada. Tus datos están disponibles por 30 días."
        )

    return dict(user)

def get_company_id(user: dict) -> str:
    """Extract company_id from user dict (must be attached to JWT or queried)"""
    return user.get("company_id")

async def get_current_admin(current_user=Depends(get_current_user)):
    if current_user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Se requiere rol administrador")
    return current_user

async def get_current_super_admin(current_user=Depends(get_current_user)):
    if not current_user.get("is_super_admin", False):
        raise HTTPException(status_code=403, detail="Se requiere rol super-administrador de la plataforma")
    return current_user
