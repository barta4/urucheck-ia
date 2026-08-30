"""
Payments and MercadoPago integration.
"""
import os
import httpx
import json
from datetime import datetime
from fastapi import APIRouter, HTTPException, Depends, Request
from typing import Optional
from auth import get_current_admin
from database import database
from config import settings
from mp_oauth import get_mp_access_token

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


@router.post("/webhook")
async def mp_webhook(request: Request):
    """
    MercadoPago webhook endpoint.
    Receives payment notifications and processes them.
    """
    try:
        data = await request.json()
        topic = data.get("topic")
        resource = data.get("data", {}).get("id")

        if topic == "payment":
            await _process_payment_notification(resource)
        elif topic == "merchant_order":
            pass  # Handle if needed
        elif topic == "preapproval":
            await _process_preapproval_notification(resource)

        return {"status": "ok"}
    except Exception as e:
        print(f"[MP Webhook] Error: {e}")
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
