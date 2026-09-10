"""
Payments and MercadoPago integration.
"""
import os
import httpx
import json
import hmac
import hashlib
import time
import logging
from datetime import datetime
from fastapi import APIRouter, HTTPException, Depends, Request
from typing import Optional
from auth import get_current_admin
from database import database
from config import settings
from mp_oauth import get_mp_access_token

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/payments", tags=["payments"])


@router.post("/create-preference")
async def create_payment_preference(
    amount: float,
    description: str = "Suscripción mensual - Sistema de Asistencia",
    current_user=Depends(get_current_admin)
):
    """Create MercadoPago payment preference for checkout"""
    company_id = current_user["company_id"]
    company = await database.fetch_one(
        "SELECT name, admin_email FROM companies WHERE id = :cid", {"cid": company_id}
    )

    try:
        mp_token = await get_mp_access_token()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    preference_data = {
        "items": [{
            "title": description,
            "quantity": 1,
            "unit_price": amount,
            "currency_id": "USD",
        }],
        "payer": {
            "name": company["name"],
            "email": company["admin_email"],
        },
        "back_urls": {
            "success": f"{settings.FRONTEND_URL}/subscription/success",
            "failure": f"{settings.FRONTEND_URL}/subscription/failure",
            "pending": f"{settings.FRONTEND_URL}/subscription/pending",
        },
        "auto_return": "approved",
        "notification_url": f"{settings.FRONTEND_URL.replace('http://', 'https://').rstrip('/')}/api/payments/webhook",
    }

    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://api.mercadopago.com/checkout/preferences",
            headers={
                "Authorization": f"Bearer {mp_token}",
                "Content-Type": "application/json",
            },
            json=preference_data,
        )

    if response.status_code not in (200, 201):
        raise HTTPException(status_code=500, detail=f"Error creando preferencia MP: {response.text}")

    result = response.json()
    return {
        "preference_id": result["id"],
        "init_point": result["init_point"],
        "sandbox_init_point": result.get("sandbox_init_point"),
    }


def verify_mp_signature(
    x_signature: Optional[str],
    x_request_id: Optional[str],
    data_id: Optional[str],
    secret: str,
    max_age_seconds: int = 600,
) -> bool:
    """
    Verify MercadoPago webhook HMAC signature.
    x_signature format: 'ts=1701234567,v1=hash...'
    """
    if not x_signature or not x_request_id or not secret:
        return False

    parts = {}
    for part in x_signature.split(","):
        if "=" in part:
            k, v = part.strip().split("=", 1)
            parts[k] = v

    ts = parts.get("ts")
    v1 = parts.get("v1")
    if not ts or not v1:
        return False

    # Check replay window (allow +/- max_age_seconds)
    try:
        ts_int = int(ts)
        current_ts = int(time.time())
        if abs(current_ts - ts_int) > max_age_seconds:
            logger.warning(f"[MP Webhook] Replay or expired timestamp: ts={ts_int}, now={current_ts}")
            return False
    except ValueError:
        return False

    # Template format defined by MercadoPago: "id:[data.id];request-id:[x-request-id];ts:[ts];"
    data_id_str = str(data_id or "")
    manifest = f"id:{data_id_str};request-id:{x_request_id};ts:{ts};"
    expected_hash = hmac.new(
        secret.encode("utf-8"),
        manifest.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()

    return hmac.compare_digest(expected_hash, v1)


@router.post("/webhook")
async def mp_webhook(request: Request):
    """
    MercadoPago webhook endpoint.
    Receives payment notifications and processes them with HMAC signature verification.
    """
    # 1. Retrieve webhook secret from settings or DB
    mp_secret = settings.MERCADOPAGO_WEBHOOK_SECRET
    if not mp_secret:
        row = await database.fetch_one(
            "SELECT value FROM saas_settings WHERE id = 'mp_webhook_secret'"
        )
        if row and row["value"]:
            mp_secret = row["value"]

    x_signature = request.headers.get("x-signature")
    x_request_id = request.headers.get("x-request-id")

    try:
        data = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Cuerpo de petición JSON inválido")

    # data.id can arrive in query parameters or json payload
    data_id = (
        request.query_params.get("data.id")
        or (data.get("data", {}) or {}).get("id")
        or data.get("id")
    )

    if mp_secret:
        if not x_signature or not x_request_id:
            logger.warning("[MP Webhook] Rechazado: faltan cabeceras x-signature o x-request-id")
            raise HTTPException(status_code=403, detail="Firma de webhook requerida")

        if not verify_mp_signature(x_signature, x_request_id, data_id, mp_secret):
            logger.warning("[MP Webhook] Rechazado: firma HMAC inválida")
            raise HTTPException(status_code=403, detail="Firma de webhook inválida")
    else:
        if not settings.DEBUG:
            logger.error("[MP Webhook] CRÍTICO: MERCADOPAGO_WEBHOOK_SECRET no configurado en producción")
            raise HTTPException(status_code=500, detail="Webhook no configurado de forma segura")
        else:
            logger.warning("[MP Webhook] ADVERTENCIA: Procesando webhook sin firma en modo DEBUG")

    topic = data.get("topic") or data.get("type")
    resource = data_id

    try:
        if topic == "payment":
            await _process_payment_notification(str(resource))
        elif topic == "merchant_order":
            pass  # Handle if needed
        elif topic == "preapproval":
            await _process_preapproval_notification(str(resource))

        return {"status": "ok"}
    except Exception as e:
        logger.error(f"[MP Webhook] Error: {e}")
        return {"status": "error", "message": str(e)}


async def _process_payment_notification(mp_payment_id: str):
    """Process a MercadoPago payment notification"""
    try:
        mp_token = await get_mp_access_token()
    except Exception as e:
        print(f"[MP Webhook] Error obteniendo token MP: {e}")
        return

    # Fetch payment details from MP
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"https://api.mercadopago.com/v1/payments/{mp_payment_id}",
            headers={"Authorization": f"Bearer {mp_token}"},
        )

    if response.status_code != 200:
        print(f"[MP Webhook] Error fetching payment {mp_payment_id}")
        return

    payment_data = response.json()
    status = payment_data.get("status")  # approved, pending, rejected
    amount = payment_data.get("transaction_amount")
    payer_email = payment_data.get("payer", {}).get("email")
    metadata = payment_data.get("metadata", {})
    company_id = metadata.get("company_id")

    # Validate company_id BEFORE any DB writes to avoid orphan records
    if not company_id:
        print(f"[MP Webhook] No company_id in payment {mp_payment_id} — skipping")
        return

    # Record payment
    payment_id = await database.execute(
        """
        INSERT INTO payments (company_id, amount, currency, method, mercado_pago_id, mercado_pago_status, raw_response)
        VALUES (:cid, :amount, 'USD', :method, :mp_id, :mp_status, :raw)
        RETURNING id
        """,
        {
            "cid": company_id,
            "amount": amount,
            "method": "card",
            "mp_id": mp_payment_id,
            "mp_status": status,
            "raw": json.dumps(payment_data),
        }
    )

    if status == "approved":
        # Update subscription
        await database.execute(
            """
            UPDATE subscriptions SET
                status = 'active',
                current_period_start = NOW(),
                current_period_end = NOW() + INTERVAL '30 days',
                updated_at = NOW()
            WHERE company_id = :cid
            """,
            {"cid": company_id}
        )

        # Update company
        await database.execute(
            """
            UPDATE companies SET
                status = 'active',
                last_payment_at = NOW(),
                updated_at = NOW()
            WHERE id = :cid
            """,
            {"cid": company_id}
        )

        # Find and update invoice
        await database.execute(
            """
            UPDATE invoices SET
                status = 'paid',
                paid_at = NOW(),
                mercado_pago_payment_id = :mp_id
            WHERE company_id = :cid AND status = 'pending'
            """,
            {"mp_id": mp_payment_id, "cid": company_id}
        )

        # Audit log
        await database.execute(
            """
            INSERT INTO audit_logs (company_id, action, resource, details)
            VALUES (:cid, 'payment_received', 'payment', :details)
            """,
            {"cid": company_id, "details": json.dumps({"amount": amount, "mp_id": mp_payment_id})}
        )

    elif status in ("rejected", "refunded"):
        await database.execute(
            """
            UPDATE companies SET status = 'grace'
            WHERE id = :cid
            """,
            {"cid": company_id}
        )


async def _process_preapproval_notification(mp_preapproval_id: str):
    """Process MercadoPago preapproval (recurring subscription) notification"""
    try:
        mp_token = await get_mp_access_token()
    except Exception as e:
        print(f"[MP Webhook] Error obteniendo token MP: {e}")
        return

    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"https://api.mercadopago.com/preapproval/{mp_preapproval_id}",
            headers={"Authorization": f"Bearer {mp_token}"},
        )

    if response.status_code != 200:
        return

    preapproval = response.json()
    status = preapproval.get("status")  # authorized, paused, cancelled

    # Find company by mercado_pago_id
    sub = await database.fetch_one(
        "SELECT company_id FROM subscriptions WHERE mercado_pago_id = :mp_id",
        {"mp_id": mp_preapproval_id}
    )

    if not sub:
        return

    company_id = sub["company_id"]

    if status == "cancelled":
        await database.execute(
            """
            UPDATE subscriptions SET status = 'cancelled', updated_at = NOW()
            WHERE company_id = :cid
            """,
            {"cid": company_id}
        )
        await database.execute(
            "UPDATE companies SET status = 'suspended' WHERE id = :cid",
            {"cid": company_id}
        )


@router.get("/my")
async def get_my_payments(current_user=Depends(get_current_admin)):
    """Get payment history for current company"""
    company_id = current_user["company_id"]

    rows = await database.fetch_all(
        """
        SELECT p.*, i.invoice_number
        FROM payments p
        LEFT JOIN invoices i ON p.invoice_id = i.id
        WHERE p.company_id = :cid
        ORDER BY p.created_at DESC
        LIMIT 50
        """,
        {"cid": company_id}
    )
    return [dict(r) for r in rows]
