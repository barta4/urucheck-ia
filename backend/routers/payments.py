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
from payment_service import (
    verify_mp_signature,
    create_mp_checkout_preference,
    process_mp_payment_notification,
    process_mp_preapproval_notification,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/payments", tags=["payments"])

# Keep aliases for backward compatibility if imported elsewhere
_process_payment_notification = process_mp_payment_notification
_process_preapproval_notification = process_mp_preapproval_notification


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
    if not company:
        raise HTTPException(status_code=404, detail="Empresa no encontrada")

    try:
        return await create_mp_checkout_preference(
            company_id=company_id,
            company_name=company["name"],
            company_email=company["admin_email"],
            amount=amount,
            description=description,
        )
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error creando preferencia MP: {str(e)}")


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
