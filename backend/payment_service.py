"""
Unified Payment and Subscription Service.
Centralizes MercadoPago preference creation, webhook verification, payment notifications,
and subscription ledger updates.
"""
import os
import httpx
import json
import hmac
import hashlib
import time
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any

from database import database
from config import settings
from mp_oauth import get_mp_access_token

logger = logging.getLogger(__name__)


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
    Template: 'id:[data.id];request-id:[x-request-id];ts:[ts];'
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

    # Check replay window
    try:
        ts_int = int(ts)
        current_ts = int(time.time())
        if abs(current_ts - ts_int) > max_age_seconds:
            logger.warning(f"[MP Webhook] Replay or expired timestamp: ts={ts_int}, now={current_ts}")
            return False
    except ValueError:
        return False

    data_id_str = str(data_id or "")
    manifest = f"id:{data_id_str};request-id:{x_request_id};ts:{ts};"
    expected_hash = hmac.new(
        secret.encode("utf-8"),
        manifest.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()

    return hmac.compare_digest(expected_hash, v1)


async def create_mp_checkout_preference(
    company_id: str,
    company_name: str,
    company_email: str,
    amount: float,
    description: str = "Suscripción mensual - Sistema de Asistencia",
    currency: str = "USD",
    back_urls: Optional[Dict[str, str]] = None,
    notification_url: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Create a MercadoPago checkout preference for a company.
    """
    mp_token = await get_mp_access_token()

    if not back_urls:
        frontend_base = settings.FRONTEND_URL.rstrip('/')
        back_urls = {
            "success": f"{frontend_base}/subscription/success",
            "failure": f"{frontend_base}/subscription/failure",
            "pending": f"{frontend_base}/subscription/pending",
        }

    if not notification_url:
        webhook_base = settings.FRONTEND_URL.replace('http://', 'https://').rstrip('/')
        notification_url = f"{webhook_base}/api/payments/webhook"

    preference_data = {
        "items": [{
            "title": description,
            "quantity": 1,
            "unit_price": float(amount),
            "currency_id": currency,
        }],
        "payer": {
            "name": company_name,
            "email": company_email,
        },
        "external_reference": str(company_id),
        "metadata": {
            "company_id": str(company_id)
        },
        "back_urls": back_urls,
        "auto_return": "approved",
        "notification_url": notification_url,
    }

    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://api.mercadopago.com/checkout/preferences",
            headers={
                "Authorization": f"Bearer {mp_token}",
                "Content-Type": "application/json",
            },
            json=preference_data,
            timeout=15.0,
        )

    if response.status_code not in (200, 201):
        logger.error(f"[MP Preference] Error creando preferencia: {response.text}")
        raise RuntimeError(f"Error en MercadoPago ({response.status_code}): {response.text}")

    result = response.json()
    return {
        "preference_id": result["id"],
        "init_point": result["init_point"],
        "sandbox_init_point": result.get("sandbox_init_point"),
    }


async def process_mp_payment_notification(mp_payment_id: str) -> bool:
    """
    Fetch payment details from MercadoPago API and update subscriptions / companies / invoices.
    """
    try:
        mp_token = await get_mp_access_token()
    except Exception as e:
        logger.error(f"[MP Webhook] Error obteniendo token MP: {e}")
        return False

    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"https://api.mercadopago.com/v1/payments/{mp_payment_id}",
            headers={"Authorization": f"Bearer {mp_token}"},
            timeout=15.0,
        )

    if response.status_code != 200:
        logger.error(f"[MP Webhook] Error obteniendo pago {mp_payment_id}: {response.text}")
        return False

    payment_data = response.json()
    status = payment_data.get("status")  # approved, pending, rejected
    amount = payment_data.get("transaction_amount")
    metadata = payment_data.get("metadata", {})
    company_id = metadata.get("company_id")

    if not company_id:
        logger.warning(f"[MP Webhook] Pago {mp_payment_id} sin company_id en metadata — omitido")
        return False

    # Insert payment record
    await database.execute(
        """
        INSERT INTO payments (company_id, amount, currency, method, mercado_pago_id, mercado_pago_status, raw_response)
        VALUES (:cid, :amount, 'USD', :method, :mp_id, :mp_status, :raw)
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
        # Extend or activate subscription for 30 days
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

        # Reactivate company status
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

        # Settle pending invoices
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

    return True


async def process_mp_preapproval_notification(mp_preapproval_id: str) -> bool:
    """
    Handle MercadoPago recurring subscription (preapproval) notifications.
    """
    try:
        mp_token = await get_mp_access_token()
    except Exception as e:
        logger.error(f"[MP Webhook] Error obteniendo token MP: {e}")
        return False

    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"https://api.mercadopago.com/preapproval/{mp_preapproval_id}",
            headers={"Authorization": f"Bearer {mp_token}"},
            timeout=15.0,
        )

    if response.status_code != 200:
        return False

    preapproval = response.json()
    status = preapproval.get("status")

    sub = await database.fetch_one(
        "SELECT company_id FROM subscriptions WHERE mercado_pago_id = :mp_id",
        {"mp_id": mp_preapproval_id}
    )

    if not sub:
        return False

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

    return True


async def apply_subscription_manual_payment(
    company_id: str,
    amount: float,
    currency: str,
    method: str,
    days_to_add: int,
    notes: Optional[str] = None,
    user_id: Optional[str] = None,
    invoice_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Applies a manual payment (cash, bank transfer) to a company's subscription.
    Updates payments, invoices, subscriptions, companies, and audit_logs.
    """
    company = await database.fetch_one(
        "SELECT id, name FROM companies WHERE id = :cid",
        {"cid": company_id}
    )
    if not company:
        raise ValueError("Empresa no encontrada")

    # Generate invoice if none provided
    inv_num = None
    if not invoice_id:
        count_row = await database.fetch_one("SELECT COUNT(*) as cnt FROM invoices")
        cnt = (count_row["cnt"] if count_row else 0) + 1
        inv_num = f"INV-MAN-{datetime.now(timezone.utc).strftime('%Y%m')}-{cnt:04d}"

        invoice_id = await database.execute(
            """
            INSERT INTO invoices (company_id, invoice_number, amount, currency, status, paid_at, notes)
            VALUES (:cid, :num, :amount, :currency, 'paid', NOW(), :notes)
            RETURNING id
            """,
            {
                "cid": company_id,
                "num": inv_num,
                "amount": amount,
                "currency": currency,
                "notes": f"Pago manual registrado ({method}): {notes or ''}".strip(),
            }
        )

    # Insert payment record
    payment_id = await database.execute(
        """
        INSERT INTO payments (company_id, invoice_id, amount, currency, method, mercado_pago_status, notes)
        VALUES (:cid, :inv_id, :amount, :currency, :method, 'approved', :notes)
        RETURNING id
        """,
        {
            "cid": company_id,
            "inv_id": invoice_id,
            "amount": amount,
            "currency": currency,
            "method": method,
            "notes": notes,
        }
    )

    # Compute new period end
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    sub = await database.fetch_one(
        "SELECT id, current_period_end FROM subscriptions WHERE company_id = :cid",
        {"cid": company_id}
    )

    if sub:
        curr_end = sub["current_period_end"]
        if curr_end and curr_end.replace(tzinfo=None) > now:
            new_end = curr_end.replace(tzinfo=None) + timedelta(days=days_to_add)
        else:
            new_end = now + timedelta(days=days_to_add)

        await database.execute(
            """
            UPDATE subscriptions SET
                status = 'active',
                current_period_start = NOW(),
                current_period_end = :nend,
                updated_at = NOW()
            WHERE company_id = :cid
            """,
            {"cid": company_id, "nend": new_end}
        )
    else:
        new_end = now + timedelta(days=days_to_add)
        await database.execute(
            """
            INSERT INTO subscriptions (company_id, status, current_period_start, current_period_end)
            VALUES (:cid, 'active', NOW(), :nend)
            """,
            {"cid": company_id, "nend": new_end}
        )

    # Update company status to active
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

    # Audit log
    if user_id:
        await database.execute(
            """
            INSERT INTO audit_logs (company_id, user_id, action, resource, resource_id, details)
            VALUES (:cid, :uid, 'manual_payment_recorded', 'payment', :pid, :details)
            """,
            {
                "cid": company_id,
                "uid": user_id,
                "pid": payment_id,
                "details": json.dumps({
                    "amount": amount,
                    "currency": currency,
                    "method": method,
                    "days_added": days_to_add,
                    "notes": notes,
                })
            }
        )

    return {
        "message": f"Pago de ${amount} {currency} registrado con éxito para {company['name']}.",
        "payment_id": str(payment_id),
        "invoice_number": inv_num,
        "new_period_end": new_end.isoformat() if hasattr(new_end, 'isoformat') else str(new_end)
    }
