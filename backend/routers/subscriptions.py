"""
Subscription management — company self-service + super-admin control.
"""
from fastapi import APIRouter, HTTPException, Depends
import json
from datetime import datetime, timedelta
from typing import Optional
from schemas import SubscriptionOut, ChangePlanRequest
from auth import get_current_user, get_current_admin
from database import database

router = APIRouter(prefix="/api/subscriptions", tags=["subscriptions"])


@router.get("/my")
async def get_my_subscription(current_user=Depends(get_current_admin)):
    """Get current user's company subscription"""
    company_id = current_user["company_id"]

    sub = await database.fetch_one(
        """
        SELECT s.*, p.name as plan_name, p.slug as plan_slug,
               p.max_employees, p.max_geofences, p.face_verification,
               p.webhooks, p.ai_chat, p.export_reports, p.priority_support
        FROM subscriptions s
        LEFT JOIN plans p ON s.plan_id = p.id
        WHERE s.company_id = :cid
        """,
        {"cid": company_id}
    )

    if not sub:
        raise HTTPException(status_code=404, detail="Suscripción no encontrada")

    result = dict(sub)

    # Calculate trial status using UTC-aware datetime to match PostgreSQL timestamps
    if sub["trial_end"]:
        from datetime import timezone
        now = datetime.now(timezone.utc)
        trial_end = sub["trial_end"]
        # Ensure trial_end is tz-aware for comparison
        if trial_end.tzinfo is None:
            trial_end = trial_end.replace(tzinfo=timezone.utc)
        remaining_seconds = (trial_end - now).total_seconds()
        result["trial_remaining_days"] = max(0, int(remaining_seconds / 86400))
        result["is_trial_active"] = remaining_seconds > 0
    else:
        result["trial_remaining_days"] = 0
        result["is_trial_active"] = False

    return result


@router.post("/change-plan")
async def change_plan(
    data: ChangePlanRequest,
    current_user=Depends(get_current_admin)
):
    """
    Change company's plan.
    Validates compatibility and updates subscription.
    """
    company_id = current_user["company_id"]

    # Get new plan
    new_plan = await database.fetch_one("SELECT * FROM plans WHERE id = :pid AND active = true", {"pid": str(data.plan_id)})
    if not new_plan:
        raise HTTPException(status_code=404, detail="Plan no encontrado")

    # Get current subscription
    sub = await database.fetch_one(
        "SELECT * FROM subscriptions WHERE company_id = :cid", {"cid": company_id}
    )
    if not sub:
        raise HTTPException(status_code=404, detail="Suscripción no encontrada")

    old_plan_id = sub["plan_id"]

    # Check employee limit compatibility
    emp_count = await database.fetch_one(
        "SELECT COUNT(*) as cnt FROM employees WHERE company_id = :cid AND active = true",
        {"cid": company_id}
    )
    if emp_count["cnt"] > new_plan["max_employees"]:
        raise HTTPException(
            status_code=400,
            detail=f"El nuevo plan permite máximo {new_plan['max_employees']} empleados, tienes {emp_count['cnt']}. Reduce empleados primero."
        )

    # Update subscription
    await database.execute(
        """
        UPDATE subscriptions SET
            plan_id = :pid,
            status = 'active',
            updated_at = NOW()
        WHERE company_id = :cid
        """,
        {"pid": str(data.plan_id), "cid": company_id}
    )

    # Update company plan_id
    await database.execute(
        "UPDATE companies SET plan_id = :pid, updated_at = NOW() WHERE id = :cid",
        {"pid": str(data.plan_id), "cid": company_id}
    )

    # Log the change
    await database.execute(
        """
        INSERT INTO audit_logs (company_id, user_id, action, resource, details)
        VALUES (:cid, :uid, 'plan_changed', 'subscription', :details)
        """,
        {
            "cid": company_id,
            "uid": current_user["id"],
            "details": json.dumps({"old_plan_id": str(old_plan_id), "new_plan_id": str(data.plan_id)})
        }
    )

    return {"message": f"Plan cambiado a '{new_plan['name']}' exitosamente"}


@router.get("/check-feature/{feature}")
async def check_feature(feature: str, current_user=Depends(get_current_user)):
    """Check if current company's plan includes a specific feature"""
    company_id = current_user["company_id"]

    sub = await database.fetch_one(
        """
        SELECT p.face_verification, p.webhooks, p.ai_chat, p.export_reports,
               p.priority_support, p.custom_branding, p.api_access
        FROM subscriptions s
        JOIN plans p ON s.plan_id = p.id
        WHERE s.company_id = :cid
        """,
        {"cid": company_id}
    )

    if not sub:
        raise HTTPException(status_code=404, detail="Suscripción no encontrada")

    feature_map = {
        "face_verification": "face_verification",
        "webhooks": "webhooks",
        "ai_chat": "ai_chat",
        "export_reports": "export_reports",
        "priority_support": "priority_support",
        "custom_branding": "custom_branding",
        "api_access": "api_access",
    }

    if feature not in feature_map:
        raise HTTPException(status_code=400, detail=f"Feature '{feature}' no reconocido")

    return {
        "feature": feature,
        "available": sub[feature_map[feature]],
        "message": f"Feature '{feature}' {'disponible' if sub[feature_map[feature]] else 'NO disponible en tu plan'}"
    }


@router.get("/")
async def list_subscriptions(
    status: Optional[str] = None,
    current_user=Depends(get_current_admin)
):
    """List all subscriptions (admin view)"""
    conditions = ["1=1"]
    params = {}

    is_super_admin = current_user.get("is_super_admin", False)
    if not is_super_admin:
        conditions.append("s.company_id = :cid")
        params["cid"] = current_user["company_id"]

    if status:
        conditions.append("s.status = :status")
        params["status"] = status

    where = " AND ".join(conditions)
    rows = await database.fetch_all(
        f"""
        SELECT s.*, c.name as company_name, c.slug as company_slug, c.admin_email,
               p.name as plan_name, p.slug as plan_slug
        FROM subscriptions s
        JOIN companies c ON s.company_id = c.id
        LEFT JOIN plans p ON s.plan_id = p.id
        WHERE {where}
        ORDER BY s.created_at DESC
        """,
        params
    )
    return [dict(r) for r in rows]
