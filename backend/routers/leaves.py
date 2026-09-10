import os
import uuid
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from typing import Optional, List
from datetime import date
from database import database
from auth import get_current_user, get_current_admin
from config import settings

router = APIRouter(prefix="/api/leaves", tags=["leaves"])

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
    
    cert_path = None
    if certificate:
        ext = certificate.filename.split(".")[-1] if certificate.filename else "jpg"
        if ext.lower() not in ("png", "jpg", "jpeg", "webp", "pdf"):
            raise HTTPException(status_code=400, detail="Formato no permitido para certificado.")
            
        cert_dir = os.path.join(settings.PHOTOS_PATH, "certificates")
        os.makedirs(cert_dir, exist_ok=True)
        filename = f"cert_{company_id}_{employee_id}_{uuid.uuid4().hex}.{ext}"
        cert_path = os.path.join(cert_dir, filename)
        
        content = await certificate.read()
        if len(content) > 10 * 1024 * 1024:  # 10 MB limit (H8)
            raise HTTPException(status_code=413, detail="El certificado excede el tamaño máximo permitido (10 MB).")

        try:
            with open(cert_path, "wb") as f:
                f.write(content)
        except (PermissionError, OSError):
            fallback_dir = "/tmp/photos/certificates"
            os.makedirs(fallback_dir, exist_ok=True)
            cert_path = os.path.join(fallback_dir, filename)
            with open(cert_path, "wb") as f:
                f.write(content)

    query = """
        INSERT INTO leave_requests (company_id, employee_id, start_date, end_date, reason, certificate_path)
        VALUES (:cid, :eid, :start, :end, :reason, :cert)
        RETURNING id
    """
    row = await database.fetch_one(query, {
        "cid": company_id,
        "eid": employee_id,
        "start": start_date,
        "end": end_date,
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
        "UPDATE leave_requests SET status = :status WHERE id = :id AND company_id = :cid RETURNING id",
        {"status": status, "id": leave_id, "cid": company_id}
    )
    if not row:
        raise HTTPException(status_code=404, detail="Solicitud no encontrada")

    return {"message": f"Solicitud marcada como {status}"}
