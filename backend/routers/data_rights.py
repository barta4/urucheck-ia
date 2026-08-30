"""
Data subject rights endpoints (ARCO+) — multi-tenant.
"""
import os
import json
import csv
import io
from datetime import datetime, date, timedelta
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from auth import get_current_user
from database import database

router = APIRouter(prefix="/api/data-rights", tags=["data-rights"])


class DataDeletionRequest(BaseModel):
    delete_face_photo: bool = True
    delete_attendance_logs: bool = False
    reason: Optional[str] = None


@router.get("/export")
async def export_my_data(current_user=Depends(get_current_user)):
    employee_id = str(current_user["id"])
    company_id = str(current_user["company_id"])

    emp = await database.fetch_one(
        "SELECT id, name, email, role, active, face_reference_path, created_at FROM employees WHERE id = :eid AND company_id = :cid",
        {"eid": employee_id, "cid": company_id}
    )
    emp_data = dict(emp) if emp else {}
    emp_data["face_reference_path"] = "PRESENT" if emp_data.get("face_reference_path") else None

    schedules = await database.fetch_all(
        "SELECT * FROM schedules WHERE employee_id = :eid AND company_id = :cid", {"eid": employee_id, "cid": company_id}
    )

    cutoff = date.today() - timedelta(days=180)
    logs = await database.fetch_all(
        "SELECT * FROM attendance_logs WHERE employee_id = :eid AND company_id = :cid AND DATE(timestamp) >= :cutoff ORDER BY timestamp DESC",
        {"eid": employee_id, "cid": company_id, "cutoff": cutoff}
    )

    streak = await database.fetch_one(
        "SELECT * FROM streaks WHERE employee_id = :eid AND company_id = :cid", {"eid": employee_id, "cid": company_id}
    )

    bonuses = await database.fetch_all(
        "SELECT * FROM bonus_records WHERE employee_id = :eid AND company_id = :cid", {"eid": employee_id, "cid": company_id}
    )

    geofences = await database.fetch_all(
        """
        SELECT g.* FROM geofences g
        JOIN employee_geofences eg ON g.id = eg.geofence_id
        WHERE eg.employee_id = :eid AND g.company_id = :cid
        """,
        {"eid": employee_id, "cid": company_id}
    )

    export_data = {
        "export_date": datetime.now().isoformat(),
        "jurisdiction": "Uruguay — Ley 18.331 (ARCO+)",
        "employee": emp_data,
        "schedules": [dict(s) for s in schedules],
        "attendance_logs": [{**dict(log), "photo_path": "PRESENT" if log.get("photo_path") else None} for log in logs],
        "streak": dict(streak) if streak else None,
        "bonus_records": [dict(b) for b in bonuses],
        "geofence_assignments": [dict(g) for g in geofences],
    }

    json_bytes = json.dumps(export_data, indent=2, ensure_ascii=False, default=str).encode("utf-8")

    return StreamingResponse(
        iter([json_bytes]),
        media_type="application/json",
        headers={
            "Content-Disposition": f'attachment; filename="mis_datos_{employee_id}.json"',
            "Content-Length": str(len(json_bytes))
        }
    )


@router.get("/export-csv")
async def export_attendance_csv(current_user=Depends(get_current_user)):
    employee_id = str(current_user["id"])
    company_id = str(current_user["company_id"])
    logs = await database.fetch_all(
        """
        SELECT type, timestamp, status, latitude, longitude, streak_day
        FROM attendance_logs
        WHERE employee_id = :eid AND company_id = :cid
        ORDER BY timestamp DESC
        LIMIT 500
        """,
        {"eid": employee_id, "cid": company_id}
    )

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Tipo", "Fecha/Hora", "Estado", "Latitud", "Longitud", "Día de racha"])

    type_labels = {"check_in": "Entrada", "break_start": "Inicio descanso", "break_end": "Fin descanso", "check_out": "Salida"}
    status_labels = {"on_time": "En hora", "late": "Tarde", "warning": "Advertencia"}

    for log in logs:
        writer.writerow([
            type_labels.get(log["type"], log["type"]),
            str(log["timestamp"]),
            status_labels.get(log["status"], log["status"]),
            log["latitude"] or "",
            log["longitude"] or "",
            log["streak_day"] or 0,
        ])

    csv_bytes = output.getvalue().encode("utf-8")

    return StreamingResponse(
        iter([csv_bytes]),
        media_type="text/csv",
        headers={
            "Content-Disposition": f'attachment; filename="asistencia_{employee_id}.csv"',
            "Content-Length": str(len(csv_bytes))
        }
    )


@router.post("/delete-face-photo")
async def delete_face_photo(current_user=Depends(get_current_user)):
    employee_id = str(current_user["id"])
    company_id = str(current_user["company_id"])

    emp = await database.fetch_one(
        "SELECT face_reference_path FROM employees WHERE id = :eid AND company_id = :cid",
        {"eid": employee_id, "cid": company_id}
    )

    if emp and emp["face_reference_path"]:
        path = emp["face_reference_path"]
        if os.path.exists(path):
            try:
                os.remove(path)
            except Exception:
                pass

    await database.execute(
        "UPDATE employees SET face_reference_path = NULL WHERE id = :eid AND company_id = :cid",
        {"eid": employee_id, "cid": company_id}
    )

    return {"message": "Foto de referencia facial eliminada correctamente"}


@router.post("/request-deletion")
async def request_data_deletion(
    req: DataDeletionRequest,
    current_user=Depends(get_current_user)
):
    employee_id = str(current_user["id"])
    company_id = str(current_user["company_id"])

    if req.delete_face_photo:
        emp = await database.fetch_one(
            "SELECT face_reference_path FROM employees WHERE id = :eid AND company_id = :cid",
            {"eid": employee_id, "cid": company_id}
        )
        if emp and emp["face_reference_path"]:
            path = emp["face_reference_path"]
            if os.path.exists(path):
                try:
                    os.remove(path)
                except Exception:
                    pass
            await database.execute(
                "UPDATE employees SET face_reference_path = NULL WHERE id = :eid AND company_id = :cid",
                {"eid": employee_id, "cid": company_id}
            )

    return {
        "message": "Solicitud de eliminación procesada",
        "actions_taken": {
            "face_photo_deleted": req.delete_face_photo,
            "attendance_logs_deleted": False,
        },
        "note": "Los registros de asistencia se conservan por obligación legal (Ley 18.331, Art. 10)."
    }


@router.get("/summary")
async def get_data_summary(current_user=Depends(get_current_user)):
    employee_id = str(current_user["id"])
    company_id = str(current_user["company_id"])

    emp = await database.fetch_one(
        "SELECT face_reference_path, created_at FROM employees WHERE id = :eid AND company_id = :cid",
        {"eid": employee_id, "cid": company_id}
    )

    log_count = await database.fetch_one(
        "SELECT COUNT(*) as cnt FROM attendance_logs WHERE employee_id = :eid AND company_id = :cid",
        {"eid": employee_id, "cid": company_id}
    )

    streak = await database.fetch_one(
        "SELECT current_streak FROM streaks WHERE employee_id = :eid AND company_id = :cid",
        {"eid": employee_id, "cid": company_id}
    )

    geofence_count = await database.fetch_one(
        """
        SELECT COUNT(*) as cnt FROM employee_geofences eg
        JOIN geofences g ON eg.geofence_id = g.id
        WHERE eg.employee_id = :eid AND g.company_id = :cid
        """,
        {"eid": employee_id, "cid": company_id}
    )

    return {
        "employee_id": employee_id,
        "registered_since": emp["created_at"] if emp else None,
        "data_held": {
            "face_reference_photo": bool(emp and emp["face_reference_path"]),
            "attendance_log_count": log_count["cnt"] if log_count else 0,
            "current_streak": streak["current_streak"] if streak else 0,
            "geofence_assignments": geofence_count["cnt"] if geofence_count else 0,
        },
        "retention_policy": {
            "verification_photos": "90 días",
            "face_reference_photo": "Relación laboral + 30 días",
            "attendance_logs": "2 años",
        }
    }
