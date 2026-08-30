"""
Audit log endpoints.
"""
from fastapi import APIRouter, Depends, Query
from typing import Optional, List
from datetime import date
from auth import get_current_user, get_current_admin
from database import database

router = APIRouter(prefix="/api/audit", tags=["audit"])


@router.get("/logs")
async def get_audit_logs(
    company_id: Optional[str] = None,
    action: Optional[str] = None,
    resource: Optional[str] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    limit: int = Query(100, le=1000),
    offset: int = 0,
    current_user=Depends(get_current_admin)
):
    """
    Get audit logs.
    Admin can only see logs for their company. Super-admin sees all.
    """
    is_super_admin = current_user.get("is_super_admin", False)

    conditions = []
    params = {"limit": limit, "offset": offset}

    if not is_super_admin:
        conditions.append("al.company_id = :cid")
        params["cid"] = current_user["company_id"]
    elif company_id:
        conditions.append("al.company_id = :cid")
        params["cid"] = company_id

    if action:
        conditions.append("al.action = :action")
        params["action"] = action

    if resource:
        conditions.append("al.resource = :resource")
        params["resource"] = resource

    if date_from:
        conditions.append("DATE(al.created_at) >= :date_from")
        params["date_from"] = date_from

    if date_to:
        conditions.append("DATE(al.created_at) <= :date_to")
        params["date_to"] = date_to

    where = " AND ".join(conditions) if conditions else "1=1"

    rows = await database.fetch_all(
        f"""
        SELECT al.*, e.name as user_name
        FROM audit_logs al
        LEFT JOIN employees e ON al.user_id = e.id
        WHERE {where}
        ORDER BY al.created_at DESC
        LIMIT :limit OFFSET :offset
        """,
        params
    )

    total = await database.fetch_one(
        f"SELECT COUNT(*) as cnt FROM audit_logs al WHERE {where}", params
    )

    return {
        "logs": [dict(r) for r in rows],
        "total": total["cnt"] if total else 0,
        "limit": limit,
        "offset": offset,
    }


@router.get("/actions")
async def get_distinct_actions(current_user=Depends(get_current_admin)):
    """Get list of distinct audit actions for filtering"""
    is_super_admin = current_user.get("is_super_admin", False)

    if not is_super_admin:
        rows = await database.fetch_all(
            "SELECT DISTINCT action FROM audit_logs WHERE company_id = :cid ORDER BY action",
            {"cid": current_user["company_id"]}
        )
    else:
        rows = await database.fetch_all("SELECT DISTINCT action FROM audit_logs ORDER BY action")

    return [r["action"] for r in rows]
