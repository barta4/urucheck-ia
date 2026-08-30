"""
Plans management — CRUD (super-admin only for now).
"""
import logging
from fastapi import APIRouter, HTTPException, Depends
from typing import List
from schemas import PlanCreate, PlanUpdate, PlanOut
from auth import get_current_user, get_current_super_admin
from database import database

logger = logging.getLogger(__name__)

# Whitelist of column names allowed in the dynamic UPDATE SET clause.
_ALLOWED_PLAN_UPDATE_FIELDS = {
    "name", "slug", "description", "price_monthly", "price_yearly",
    "max_employees", "max_geofences", "face_verification", "webhooks",
    "ai_chat", "export_reports", "priority_support", "custom_branding",
    "api_access", "trial_days", "active",
}

router = APIRouter(prefix="/api/plans", tags=["plans"])


@router.get("/", response_model=List[dict])
async def list_plans(current_user=Depends(get_current_user)):
    """List all available active plans with company count."""
    rows = await database.fetch_all(
        """
        SELECT p.*,
               COUNT(c.id) FILTER (WHERE c.active = true) AS company_count
        FROM plans p
        LEFT JOIN companies c ON c.plan_id = p.id
        WHERE p.active = true
        GROUP BY p.id
        ORDER BY p.price_monthly ASC
        """
    )
    return [dict(r) for r in rows]


@router.get("/all")
async def list_all_plans(current_user=Depends(get_current_super_admin)):
    """List ALL plans including inactive (superadmin only)."""
    rows = await database.fetch_all(
        """
        SELECT p.*,
               COUNT(c.id) FILTER (WHERE c.active = true) AS company_count
        FROM plans p
        LEFT JOIN companies c ON c.plan_id = p.id
        GROUP BY p.id
        ORDER BY p.price_monthly ASC
        """
    )
    return [dict(r) for r in rows]


@router.post("/", response_model=PlanOut)
async def create_plan(data: PlanCreate, current_user=Depends(get_current_super_admin)):
    existing = await database.fetch_one("SELECT id FROM plans WHERE slug = :slug", {"slug": data.slug})
    if existing:
        raise HTTPException(status_code=400, detail="Ya existe un plan con ese slug")

    plan_id = await database.execute(
        """
        INSERT INTO plans (name, slug, description, price_monthly, price_yearly,
                          max_employees, max_geofences, face_verification, webhooks,
                          ai_chat, export_reports, priority_support, custom_branding,
                          api_access, trial_days)
        VALUES (:name, :slug, :desc, :pm, :py, :me, :mg, :fv, :wh, :ai, :er, :ps, :cb, :aa, :td)
        RETURNING id
        """,
        {
            "name": data.name, "slug": data.slug, "desc": data.description,
            "pm": data.price_monthly, "py": data.price_yearly,
            "me": data.max_employees, "mg": data.max_geofences,
            "fv": data.face_verification, "wh": data.webhooks, "ai": data.ai_chat,
            "er": data.export_reports, "ps": data.priority_support,
            "cb": data.custom_branding, "aa": data.api_access, "td": data.trial_days,
        }
    )

    row = await database.fetch_one("SELECT * FROM plans WHERE id = :id", {"id": plan_id})
    return dict(row)


@router.patch("/{plan_id}")
async def update_plan(plan_id: str, data: PlanUpdate, current_user=Depends(get_current_super_admin)):
    updates = {k: v for k, v in data.model_dump(exclude_unset=True).items()}
    if not updates:
        raise HTTPException(status_code=400, detail="No hay datos para actualizar")

    # Security: only allow whitelisted column names in the SET clause
    safe_updates = {k: v for k, v in updates.items() if k in _ALLOWED_PLAN_UPDATE_FIELDS}
    if not safe_updates:
        raise HTTPException(status_code=400, detail="No hay campos válidos para actualizar")

    set_clause = ", ".join([f"{k} = :{k}" for k in safe_updates.keys()])
    safe_updates["id"] = plan_id
    await database.execute(f"UPDATE plans SET {set_clause} WHERE id = :id", safe_updates)
    return {"message": "Plan actualizado"}


@router.delete("/{plan_id}")
async def delete_plan(plan_id: str, current_user=Depends(get_current_super_admin)):
    # Check if any company uses this plan
    users = await database.fetch_one(
        "SELECT COUNT(*) as cnt FROM companies WHERE plan_id = :pid", {"pid": plan_id}
    )
    if users["cnt"] > 0:
        raise HTTPException(status_code=400, detail=f"No se puede eliminar: {users['cnt']} empresas usan este plan")

    await database.execute("DELETE FROM plans WHERE id = :id", {"id": plan_id})
    return {"message": "Plan eliminado"}
