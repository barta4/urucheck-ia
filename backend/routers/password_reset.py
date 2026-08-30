"""
Password reset endpoints.
Since there's no email server, this creates a reset request that the admin can fulfill.
"""
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, EmailStr
from datetime import datetime, timedelta, timezone
from auth import get_password_hash, get_current_admin
from database import database
import uuid

router = APIRouter(prefix="/api/auth", tags=["auth"])


from typing import Optional

class ForgotPasswordRequest(BaseModel):
    email: EmailStr
    company_slug: Optional[str] = None


class ResetPasswordRequest(BaseModel):
    employee_id: str
    new_password: str


@router.post("/forgot-password")
async def forgot_password(data: ForgotPasswordRequest):
    """
    Employee requests password reset.
    Creates a reset token (valid 24h) in DB. Admin must fulfill it.
    """
    clean_email = data.email.strip() if data.email else ""
    generic_msg = "Si el email existe en el sistema, se ha enviado una solicitud a tu administrador."

    if data.company_slug:
        company = await database.fetch_one(
            "SELECT id FROM companies WHERE slug = :slug AND active = true",
            {"slug": data.company_slug}
        )
        if not company:
            return {"message": generic_msg}
        emp = await database.fetch_one(
            "SELECT id, name, company_id FROM employees WHERE LOWER(email) = LOWER(:email) AND company_id = :cid AND active = true",
            {"email": clean_email, "cid": company["id"]}
        )
    else:
        # Fallback for mobile app where company_slug is not entered on the forgot screen
        emp = await database.fetch_one(
            """
            SELECT e.id, e.name, e.company_id 
            FROM employees e
            JOIN companies c ON e.company_id = c.id
            WHERE LOWER(e.email) = LOWER(:email) AND e.active = true AND c.active = true
            ORDER BY e.created_at DESC LIMIT 1
            """,
            {"email": clean_email}
        )

    if not emp:
        # Don't reveal if email exists (prevents user enumeration)
        return {"message": generic_msg}

    # Expire any previous pending tokens for this employee
    await database.execute(
        "UPDATE password_reset_requests SET status = 'expired' WHERE employee_id = :eid AND company_id = :cid AND status = 'pending'",
        {"eid": str(emp["id"]), "cid": str(emp["company_id"])}
    )

    # Create new reset request with 24h expiry
    token = str(uuid.uuid4())
    expires_at = datetime.now(timezone.utc) + timedelta(hours=24)
    await database.execute(
        """
        INSERT INTO password_reset_requests (employee_id, company_id, token, status, expires_at)
        VALUES (:eid, :cid, :token, 'pending', :expires_at)
        """,
        {"eid": str(emp["id"]), "cid": str(emp["company_id"]), "token": token, "expires_at": expires_at}
    )

    return {
        "message": "Solicitud enviada a tu administrador. Contacta a tu supervisor para restablecer tu contraseña."
    }


@router.post("/reset-password")
async def reset_password(data: ResetPasswordRequest, admin=Depends(get_current_admin)):
    """
    Admin resets an employee's password directly.
    Only operates within the admin's own company (multi-tenant isolation).
    """
    company_id = admin["company_id"]

    if len(data.new_password) < 8:
        raise HTTPException(status_code=400, detail="La contraseña debe tener al menos 8 caracteres")

    # Security: ensure employee belongs to admin's company
    emp = await database.fetch_one(
        "SELECT id, name FROM employees WHERE id = :eid AND company_id = :cid AND active = true",
        {"eid": data.employee_id, "cid": company_id}
    )
    if not emp:
        raise HTTPException(status_code=404, detail="Empleado no encontrado")

    hashed = get_password_hash(data.new_password)
    await database.execute(
        "UPDATE employees SET password_hash = :hash WHERE id = :eid AND company_id = :cid",
        {"hash": hashed, "eid": data.employee_id, "cid": company_id}
    )

    # Mark reset requests as fulfilled
    await database.execute(
        "UPDATE password_reset_requests SET status = 'fulfilled' WHERE employee_id = :eid AND company_id = :cid AND status = 'pending'",
        {"eid": data.employee_id, "cid": company_id}
    )

    return {"message": f"Contraseña de {emp['name']} restablecida exitosamente"}
