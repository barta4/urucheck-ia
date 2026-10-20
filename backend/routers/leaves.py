import logging
import os
import uuid
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from typing import Optional, List
from datetime import date, datetime
from database import database
from auth import get_current_user, get_current_admin
from config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/leaves", tags=["leaves"])

MAX_CERTIFICATE_BYTES = 10 * 1024 * 1024
MAX_REASON_LENGTH = 50


def _parse_form_date(value: str, field_label: str) -> date:
    try:
        return date.fromisoformat(value.strip())
    except (ValueError, AttributeError):
        raise HTTPException(
            status_code=400,
            detail=f"La fecha de '{field_label}' no es válida. Use el formato AAAA-MM-DD."
        )


@router.post("/")
async def create_leave_request(
    start_date: str = Form(...),
    end_date: str = Form(...),
    reason: str = Form(...),
    certificate: Optional[UploadFile] = File(None),
    current_user: dict = Depends(get_current_user)
):
    employee_id = current_user["id"]
    company_id = current_user["company_id"]

    # Validate dates: ISO format and chronological order
    start = _parse_form_date(start_date, "inicio")
    end = _parse_form_date(end_date, "fin")
    if end < start:
        raise HTTPException(status_code=400, detail="La fecha de fin no puede ser anterior a la fecha de inicio.")

    # reason column is VARCHAR(50) — longer values would crash with a raw 500
    reason = (reason or "").strip()
    if not reason:
        raise HTTPException(status_code=400, detail="El motivo de la licencia es obligatorio.")
    if len(reason) > MAX_REASON_LENGTH:
        raise HTTPException(
            status_code=400,
            detail=f"El motivo no puede superar los {MAX_REASON_LENGTH} caracteres."
        )

    cert_path = None
    if certificate:
        ext = certificate.filename.split(".")[-1] if certificate.filename else "jpg"
        if ext.lower() not in ("png", "jpg", "jpeg", "webp", "pdf"):
            raise HTTPException(status_code=400, detail="Formato no permitido para certificado.")

        cert_dir = os.path.join(settings.PHOTOS_PATH, "certificates")
        os.makedirs(cert_dir, exist_ok=True)
        filename = f"cert_{company_id}_{employee_id}_{uuid.uuid4().hex}.{ext.lower()}"
        cert_path = os.path.join(cert_dir, filename)

        # Chunked read — aborts before buffering oversized files in RAM
        chunks = []
        total = 0
        while True:
            chunk = await certificate.read(1024 * 512)
            if not chunk:
                break
            total += len(chunk)
            if total > MAX_CERTIFICATE_BYTES:
                raise HTTPException(status_code=413, detail="El certificado excede el tamaño máximo permitido (10 MB).")
            chunks.append(chunk)
        content = b"".join(chunks)

        try:
            with open(cert_path, "wb") as f:
                f.write(content)
        except (PermissionError, OSError) as e:
            logger.error("[leaves] No se pudo guardar el certificado en disco: %s", e)
            raise HTTPException(status_code=500, detail="No se pudo guardar el certificado. Inténtalo más tarde.")

    query = """
        INSERT INTO leave_requests (company_id, employee_id, start_date, end_date, reason, certificate_path)
        VALUES (:cid, :eid, :start, :end, :reason, :cert)
        RETURNING id
    """
    row = await database.fetch_one(query, {
        "cid": company_id,
        "eid": employee_id,
        "start": start,
        "end": end,
        "reason": reason,
        "cert": cert_path
    })

    return {"message": "Solicitud de licencia creada correctamente", "id": str(row["id"])}

@router.get("/me")
async def get_my_leaves(current_user: dict = Depends(get_current_user)):
    employee_id = current_user["id"]
    company_id = current_user["company_id"]
    
    rows = await database.fetch_all(
        "SELECT * FROM leave_requests WHERE employee_id = :eid AND company_id = :cid ORDER BY created_at DESC",
        {"eid": employee_id, "cid": company_id}
    )
    return [dict(r) for r in rows]

@router.get("/")
async def get_company_leaves(current_user: dict = Depends(get_current_admin)):
    company_id = current_user["company_id"]
    
    rows = await database.fetch_all(
        """
        SELECT l.*, e.name as employee_name
        FROM leave_requests l
        JOIN employees e ON l.employee_id = e.id
        WHERE l.company_id = :cid
        ORDER BY l.created_at DESC
        """,
        {"cid": company_id}
    )
    return [dict(r) for r in rows]

@router.patch("/{leave_id}/status")
async def update_leave_status(
    leave_id: str, 
    status: str = Form(...), 
    current_user: dict = Depends(get_current_admin)
):
    company_id = current_user["company_id"]
    
    if status not in ("approved", "rejected", "pending"):
        raise HTTPException(status_code=400, detail="Estado inválido")

    row = await database.fetch_one(
        """UPDATE leave_requests
           SET status = :status
           WHERE id = :id AND company_id = :cid
           RETURNING id, employee_id, start_date, end_date""",
        {"status": status, "id": leave_id, "cid": company_id}
    )
    if not row:
        raise HTTPException(status_code=404, detail="Solicitud no encontrada")

    # Notify the employee about the decision (push) — they would otherwise
    # have to poll the Leaves screen to discover it.
    if status in ("approved", "rejected"):
        try:
            from routers.notifications import send_push_notification
            emp = await database.fetch_one(
                "SELECT id, name, expo_push_token FROM employees WHERE id = :eid AND company_id = :cid",
                {"eid": str(row["employee_id"]), "cid": company_id}
            )
            if emp and emp["expo_push_token"]:
                if status == "approved":
                    title = "✅ Licencia aprobada"
                    body = (f"Hola {emp['name']}, tu licencia del {row['start_date']} al {row['end_date']} "
                            "fue APROBADA. ¡Que la disfrutes!")
                else:
                    title = "🔴 Licencia rechazada"
                    body = (f"Hola {emp['name']}, tu solicitud de licencia del {row['start_date']} "
                            f"al {row['end_date']} fue rechazada. Contacta a tu administrador para más detalles.")
                await send_push_notification(to=emp["expo_push_token"], title=title, body=body)
        except Exception as e:
            logger.warning("[leaves] No se pudo notificar al empleado el cambio de estado: %s", e)

    return {"message": f"Solicitud marcada como {status}"}
