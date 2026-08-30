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

router = APIRouter(prefix="/api/company", tags=["company"])


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
        print(f"[Company Router Error] Fallo al recuperar company_config de la base de datos: {e}")

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
        print(f"[Company Config Router Error] Fallo al recuperar saas_settings: {e}")

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

    # If authenticated, return full config including sensitive fields
    if current_user:
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
        updates["smtp_password"] = smtp_password
    if smtp_from_email is not None:
        updates["smtp_from_email"] = smtp_from_email
    if smtp_to_email is not None:
        updates["smtp_to_email"] = smtp_to_email
    if email_notify_monthly_report is not None:
        updates["email_notify_monthly_report"] = email_notify_monthly_report.lower() == "true"

    if logo:
        if not logo.content_type.startswith("image/"):
            raise HTTPException(status_code=400, detail="El archivo debe ser una imagen")
        ext = logo.filename.split(".")[-1].lower() if logo.filename else "png"
        if ext not in ("png", "jpg", "jpeg", "svg", "webp"):
            raise HTTPException(status_code=400, detail="Formato no permitido. Use PNG, JPG o SVG")

        old = await database.fetch_one(
            "SELECT logo_path FROM company_config WHERE company_id = :cid",
            {"cid": company_id}
        )
        if old and old["logo_path"] and os.path.exists(old["logo_path"]):
            try:
                os.remove(old["logo_path"])
            except Exception:
                pass

        logos_dir = os.path.join(settings.PHOTOS_PATH, "logos")
        os.makedirs(logos_dir, exist_ok=True)
        filename = f"logo_{company_id}_{uuid.uuid4().hex}.{ext}"
        logo_path = os.path.join(logos_dir, filename)
        content = await logo.read()
        with open(logo_path, "wb") as f:
            f.write(content)
        updates["logo_path"] = logo_path

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
    set_parts = []
    params = {"cid": company_id}
    for k, v in updates.items():
        if v == "NOW()":
            set_parts.append(f"{k} = NOW()")
        else:
            set_parts.append(f"{k} = :{k}")
            params[k] = v

    set_clause = ", ".join(set_parts)
    await database.execute(
        f"UPDATE company_config SET {set_clause} WHERE company_id = :cid", params
    )
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
    payload = {
        "event": "test",
        "message": "🤖 Mensaje de prueba del sistema de asistencia",
        "timestamp": datetime.now(ZoneInfo(settings.TIMEZONE)).isoformat(),
        "data": {
            "employee": "Empleado de Prueba",
            "type": "check_in",
            "status": "on_time",
            "hora": "11:00:00"
        }
    }
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(url, json=payload)
        return {"success": True, "status_code": resp.status_code, "message": f"Webhook respondio con HTTP {resp.status_code}"}
    except httpx.TimeoutException:
        raise HTTPException(status_code=408, detail="El Webhook no respondió en tiempo (timeout)")
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Error al conectar con el Webhook: {str(e)}")


@router.post("/report/send-email")
async def send_monthly_report_email(current_user=Depends(get_current_admin)):
    company_id = current_user["company_id"]
    
    # Verificar configuración SMTP
    row = await database.fetch_one(
        "SELECT smtp_host, smtp_username, smtp_password FROM company_config WHERE company_id = :cid",
        {"cid": company_id}
    )
    if not row or not row["smtp_host"] or not row["smtp_username"] or not row["smtp_password"]:
        raise HTTPException(
            status_code=400, 
            detail="Servidor SMTP no configurado. Complete los datos de host, usuario y contraseña SMTP en la pestaña de configuración."
        )
        
    from agent_controller import run_monthly_report_for_company
    try:
        await run_monthly_report_for_company(company_id)
        return {"success": True, "message": "Reporte mensual enviado exitosamente por correo electrónico."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al procesar o enviar el reporte: {str(e)}")
