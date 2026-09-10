import logging
from datetime import datetime
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from database import database
from auth import get_current_admin, get_current_user
from routers.notifications import send_push_notification

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/locations", tags=["locations"])


class LocationReportPayload(BaseModel):
    latitude: float = Field(..., ge=-90.0, le=90.0, description="Latitud GPS")
    longitude: float = Field(..., ge=-180.0, le=180.0, description="Longitud GPS")
    accuracy: Optional[float] = Field(None, ge=0, description="Precisión en metros")
    battery_level: Optional[float] = Field(None, ge=0, le=100, description="Nivel de batería %")
    source: Optional[str] = Field("on_demand", description="Origen: on_demand o shift_tracking")


@router.post("/request/{employee_id}")
async def request_employee_location(
    employee_id: str,
    admin=Depends(get_current_admin),
):
    """
    Despacha una notificación Push de alta prioridad al dispositivo del empleado
    solicitando que reporte su ubicación GPS actual en tiempo real.
    """
    company_id = admin["company_id"]

    emp = await database.fetch_one(
        """
        SELECT id, name, expo_push_token, active
        FROM employees
        WHERE id = :eid AND company_id = :cid
        """,
        {"eid": employee_id, "cid": company_id},
    )
    if not emp:
        raise HTTPException(status_code=404, detail="Empleado no encontrado")

    if not emp["active"]:
        raise HTTPException(status_code=400, detail="El empleado no se encuentra activo")

    token = emp["expo_push_token"]
    if not token or not token.startswith("ExponentPushToken"):
        raise HTTPException(
            status_code=400,
            detail="El empleado no tiene un dispositivo registrado con notificaciones activas.",
        )

    # Dispatch High Priority Push Notification
    admin_name = admin.get("name") or "La administración"
    sent = await send_push_notification(
        to=token,
        title="📍 Solicitud de Ubicación",
        body=f"{admin_name} solicita confirmar tu ubicación actual.",
        data={
            "type": "LOCATION_REQUEST",
            "employee_id": str(emp["id"]),
            "requested_at": datetime.utcnow().isoformat(),
        },
    )

    # Log to audit
    try:
        await database.execute(
            """
            INSERT INTO audit_logs (company_id, user_id, action, resource, resource_id, details)
            VALUES (:cid, :uid, 'location_requested', 'employee', :eid, :details)
            """,
            {
                "cid": company_id,
                "uid": admin.get("id"),
                "eid": str(emp["id"]),
                "details": f'{{"target_name": "{emp["name"]}", "push_sent": {str(sent).lower()}}}',
            },
        )
    except Exception as e:
        logger.warning("Fallo al registrar audit log de solicitud de ubicación: %s", e)

    return {
        "status": "requested",
        "sent": sent,
        "message": f"Solicitud de ubicación enviada a {emp['name']}",
    }


@router.post("/request-all")
async def request_all_active_locations(
    admin=Depends(get_current_admin),
):
    """
    Solicita la ubicación a todos los empleados activos de la empresa
    que cuenten con token de dispositivo registrado.
    """
    company_id = admin["company_id"]

    employees = await database.fetch_all(
        """
        SELECT id, name, expo_push_token
        FROM employees
        WHERE company_id = :cid AND active = true AND expo_push_token IS NOT NULL
        """,
        {"cid": company_id},
    )

    valid_targets = [e for e in employees if e["expo_push_token"] and e["expo_push_token"].startswith("ExponentPushToken")]
    if not valid_targets:
        raise HTTPException(
            status_code=400,
            detail="Ningún empleado activo tiene un dispositivo vinculado con notificaciones.",
        )

    dispatched = 0
    admin_name = admin.get("name") or "La administración"
    for emp in valid_targets:
        sent = await send_push_notification(
            to=emp["expo_push_token"],
            title="📍 Solicitud de Ubicación",
            body=f"{admin_name} solicita confirmar tu ubicación actual.",
            data={
                "type": "LOCATION_REQUEST",
                "employee_id": str(emp["id"]),
                "requested_at": datetime.utcnow().isoformat(),
            },
        )
        if sent:
            dispatched += 1

    return {
        "status": "requested",
        "total_targets": len(valid_targets),
        "dispatched": dispatched,
        "message": f"Solicitud despachada a {dispatched} empleado(s)",
    }


@router.post("/report")
async def report_location(
    payload: LocationReportPayload,
    current_user=Depends(get_current_user),
):
    """
    Endpoint autenticado para que la aplicación móvil reporte la ubicación actual
    (invocado tras recibir una solicitud del panel o por reporte periódico durante la jornada).
    """
    employee_id = str(current_user["id"])
    company_id = str(current_user["company_id"])

    # 1. Update latest location columns in employees
    await database.execute(
        """
        UPDATE employees
        SET last_latitude = :lat,
            last_longitude = :lng,
            last_location_accuracy = :accuracy,
            last_location_at = NOW(),
            last_location_source = :source
        WHERE id = :eid AND company_id = :cid
        """,
        {
            "lat": payload.latitude,
            "lng": payload.longitude,
            "accuracy": payload.accuracy,
            "source": payload.source or "on_demand",
            "eid": employee_id,
            "cid": company_id,
        },
    )

    # 2. Insert into telemetry history table
    try:
        await database.execute(
            """
            INSERT INTO employee_location_reports (
                company_id, employee_id, latitude, longitude,
                accuracy, battery_level, source
            ) VALUES (
                :cid, :eid, :lat, :lng,
                :accuracy, :battery, :source
            )
            """,
            {
                "cid": company_id,
                "eid": employee_id,
                "lat": payload.latitude,
                "lng": payload.longitude,
                "accuracy": payload.accuracy,
                "battery": payload.battery_level,
                "source": payload.source or "on_demand",
            },
        )
    except Exception as e:
        logger.warning("Fallo al guardar reporte de ubicación en employee_location_reports: %s", e)

    return {
        "status": "ok",
        "message": "Ubicación reportada exitosamente",
        "timestamp": datetime.utcnow().isoformat(),
    }


@router.get("/live")
async def get_live_locations(
    admin=Depends(get_current_admin),
):
    """
    Retorna la lista de empleados con su última ubicación reportada hoy.
    """
    company_id = admin["company_id"]

    rows = await database.fetch_all(
        """
        SELECT
            e.id AS employee_id,
            e.name,
            e.email,
            e.last_latitude,
            e.last_longitude,
            e.last_location_accuracy,
            e.last_location_at,
            e.last_location_source,
            (e.expo_push_token IS NOT NULL AND e.expo_push_token LIKE 'ExponentPushToken%') AS has_device
        FROM employees e
        WHERE e.company_id = :cid AND e.active = true
        ORDER BY e.name ASC
        """,
        {"cid": company_id},
    )

    return [
        {
            "employee_id": str(r["employee_id"]),
            "name": r["name"],
            "email": r["email"],
            "latitude": float(r["last_latitude"]) if r["last_latitude"] is not None else None,
            "longitude": float(r["last_longitude"]) if r["last_longitude"] is not None else None,
            "accuracy": r["last_location_accuracy"],
            "updated_at": str(r["last_location_at"]) if r["last_location_at"] else None,
            "source": r["last_location_source"],
            "has_device": bool(r["has_device"]),
        }
        for r in rows
    ]
