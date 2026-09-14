"""
Company management endpoints.
"""
import json
import re
from datetime import datetime, timedelta
from fastapi import APIRouter, HTTPException, Depends, Request
from typing import Optional
from pydantic import BaseModel, EmailStr
from auth import get_password_hash, get_current_user, get_current_admin, get_current_super_admin, create_access_token
from database import database
from db_utils import build_dynamic_update_query
from schemas import CompanyCreate, CompanyOut, CompanyStatusUpdate
from slowapi import Limiter
from slowapi.util import get_remote_address

router = APIRouter(prefix="/api/companies", tags=["companies"])
limiter = Limiter(key_func=get_remote_address)


class RegisterResponse(BaseModel):
    message: str
    company_id: str
    company_slug: str
    admin_token: str
    admin_id: str
    admin_name: str


@router.post("/register", response_model=RegisterResponse)
@limiter.limit("5/minute")
async def register_company(request: Request, data: CompanyCreate):
    """
    Self-service company registration.
    Creates: company, company_config, admin employee, subscription.
    """
    if not re.match(r'^[a-z0-9][a-z0-9-]*[a-z0-9]$', data.slug) or len(data.slug) < 3:
        raise HTTPException(status_code=400, detail="Slug inválido. Use 3+ caracteres, solo letras minúsculas, números y guiones.")

    existing = await database.fetch_one(
        "SELECT id FROM companies WHERE slug = :slug OR admin_email = :email",
        {"slug": data.slug, "email": data.admin_email}
    )
    if existing:
        raise HTTPException(status_code=400, detail="Ya existe una empresa con ese slug o email de administrador")

    # Get plan
    plan = await database.fetch_one(
        "SELECT * FROM plans WHERE slug = :slug AND active = true",
        {"slug": data.plan_slug}
    )
    if not plan:
        plan = await database.fetch_one("SELECT * FROM plans WHERE slug = 'free'")

    now = datetime.now()
    trial_days = plan["trial_days"] or 14
    trial_end = now + timedelta(days=trial_days)

    hashed_password = get_password_hash(data.admin_password)

    # Create company
    company_id = await database.execute(
        """
        INSERT INTO companies (plan_id, name, slug, admin_email, admin_password_hash,
                               status, trial_ends_at, billing_name)
        VALUES (:plan_id, :name, :slug, :email, :password_hash, 'trial', :trial_end, :billing)
        RETURNING id
        """,
        {
            "plan_id": str(plan["id"]),
            "name": data.name,
            "slug": data.slug,
            "email": data.admin_email,
            "password_hash": hashed_password,
            "trial_end": trial_end,
            "billing": data.billing_name,
        }
    )

    company_id_str = str(company_id)

    # Create config
    await database.execute(
        "INSERT INTO company_config (company_id, company_name) VALUES (:cid, :name)",
        {"cid": company_id_str, "name": data.name}
    )

    # Create admin employee
    admin_id = await database.execute(
        """
        INSERT INTO employees (company_id, name, email, password_hash, role)
        VALUES (:cid, :name, :email, :password_hash, 'admin')
        RETURNING id
        """,
        {
            "cid": company_id_str,
            "name": "Administrador",
            "email": data.admin_email,
            "password_hash": hashed_password,
        }
    )

    # Create subscription
    await database.execute(
        """
        INSERT INTO subscriptions (company_id, plan_id, status, trial_start, trial_end)
        VALUES (:cid, :pid, 'trial', :tstart, :tend)
        """,
        {"cid": company_id_str, "pid": str(plan["id"]), "tstart": now, "tend": trial_end}
    )

    # Audit
    await database.execute(
        """
        INSERT INTO audit_logs (company_id, action, resource, details)
        VALUES (:cid, 'company_created', 'company', :details)
        """,
        {"cid": company_id_str, "details": json.dumps({"name": data.name, "plan": plan["name"]})}
    )

    token_data = {
        "sub": str(admin_id),
        "company_id": company_id_str,
        "company_slug": data.slug,
    }
    token = create_access_token(token_data)

    return RegisterResponse(
        message=f"Empresa '{data.name}' creada exitosamente. Tienes {trial_days} días de prueba.",
        company_id=company_id_str,
        company_slug=data.slug,
        admin_token=token,
        admin_id=str(admin_id),
        admin_name="Administrador",
    )


@router.get("/")
async def list_companies(
    active_only: bool = True,
    current_user=Depends(get_current_admin)
):
    """
    List companies. Regular admins see only their own company.
    A super-admin role should be added to expose the full list.
    """
    is_super = current_user.get("is_super_admin", False)
    conditions = []
    params = {}
    if not is_super:
        conditions.append("id = :own_cid")
        params["own_cid"] = current_user["company_id"]
    if active_only:
        conditions.append("active = true")

    where = " AND ".join(conditions) if conditions else "1=1"
    rows = await database.fetch_all(
        f"""
        SELECT c.id, c.name, c.slug, c.plan_id, c.max_employees_override as max_employees, c.active, c.created_at,
               COUNT(e.id) as active_employees
        FROM companies c
        LEFT JOIN employees e ON c.id = e.company_id AND e.active = true
        WHERE {where}
        GROUP BY c.id
        ORDER BY c.name
        """,
        params
    )
    return [dict(r) for r in rows]


@router.get("/me")
async def get_my_company(current_user=Depends(get_current_admin)):
    """Get current user's company info"""
    company_id = current_user["company_id"]
    row = await database.fetch_one(
        "SELECT id, name, slug, plan_id, max_employees_override, active, created_at FROM companies WHERE id = :cid",
        {"cid": company_id}
    )
    if not row:
        raise HTTPException(status_code=404, detail="Empresa no encontrada")
    return dict(row)


@router.patch("/{company_id}")
async def update_company_status(
    company_id: str,
    payload: CompanyStatusUpdate,
    current_user=Depends(get_current_admin)
):
    """Update company status. Admins can modify their own, super-admins can modify any."""
    # Multi-tenant isolation: only allow operating on own company unless super-admin
    is_super = current_user.get("is_super_admin", False)
    if str(current_user["company_id"]) != company_id and not is_super:
        raise HTTPException(status_code=403, detail="No autorizado para modificar esta empresa")

    status = payload.status
    allowed_statuses = {"active", "suspended", "cancelled", "grace"}
    if status not in allowed_statuses:
        raise HTTPException(status_code=400, detail=f"Estado inválido. Debe ser uno de: {', '.join(allowed_statuses)}")

    updates = {}
    updates["status"] = status
    if status == "suspended":
        updates["suspended_at"] = "NOW()"
    elif status == "active":
        updates["suspended_at"] = None
        updates["cancelled_at"] = None
    elif status == "cancelled":
        updates["cancelled_at"] = "NOW()"

    query, params = build_dynamic_update_query(
        table_name="companies",
        update_fields=updates,
        where_clause="id = :cid",
        where_params={"cid": company_id},
    )
    await database.execute(query, params)
    return {"message": f"Estado actualizado a '{status}'"}


@router.post("/{company_id}/assign-plan")
async def assign_plan_to_company(
    company_id: str,
    plan_id: str,
    current_user=Depends(get_current_super_admin)
):
    """
    Super-admin assigns a plan to a company.
    Validates compatibility with current employee count.
    """

    # Get new plan
    new_plan = await database.fetch_one(
        "SELECT * FROM plans WHERE id = :pid AND active = true",
        {"pid": plan_id}
    )
    if not new_plan:
        raise HTTPException(status_code=404, detail="Plan no encontrado")

    # Get company
    company = await database.fetch_one(
        "SELECT id, name, plan_id FROM companies WHERE id = :cid",
        {"cid": company_id}
    )
    if not company:
        raise HTTPException(status_code=404, detail="Empresa no encontrada")

    # Check employee limit
    emp_count = await database.fetch_one(
        "SELECT COUNT(*) as cnt FROM employees WHERE company_id = :cid AND active = true",
        {"cid": company_id}
    )
    if emp_count["cnt"] > new_plan["max_employees"]:
        raise HTTPException(
            status_code=400,
            detail=f"El plan '{new_plan['name']}' permite máximo {new_plan['max_employees']} empleados, pero esta empresa tiene {emp_count['cnt']}. Reduce empleados o elige otro plan."
        )

    # Update company plan
    await database.execute(
        "UPDATE companies SET plan_id = :pid, updated_at = NOW() WHERE id = :cid",
        {"pid": plan_id, "cid": company_id}
    )

    # Update subscription
    existing_sub = await database.fetch_one(
        "SELECT id FROM subscriptions WHERE company_id = :cid",
        {"cid": company_id}
    )
    if existing_sub:
        await database.execute(
            """
            UPDATE subscriptions SET plan_id = :pid, status = 'active', updated_at = NOW()
            WHERE company_id = :cid
            """,
            {"pid": plan_id, "cid": company_id}
        )
    else:
        await database.execute(
            """
            INSERT INTO subscriptions (company_id, plan_id, status, trial_start, trial_end)
            VALUES (:cid, :pid, 'active', NOW(), NOW() + INTERVAL '30 days')
            """,
            {"cid": company_id, "pid": plan_id}
        )

    # Audit
    await database.execute(
        """
        INSERT INTO audit_logs (company_id, user_id, action, resource, resource_id, details)
        VALUES (:cid, :uid, 'plan_assigned', 'plan', :rid, :details)
        """,
        {
            "cid": company_id,
            "uid": current_user["id"],
            "rid": plan_id,
            "details": json.dumps({"plan_name": new_plan["name"], "company_name": company["name"]})
        }
    )

    return {
        "message": f"Plan '{new_plan['name']}' asignado a '{company['name']}' exitosamente"
    }


@router.delete("/{company_id}")
async def delete_company(
    company_id: str,
    force: bool = False,
    current_user=Depends(get_current_super_admin)
):
    """
    Super-admin soft-deletes a company.
    Deactivates company, its employees, and marks subscription as cancelled.
    """
    company = await database.fetch_one(
        "SELECT id, name, slug, status, active FROM companies WHERE id = :cid",
        {"cid": company_id}
    )
    if not company:
        raise HTTPException(status_code=404, detail="Empresa no encontrada")

    # Soft delete company
    await database.execute(
        """
        UPDATE companies SET
            active = false,
            status = 'deleted',
            deleted_at = NOW(),
            updated_at = NOW()
        WHERE id = :cid
        """,
        {"cid": company_id}
    )

    # Deactivate all company employees
    await database.execute(
        "UPDATE employees SET active = false WHERE company_id = :cid",
        {"cid": company_id}
    )

    # Cancel subscription
    await database.execute(
        "UPDATE subscriptions SET status = 'cancelled', updated_at = NOW() WHERE company_id = :cid",
        {"cid": company_id}
    )

    # Audit log
    await database.execute(
        """
        INSERT INTO audit_logs (company_id, user_id, action, resource, resource_id, details)
        VALUES (:cid, :uid, 'company_deleted', 'company', :cid, :details)
        """,
        {
            "cid": company_id,
            "uid": current_user["id"],
            "details": json.dumps({
                "company_name": company["name"],
                "company_slug": company["slug"],
                "action": "soft_delete"
            })
        }
    )

    return {
        "message": f"Empresa '{company['name']}' eliminada exitosamente del sistema."
    }

