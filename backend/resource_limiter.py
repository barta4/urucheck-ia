"""
Resource limiter — enforces plan limits on key operations.
Used as a utility called from routers, not middleware (for clarity).
"""
from database import database
from fastapi import HTTPException


async def check_employee_limit(company_id: str) -> None:
    """Check if company can add more employees"""
    company = await database.fetch_one(
        """
        SELECT
            c.max_employees_override,
            p.max_employees
        FROM companies c
        LEFT JOIN plans p ON c.plan_id = p.id
        WHERE c.id = :cid
        """,
        {"cid": company_id}
    )

    if not company:
        raise HTTPException(status_code=404, detail="Empresa no encontrada")

    limit = company["max_employees_override"] or company["max_employees"]

    count = await database.fetch_one(
        "SELECT COUNT(*) as cnt FROM employees WHERE company_id = :cid AND active = true",
        {"cid": company_id}
    )

    if count["cnt"] >= limit:
        raise HTTPException(
            status_code=400,
            detail=f"Límite de {limit} empleados alcanzado. Actualiza tu plan para agregar más."
        )


async def check_geofence_limit(company_id: str) -> None:
    """Check if company can add more geofences"""
    company = await database.fetch_one(
        "SELECT p.max_geofences FROM companies c LEFT JOIN plans p ON c.plan_id = p.id WHERE c.id = :cid",
        {"cid": company_id}
    )

    if not company:
        raise HTTPException(status_code=404, detail="Empresa no encontrada")

    limit = company["max_geofences"] or 2

    count = await database.fetch_one(
        "SELECT COUNT(*) as cnt FROM geofences WHERE company_id = :cid",
        {"cid": company_id}
    )

    if count["cnt"] >= limit:
        raise HTTPException(
            status_code=400,
            detail=f"Límite de {limit} geocercas alcanzado. Actualiza tu plan."
        )


async def check_feature_access(company_id: str, feature: str) -> None:
    """Check if company's plan includes a feature, raise 402 if not"""
    feature_map = {
        "webhooks": "webhooks",
        "ai_chat": "ai_chat",
        "export_reports": "export_reports",
        "priority_support": "priority_support",
        "custom_branding": "custom_branding",
        "api_access": "api_access",
    }

    if feature not in feature_map:
        return  # Unknown feature, allow

    col = feature_map[feature]

    sub = await database.fetch_one(
        """
        SELECT p.*
        FROM subscriptions s
        JOIN plans p ON s.plan_id = p.id
        WHERE s.company_id = :cid
        """,
        {"cid": company_id}
    )

    if not sub or not sub.get(col, False):
        feature_names = {
            "webhooks": "Webhooks",
            "ai_chat": "Chat con IA (Gemini)",
            "export_reports": "Exportación de reportes",
            "priority_support": "Soporte prioritario",
            "custom_branding": "Marca personalizada",
            "api_access": "API personalizada",
        }
        raise HTTPException(
            status_code=402,
            detail=f"Feature '{feature_names.get(feature, feature)}' no disponible en tu plan. Actualiza para acceder."
        )


async def check_company_active(company_id: str) -> None:
    """Check if company is active and not suspended"""
    company = await database.fetch_one(
        "SELECT status, active FROM companies WHERE id = :cid",
        {"cid": company_id}
    )

    if not company:
        raise HTTPException(status_code=404, detail="Empresa no encontrada")

    if not company["active"]:
        raise HTTPException(status_code=403, detail="Empresa desactivada")

    if company["status"] == "suspended":
        raise HTTPException(
            status_code=403,
            detail="Cuenta suspendida. Contacta a soporte para reactivar."
        )

    if company["status"] == "cancelled":
        raise HTTPException(
            status_code=403,
            detail="Cuenta cancelada. Tus datos están disponibles por 30 días."
        )
