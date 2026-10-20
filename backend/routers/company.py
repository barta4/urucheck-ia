import logging
import os
import uuid
import httpx
from datetime import datetime
from zoneinfo import ZoneInfo
from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException, Header
from fastapi.responses import FileResponse
from typing import Optional
from auth import get_current_admin, get_current_user
from database import database
from config import settings
from crypto import encrypt_secret, decrypt_secret, mask_secret
from db_utils import build_dynamic_update_query
from url_guard import validate_outbound_url, UnsafeOutboundURL

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/company", tags=["company"])

# Maximum logo upload size (bytes)
MAX_LOGO_BYTES = 5 * 1024 * 1024

# Whitelist of fields permitted to be updated via update_config (H11)
_ALLOWED_CONFIG_UPDATE_FIELDS = frozenset({
    "company_name", "timezone", "tolerance_minutes", "auto_checkout_hours",
    "require_gps", "require_face", "face_verification_enabled",
    "face_verification_provider", "primary_color", "accent_color",
    "webhook_url", "bonus_success_message", "bonus_pending_message",
    "webhook_notify_checkin", "webhook_notify_checkout",
    "webhook_notify_break", "webhook_notify_late",
    "webhook_notify_absence", "smtp_host",
    "smtp_port", "smtp_username", "smtp_password", "smtp_from_email",
    "smtp_to_email", "email_notify_monthly_report", "live_tracking_enabled",
    "live_tracking_interval_minutes", "logo_path"
})


@router.get("/config")
async def get_config(
    slug: Optional[str] = None,
    authorization: Optional[str] = Header(None)
):
    """
    Public endpoint for branding info (login page needs this).
    If Bearer token is provided, returns full config including sensitive fields.
    """
    # Try to resolve user from Authorization header
    current_user = None
    if authorization and authorization.startswith("Bearer "):
        token = authorization.replace("Bearer ", "")
        try:
            current_user = await get_current_user(token)
        except Exception:
            pass

    # Resolve company_id
    cid = current_user.get("company_id") if current_user else None
    
    row = None
    try:
        if cid:
            row = await database.fetch_one(
                "SELECT * FROM company_config WHERE company_id = :cid",
                {"cid": cid}
            )
            # If company exists but has no company_config row, create one tied to cid
            if not row:
                comp = await database.fetch_one("SELECT name FROM companies WHERE id = :cid", {"cid": cid})
                comp_name = comp["name"] if comp else "Mi Empresa"
                await database.execute(
                    "INSERT INTO company_config (company_id, company_name) VALUES (:cid, :name) ON CONFLICT (company_id) DO NOTHING",
                    {"cid": cid, "name": comp_name}
                )
                row = await database.fetch_one(
                    "SELECT * FROM company_config WHERE company_id = :cid",
                    {"cid": cid}
                )
        elif slug:
            row = await database.fetch_one(
                """
                SELECT cc.* FROM company_config cc
                JOIN companies c ON cc.company_id = c.id
                WHERE c.slug = :slug
                """,
                {"slug": slug}
            )
            if not row:
                comp = await database.fetch_one("SELECT id, name FROM companies WHERE slug = :slug", {"slug": slug})
                if comp:
                    await database.execute(
                        "INSERT INTO company_config (company_id, company_name) VALUES (:cid, :name) ON CONFLICT (company_id) DO NOTHING",
                        {"cid": str(comp["id"]), "name": comp["name"]}
                    )
                    row = await database.fetch_one(
                        "SELECT * FROM company_config WHERE company_id = :cid",
                        {"cid": str(comp["id"])}
                    )
    except Exception as e:
        logger.error("[Company Router] Fallo al recuperar company_config de la base de datos: %s", e)

    # Query global SaaS download URLs
    apk_url = ""
    ios_url = ""
    try:
        apk_row = await database.fetch_one("SELECT value FROM saas_settings WHERE id = 'apk_url'")
        ios_row = await database.fetch_one("SELECT value FROM saas_settings WHERE id = 'ios_url'")
        if apk_row:
            apk_url = apk_row["value"]
        if ios_row:
            ios_url = ios_row["value"]
    except Exception as e:
        logger.error("[Company Config Router] Fallo al recuperar saas_settings: %s", e)

    if not row:
        return {
            "company_name": "Mi Empresa",
            "logo_url": None,
            "primary_color": "#2563eb",
            "accent_color": "#1d4ed8",
            "bonus_success_message": "¡Bonus asegurado!",
            "bonus_pending_message": "Faltan {days} días para asegurar tu bono.",
            "apk_url": apk_url,
            "ios_url": ios_url,
        }

    row_dict = dict(row)
    logo_url = None
    if row_dict.get("logo_path"):
        base_url = settings.FRONTEND_URL.rstrip("/")
        # Use updated_at as cache-buster so browser can cache between unchanged versions
        cache_ts = int(row_dict.get("updated_at").timestamp()) if row_dict.get("updated_at") else 0
        logo_url = f"{base_url}/api/company/{row_dict['company_id']}/logo?v={cache_ts}"

    # Only return full config (including webhooks, SMTP, face verification) to company admins or super-admins
    is_admin = current_user and (current_user.get("role") == "admin" or current_user.get("is_super_admin", False))
    if is_admin:
        if row_dict.get("smtp_password"):
            row_dict["smtp_password"] = mask_secret(row_dict["smtp_password"])
        return dict(row_dict, logo_url=logo_url, apk_url=apk_url, ios_url=ios_url)

    # Public response — only branding fields (no webhook, SMTP, or face config)
    return {
        "company_name": row_dict.get("company_name", "Mi Empresa"),
        "logo_url": logo_url,
        "primary_color": row_dict.get("primary_color", "#2563eb"),
        "accent_color": row_dict.get("accent_color", "#1d4ed8"),
        "bonus_success_message": row_dict.get("bonus_success_message", "¡Bonus asegurado!"),
        "bonus_pending_message": row_dict.get("bonus_pending_message", "Faltan {days} días para asegurar tu bono."),
        "apk_url": apk_url,
        "ios_url": ios_url,
    }


@router.patch("/config")
async def update_config(
    company_name: Optional[str] = Form(None),
    primary_color: Optional[str] = Form(None),
    accent_color: Optional[str] = Form(None),
    webhook_url: Optional[str] = Form(None),
    bonus_success_message: Optional[str] = Form(None),
    bonus_pending_message: Optional[str] = Form(None),
    webhook_notify_checkin: Optional[str] = Form(None),
    webhook_notify_checkout: Optional[str] = Form(None),
    webhook_notify_break: Optional[str] = Form(None),
    webhook_notify_late: Optional[str] = Form(None),
    webhook_notify_absence: Optional[str] = Form(None),
    face_verification_enabled: Optional[str] = Form(None),
    face_verification_provider: Optional[str] = Form(None),
    smtp_host: Optional[str] = Form(None),
    smtp_port: Optional[int] = Form(None),
    smtp_username: Optional[str] = Form(None),
    smtp_password: Optional[str] = Form(None),
    smtp_from_email: Optional[str] = Form(None),
    smtp_to_email: Optional[str] = Form(None),
    email_notify_monthly_report: Optional[str] = Form(None),
    live_tracking_enabled: Optional[str] = Form(None),
    live_tracking_interval_minutes: Optional[int] = Form(None),
    logo: Optional[UploadFile] = File(None),
    current_user=Depends(get_current_admin),
):
    company_id = current_user["company_id"]
    updates = {}
    if company_name is not None:
        updates["company_name"] = company_name
    if primary_color is not None:
        updates["primary_color"] = primary_color
    if accent_color is not None:
        updates["accent_color"] = accent_color
    if webhook_url is not None:
        # Anti-SSRF: company admins must not be able to point the server at
        # internal services. Empty string clears the webhook.
        if webhook_url:
            try:
                webhook_url = validate_outbound_url(webhook_url, context="company_config")
            except UnsafeOutboundURL as e:
                raise HTTPException(status_code=400, detail=str(e))
            # Provision an HMAC signing secret for the webhook if missing —
            # the admin uses it to verify the X-UruCheck-Signature header.
            try:
                current = await database.fetch_one(
                    "SELECT webhook_secret FROM company_config WHERE company_id = :cid",
                    {"cid": company_id}
                )
                if not current or not current["webhook_secret"]:
                    import secrets as _secrets
                    await database.execute(
                        "UPDATE company_config SET webhook_secret = :s WHERE company_id = :cid",
                        {"s": _secrets.token_urlsafe(32), "cid": company_id}
                    )
            except Exception as e:
                # Non-fatal: send_webhook provisions the secret lazily too
                logger.warning("[company] No se pudo provisionar el secreto de firma del webhook: %s", e)
        updates["webhook_url"] = webhook_url
    if bonus_success_message is not None:
        updates["bonus_success_message"] = bonus_success_message
    if bonus_pending_message is not None:
        updates["bonus_pending_message"] = bonus_pending_message
    for field in ["webhook_notify_checkin", "webhook_notify_checkout", "webhook_notify_break", "webhook_notify_late", "webhook_notify_absence"]:
        val = locals().get(field)
        if val is not None:
            updates[field] = val.lower() == "true"

    if face_verification_enabled is not None:
        updates["face_verification_enabled"] = face_verification_enabled.lower() == "true"
    if face_verification_provider is not None:
        updates["face_verification_provider"] = face_verification_provider

    if smtp_host is not None:
        updates["smtp_host"] = smtp_host
    if smtp_port is not None:
        updates["smtp_port"] = smtp_port
    if smtp_username is not None:
        updates["smtp_username"] = smtp_username
    if smtp_password is not None:
        clean_pwd = smtp_password.strip()
        # Only update if not a masked placeholder and not empty
        if clean_pwd and clean_pwd != "********":
            updates["smtp_password"] = encrypt_secret(clean_pwd)
    if smtp_from_email is not None:
        updates["smtp_from_email"] = smtp_from_email
    if smtp_to_email is not None:
        updates["smtp_to_email"] = smtp_to_email
    if email_notify_monthly_report is not None:
        updates["email_notify_monthly_report"] = email_notify_monthly_report.lower() == "true"
    if live_tracking_enabled is not None:
        updates["live_tracking_enabled"] = live_tracking_enabled.lower() == "true"
    if live_tracking_interval_minutes is not None:
        updates["live_tracking_interval_minutes"] = max(5, min(120, int(live_tracking_interval_minutes)))

    if logo:
        # SECURITY: SVG is deliberately rejected — it can embed <script> and is
        # served same-origin, enabling stored XSS.
        if not logo.content_type or not logo.content_type.startswith("image/"):
            raise HTTPException(status_code=400, detail="El archivo debe ser una imagen")
        ext = logo.filename.split(".")[-1].lower() if logo.filename else "png"
        if ext not in ("png", "jpg", "jpeg", "webp"):
            raise HTTPException(status_code=400, detail="Formato no permitido. Use PNG, JPG o WebP")

        old = await database.fetch_one(
            "SELECT logo_path FROM company_config WHERE company_id = :cid",
            {"cid": company_id}
        )
        if old and old["logo_path"] and os.path.exists(old["logo_path"]):
            try:
                os.remove(old["logo_path"])
            except Exception as e:
                logger.warning("[company] No se pudo eliminar el logo anterior: %s", e)

        logos_dir = os.path.join(settings.PHOTOS_PATH, "logos")
        os.makedirs(logos_dir, exist_ok=True)
        filename = f"logo_{company_id}_{uuid.uuid4().hex}.{ext}"
        logo_path = os.path.join(logos_dir, filename)
        # Chunked read with hard size limit — prevents memory exhaustion
        content, total = b"", 0
        while True:
            chunk = await logo.read(1024 * 512)
            if not chunk:
                break
            total += len(chunk)
            if total > MAX_LOGO_BYTES:
                raise HTTPException(status_code=413, detail="El logo excede el tamaño máximo permitido (5 MB).")
            content += chunk
        with open(logo_path, "wb") as f:
            f.write(content)
        updates["logo_path"] = logo_path

    # Whitelist filtering to avoid arbitrary column mutation (H11)
    updates = {k: v for k, v in updates.items() if k in _ALLOWED_CONFIG_UPDATE_FIELDS}

    if not updates:
        raise HTTPException(status_code=400, detail="No hay datos para actualizar")

    # Ensure company_config row exists for this tenant
    existing = await database.fetch_one(
        "SELECT id FROM company_config WHERE company_id = :cid",
        {"cid": company_id}
    )
    if not existing:
        comp = await database.fetch_one("SELECT name FROM companies WHERE id = :cid", {"cid": company_id})
        comp_name = comp["name"] if comp else "Mi Empresa"
        await database.execute(
            "INSERT INTO company_config (company_id, company_name) VALUES (:cid, :name) ON CONFLICT (company_id) DO NOTHING",
            {"cid": company_id, "name": comp_name}
        )

    updates["updated_at"] = "NOW()"
    query, params = build_dynamic_update_query(
        table_name="company_config",
        update_fields=updates,
        where_clause="company_id = :cid",
        where_params={"cid": company_id},
    )
    await database.execute(query, params)
    return {"message": "Configuración actualizada"}


@router.get("/{company_id}/logo")
async def get_public_logo(company_id: str):
    row = await database.fetch_one(
        "SELECT logo_path FROM company_config WHERE company_id = :cid",
        {"cid": company_id}
    )
    if not row or not row["logo_path"]:
        raise HTTPException(status_code=404, detail="Sin logo configurado")
    path = row["logo_path"]
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="Archivo no encontrado")
    return FileResponse(path)


@router.post("/webhook/test", dependencies=[Depends(get_current_admin)])
async def test_webhook(current_user=Depends(get_current_admin)):
    company_id = current_user["company_id"]
    row = await database.fetch_one(
        "SELECT webhook_url FROM company_config WHERE company_id = :cid",
        {"cid": company_id}
    )
    if not row or not row["webhook_url"]:
        raise HTTPException(status_code=400, detail="No hay URL de Webhook configurada")
    url = row["webhook_url"]
    # Anti-SSRF: re-validate at request time (config may predate validation)
    try:
        url = validate_outbound_url(url, context="webhook_test")
    except UnsafeOutboundURL as e:
        raise HTTPException(status_code=400, detail=str(e))
    payload = {
        "message": "🤖 Mensaje de prueba del sistema de asistencia",
        "data": {
            "employee": "Empleado de Prueba",
            "type": "check_in",
            "status": "on_time",
            "hora": "11:00:00"
        }
    }
    # Deliver through the SAME pipeline as real events: signed, retried and
    # status-checked — otherwise a receiver that enforces the HMAC signature
    # would reject this test while accepting real events (confusing).
    from agent_controller import send_webhook
    delivered = await send_webhook("webhook_test", payload, company_id)
    if not delivered:
        raise HTTPException(
            status_code=502,
            detail="El webhook no aceptó el evento (verifica la URL, que responda 2xx y la verificación de firma)."
        )
    return {
        "success": True,
        "message": "✅ Webhook firmado y entregado correctamente (el servidor respondió HTTP 2xx).",
    }


@router.post("/report/send-email")
async def send_monthly_report_email(current_user=Depends(get_current_admin)):
    company_id = current_user["company_id"]

    # Verificar configuración SMTP
    row = await database.fetch_one(
        "SELECT smtp_host, smtp_username, smtp_password, smtp_to_email FROM company_config WHERE company_id = :cid",
        {"cid": company_id}
    )
    if not row or not row["smtp_host"] or not row["smtp_username"] or not row["smtp_password"]:
        raise HTTPException(
            status_code=400,
            detail="Servidor SMTP no configurado. Complete los datos de host, usuario y contraseña SMTP en la pestaña de configuración."
        )
    if not row["smtp_to_email"]:
        raise HTTPException(
            status_code=400,
            detail="Falta el destinatario (Correo de destino). Configúrelo en la pestaña de Email y vuelva a intentar."
        )

    from agent_controller import run_monthly_report_for_company
    try:
        # Manual send: explicit admin intent — the email_notify_monthly_report
        # toggle only gates the automatic monthly job.
        result = await run_monthly_report_for_company(company_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al procesar o enviar el reporte: {str(e)}")

    employees = result.get("employees", 0)
    if employees == 0:
        raise HTTPException(
            status_code=400,
            detail="La empresa no tiene empleados activos en el período: no hay reporte para enviar."
        )
    if result.get("email_error"):
        # The email actually failed — never report a false success
        raise HTTPException(status_code=502, detail=result["email_error"])
    if not result.get("email_sent"):
        raise HTTPException(
            status_code=502,
            detail="El reporte se generó pero no se pudo enviar por correo. Revise la configuración SMTP."
        )
    return {
        "success": True,
        "message": f"Reporte mensual enviado exitosamente por correo ({employees} empleados).",
        "webhook_sent": result.get("webhook_sent", False),
    }
