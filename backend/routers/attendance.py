import logging
import os
import uuid
import math
from datetime import datetime, date
from zoneinfo import ZoneInfo
from fastapi import APIRouter, UploadFile, File, Form, Depends, HTTPException
from typing import Optional
from schemas import AttendanceResponse
from auth import get_current_user
from database import database
from rules_engine import get_next_mark_type, evaluate_mark, get_employee_schedule
from config import settings
from agent_controller import notify_checkin, notify_checkout, notify_break, notify_late

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/attendance", tags=["attendance"])


async def _check_face_verification_required(employee_id: str, company_id: str) -> tuple:
    """
    Returns (is_required, provider, error_message).
    """
    if not settings.FACE_VERIFICATION_ENABLED:
        return False, "", ""

    try:
        config = await database.fetch_one(
            "SELECT face_verification_enabled, face_verification_provider FROM company_config WHERE company_id = :cid",
            {"cid": company_id}
        )
    except Exception as e:
        print(f"[Attendance Router Error] Fallo al recuperar configuración de verificación facial: {e}")
        config = None

    if not config or not config.get("face_verification_enabled", False):
        return False, "", ""

    provider = config.get("face_verification_provider", settings.FACE_VERIFICATION_PROVIDER)

    emp = await database.fetch_one(
        "SELECT face_reference_path FROM employees WHERE id = :eid AND company_id = :cid",
        {"eid": employee_id, "cid": company_id}
    )
    if not emp or not emp["face_reference_path"]:
        return True, provider, "Verificación facial requerida pero no tienes un rostro registrado. Contacta a tu administrador."

    if not os.path.exists(emp["face_reference_path"]):
        return True, provider, "Foto de referencia no encontrada. Contacta a tu administrador."

    return True, provider, ""


async def check_geofence(employee_id: str, company_id: str, lat: float, lng: float, geofence_id: Optional[str] = None) -> bool:
    """Returns True if inside the specified geofence, or inside any assigned geofence if not specified"""
    if geofence_id:
        # Check only the specific geofence
        geofences = await database.fetch_all(
            "SELECT * FROM geofences WHERE id = :gid AND company_id = :cid",
            {"gid": geofence_id, "cid": company_id}
        )
    else:
        # Fallback to checking all geofences assigned to this employee
        geofences = await database.fetch_all(
            """
            SELECT g.* FROM geofences g
            JOIN employee_geofences eg ON g.id = eg.geofence_id
            WHERE eg.employee_id = :eid AND g.company_id = :cid
            """,
            {"eid": employee_id, "cid": company_id}
        )
    if not geofences:
        return True

    for gf in geofences:
        phi1 = math.radians(lat)
        phi2 = math.radians(float(gf["latitude"]))
        dphi = math.radians(float(gf["latitude"]) - lat)
        dlambda = math.radians(float(gf["longitude"]) - lng)
        R = 6371000
        a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
        dist = 2 * R * math.asin(math.sqrt(a))
        if dist <= gf["radius_meters"]:
            return True
    return False


@router.post("/mark", response_model=AttendanceResponse)
async def mark_attendance(
    latitude: Optional[float] = Form(None),
    longitude: Optional[float] = Form(None),
    gps_accuracy: Optional[float] = Form(None),
    device_timestamp: Optional[str] = Form(None),
    photo: Optional[UploadFile] = File(None),
    current_user=Depends(get_current_user)
):
    employee_id = str(current_user["id"])
    company_id = str(current_user["company_id"])

    if latitude is None or longitude is None:
        return AttendanceResponse(
            status="warning",
            alert_type="yellow",
            title="GPS no disponible",
            message="No se pudo obtener su ubicación precisa. Active el GPS e intente nuevamente."
        )

    # Reject GPS readings with excessively poor accuracy
    if gps_accuracy is not None and gps_accuracy > settings.MAX_GPS_ACCURACY_METERS:
        return AttendanceResponse(
            status="warning",
            alert_type="yellow",
            title="Precisión GPS insuficiente",
            message=f"La precisión GPS es muy baja ({gps_accuracy:.0f}m). Acérquese a una ventana y vuelva a intentar."
        )

    tz = ZoneInfo(settings.TIMEZONE)
    try:
        if device_timestamp:
            dt_aware = datetime.fromisoformat(device_timestamp.replace("Z", "+00:00"))
            timestamp = dt_aware.astimezone(tz).replace(tzinfo=None)
        else:
            timestamp = datetime.now(tz).replace(tzinfo=None)
    except Exception:
        logger.warning("[attendance] Device timestamp parse failed: %s", device_timestamp)
        timestamp = datetime.now(tz).replace(tzinfo=None)

    mark_type = await get_next_mark_type(employee_id, company_id)
    if mark_type == "already_completed":
        return AttendanceResponse(
            status="warning",
            alert_type="yellow",
            title="Jornada completa",
            message="Ya has completado todos los registros del día."
        )

    schedule = await get_employee_schedule(employee_id, company_id, timestamp.weekday(), current_time=timestamp.time())
    geofence_id = schedule.get("geofence_id") if schedule else None

    in_geofence = await check_geofence(employee_id, company_id, latitude, longitude, geofence_id=geofence_id)
    if not in_geofence:
        gf_name = "el lugar de trabajo asignado"
        if geofence_id:
            try:
                gf_row = await database.fetch_one("SELECT name FROM geofences WHERE id = :gid", {"gid": geofence_id})
                if gf_row:
                    gf_name = f"'{gf_row['name']}'"
            except Exception:
                pass
        slot_label = f" ({schedule.get('slot_name')})" if schedule and schedule.get('slot_name') else ""
        return AttendanceResponse(
            status="warning",
            alert_type="yellow",
            title="Fuera de zona asignada",
            message=f"Tu ubicación no corresponde a {gf_name}{slot_label} requerido para este horario."
        )

    photo_path = None
    if photo:
        # Validate extension BEFORE writing to disk
        ext = photo.filename.split(".")[-1].lower() if photo.filename else "jpg"
        if ext not in ("png", "jpg", "jpeg", "webp"):
            raise HTTPException(status_code=400, detail="Formato de imagen no permitido. Use PNG, JPG o WebP.")
        content = await photo.read()
        if len(content) > 10 * 1024 * 1024:  # 10 MB limit (H8)
            raise HTTPException(
                status_code=413,
                detail="La imagen excede el tamaño máximo permitido (10 MB)."
            )
        filename = f"{company_id}_{employee_id}_{uuid.uuid4().hex}.{ext}"
        photo_path = os.path.join(settings.PHOTOS_PATH, filename)
        os.makedirs(settings.PHOTOS_PATH, exist_ok=True)
        with open(photo_path, "wb") as f:
            f.write(content)

    face_required, face_provider, face_error = await _check_face_verification_required(employee_id, company_id)
    face_verified = None
    face_confidence = None

    if face_required and face_error:
        if photo_path and os.path.exists(photo_path):
            os.remove(photo_path)
        return AttendanceResponse(
            status="warning",
            alert_type="yellow",
            title="Verificación facial requerida",
            message=face_error,
            face_verified=False
        )

    if face_required and photo_path:
        from face_service import verify_face
        emp = await database.fetch_one(
            "SELECT face_reference_path FROM employees WHERE id = :eid AND company_id = :cid",
            {"eid": employee_id, "cid": company_id}
        )
        reference_path = emp["face_reference_path"] if emp else None

        if reference_path:
            result = await verify_face(
                selfie_path=photo_path,
                reference_path=reference_path,
                provider=face_provider,
                threshold=settings.FACE_VERIFICATION_THRESHOLD
            )
            face_verified = result["verified"]
            face_confidence = result["confidence"]

            if not face_verified:
                if os.path.exists(photo_path):
                    os.remove(photo_path)
                return AttendanceResponse(
                    status="warning",
                    alert_type="red",
                    title="No se pudo verificar tu identidad",
                    message=result.get("error", "Intenta de nuevo con mejor iluminación."),
                    face_verified=False,
                    face_confidence=face_confidence
                )

    feedback = await evaluate_mark(employee_id, company_id, mark_type, timestamp)
    sched_id = str(schedule["id"]) if schedule and "id" in schedule else None

    log_id = await database.execute(
        """
        INSERT INTO attendance_logs
        (company_id, employee_id, schedule_id, type, timestamp, latitude, longitude, gps_accuracy, photo_path, status, early_minutes, streak_day)
        VALUES (:cid, :eid, :sched_id, :type, :ts, :lat, :lng, :acc, :photo, :status, :early_min, :streak)
        RETURNING id
        """,
        {
            "cid": company_id,
            "eid": employee_id,
            "sched_id": sched_id,
            "type": mark_type,
            "ts": timestamp,
            "lat": latitude,
            "lng": longitude,
            "acc": gps_accuracy,
            "photo": photo_path,
            "status": feedback["status"],
            "early_min": feedback.get("early_minutes", 0),
            "streak": feedback.get("streak") or 0
        }
    )

    try:
        ts_str = timestamp.strftime("%H:%M")
        geofence_name = feedback.get("geofence_name", "Ubicación General")
        if mark_type == "check_in":
            await notify_checkin(employee_id, company_id, feedback["status"], ts_str, geofence_name=geofence_name)
            if feedback["status"] == "late":
                minutes = feedback.get("minutes_late", 0)
                await notify_late(employee_id, company_id, minutes, geofence_name=geofence_name)
        elif mark_type == "check_out":
            await notify_checkout(employee_id, company_id, ts_str, geofence_name=geofence_name)
        elif mark_type in ("break_start", "break_end"):
            await notify_break(employee_id, company_id, mark_type, ts_str, geofence_name=geofence_name, status=feedback.get("status", "on_time"), minutes_late=feedback.get("minutes_late", 0))
    except Exception as ex:
        logger.warning("[attendance] Notificación fallida: %s", ex)

    feedback["next_action"] = await get_next_mark_type(employee_id, company_id)
    feedback["log_id"] = str(log_id)

    if face_verified is not None:
        feedback["face_verified"] = face_verified
        feedback["face_confidence"] = face_confidence
        if face_verified and mark_type == "check_in":
            feedback["title"] = "✅ Identidad verificada"
            feedback["message"] = f"Rostro verificado ({face_confidence:.0%} confianza). {feedback.get('message', '')}"

    return AttendanceResponse(**feedback)


@router.get("/today")
async def get_today_logs(current_user=Depends(get_current_user)):
    from datetime import date
    employee_id = str(current_user["id"])
    company_id = str(current_user["company_id"])
    today = date.today()
    now_time = datetime.now().time()
    weekday = datetime.now().weekday()

    logs = await database.fetch_all(
        """
        SELECT id, type, timestamp, status, latitude, longitude, early_minutes
        FROM attendance_logs
        WHERE employee_id = :eid AND company_id = :cid AND DATE(timestamp) = :today
        ORDER BY timestamp ASC
        """,
        {"eid": employee_id, "cid": company_id, "today": today}
    )
    next_action = await get_next_mark_type(employee_id, company_id)
    active_sched = await get_employee_schedule(employee_id, company_id, weekday, current_time=now_time)

    geofence_name = "Ubicación General"
    if active_sched and active_sched.get("geofence_id"):
        try:
            gf = await database.fetch_one(
                "SELECT name FROM geofences WHERE id = :gid",
                {"gid": active_sched["geofence_id"]},
            )
            if gf:
                geofence_name = gf["name"]
        except Exception:
            pass

    streak_row = await database.fetch_one(
        "SELECT current_streak FROM streaks WHERE employee_id = :eid AND company_id = :cid",
        {"eid": employee_id, "cid": company_id}
    )
    from config import settings
    streak = streak_row["current_streak"] if streak_row else 0
    return {
        "logs": [dict(r) for r in logs],
        "next_action": next_action,
        "streak": streak,
        "days_to_bonus": max(0, settings.BONUS_STREAK_DAYS - streak),
        "schedule": {
            "slot_name": active_sched.get("slot_name") or "Turno Regular",
            "start_time": str(active_sched.get("start_time", "")) if active_sched else None,
            "end_time": str(active_sched.get("end_time", "")) if active_sched else None,
            "break_mode": active_sched.get("break_mode", "flexible") if active_sched else "flexible",
            "break_duration_minutes": active_sched.get("break_duration_minutes", 45) if active_sched else 45,
            "geofence_name": geofence_name,
        } if active_sched else None
    }
