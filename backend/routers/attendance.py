import logging
import os
import uuid
import math
from datetime import datetime, date, timedelta, timezone
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

# Maximum accepted clock drift between client device and server (minutes)
MAX_DEVICE_CLOCK_DRIFT_MINUTES = 10
# Maximum accepted PAST drift (offline queue delay) before falling back to
# server time with the late_synced flag (minutes)
MAX_PAST_DRIFT_MINUTES = 30
# Maximum photo upload size (bytes)
MAX_PHOTO_BYTES = 10 * 1024 * 1024


async def _read_upload_limited(upload: UploadFile, max_bytes: int = MAX_PHOTO_BYTES) -> bytes:
    """
    Read an upload in chunks, aborting as soon as the size limit is exceeded.
    Prevents a single oversized request from exhausting server memory.
    """
    chunks = []
    total = 0
    while True:
        chunk = await upload.read(1024 * 512)
        if not chunk:
            break
        total += len(chunk)
        if total > max_bytes:
            raise HTTPException(
                status_code=413,
                detail="La imagen excede el tamaño máximo permitido (10 MB)."
            )
        chunks.append(chunk)
    return b"".join(chunks)


def _resolve_mark_timestamp(device_timestamp: Optional[str], tz) -> tuple:
    """
    Resolve the authoritative timestamp for a mark.
    Returns (timestamp, late_synced).

    Anti-forgery + offline-queue policy:
      - |drift| <= MAX_DEVICE_CLOCK_DRIFT_MINUTES (either direction):
        normal clock skew → trust the device time.
      - Device time in the PAST by up to MAX_PAST_DRIFT_MINUTES:
        typical offline-queue delay → trust the device time (the mark keeps
        the real time at which it was made).
      - Anything beyond that (far past or any future drift beyond the
        tolerance): manipulation or a very late offline sync → use SERVER
        time and flag late_synced=True so the response/DB record it for
        admin review (the employee cannot backdate punctuality).
    """
    server_now = datetime.now(tz)
    fallback = (server_now.replace(tzinfo=None), False)
    if not device_timestamp:
        return fallback
    try:
        dt_aware = datetime.fromisoformat(device_timestamp.replace("Z", "+00:00"))
        local_dt = dt_aware.astimezone(tz)
        past_drift = server_now - local_dt  # >0 → device is behind the server
        if abs(past_drift) <= timedelta(minutes=MAX_DEVICE_CLOCK_DRIFT_MINUTES):
            return local_dt.replace(tzinfo=None), False
        if timedelta(0) <= past_drift <= timedelta(minutes=MAX_PAST_DRIFT_MINUTES):
            # Offline-queue style delay: keep the device (real) time
            return local_dt.replace(tzinfo=None), False
        logger.warning(
            "[attendance] device_timestamp sustituido por hora del servidor (desvío %s, futuro=%s): %s",
            abs(past_drift), past_drift < timedelta(0), device_timestamp
        )
        return server_now.replace(tzinfo=None), True
    except Exception:
        logger.warning("[attendance] Device timestamp parse failed: %s", device_timestamp)
        return fallback


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
        logger.error("[Attendance Router] Fallo al recuperar configuración de verificación facial: %s", e)
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


def _parse_optional_float(val: Optional[object]) -> Optional[float]:
    if val is None:
        return None
    val_str = str(val).strip()
    if not val_str or val_str.lower() in ("none", "null", "undefined"):
        return None
    try:
        return float(val_str)
    except (ValueError, TypeError):
        return None


@router.post("/mark", response_model=AttendanceResponse)
async def mark_attendance(
    latitude: Optional[str] = Form(None),
    longitude: Optional[str] = Form(None),
    gps_accuracy: Optional[str] = Form(None),
    device_timestamp: Optional[str] = Form(None),
    photo: Optional[UploadFile] = File(None),
    current_user=Depends(get_current_user)
):
    employee_id = str(current_user["id"])
    company_id = str(current_user["company_id"])

    lat_val = _parse_optional_float(latitude)
    lng_val = _parse_optional_float(longitude)
    acc_val = _parse_optional_float(gps_accuracy)

    if lat_val is None or lng_val is None:
        return AttendanceResponse(
            status="warning",
            alert_type="yellow",
            title="GPS no disponible",
            message="No se pudo obtener su ubicación precisa. Active el GPS o conceda los permisos de ubicación e intente nuevamente."
        )

    # Reject GPS readings with excessively poor accuracy
    if acc_val is not None and acc_val > settings.MAX_GPS_ACCURACY_METERS:
        return AttendanceResponse(
            status="warning",
            alert_type="yellow",
            title="Precisión GPS insuficiente",
            message=f"La precisión GPS es muy baja ({acc_val:.0f}m). Acérquese a una ventana y vuelva a intentar."
        )

    tz = ZoneInfo(settings.TIMEZONE)
    timestamp, late_synced = _resolve_mark_timestamp(device_timestamp, tz)

    # Best-effort schedule lookup for the geofence check (no lock held here).
    # The authoritative mark_type is recomputed atomically inside the
    # transaction right before the INSERT.
    schedule = await get_employee_schedule(employee_id, company_id, timestamp.weekday(), current_time=timestamp.time())

    geofence_id = schedule.get("geofence_id") if schedule else None

    # If the active schedule explicitly has no geofence restriction, all locations are permitted
    if schedule and geofence_id is None:
        in_geofence = True
    else:
        in_geofence = await check_geofence(employee_id, company_id, lat_val, lng_val, geofence_id=geofence_id)
    if not in_geofence:
        gf_name = "el lugar de trabajo asignado"
        if geofence_id:
            try:
                # Defense-in-depth: filter by tenant even though geofence_id
                # comes from a company-scoped schedule row
                gf_row = await database.fetch_one(
                    "SELECT name FROM geofences WHERE id = :gid AND company_id = :cid",
                    {"gid": geofence_id, "cid": company_id}
                )
                if gf_row:
                    gf_name = f"'{gf_row['name']}'"
            except Exception as e:
                logger.warning("[attendance] Fallo al recuperar nombre de geocerca: %s", e)
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
        # Chunked read — rejects oversized uploads before buffering them in RAM
        content = await _read_upload_limited(photo, MAX_PHOTO_BYTES)
        filename = f"{company_id}_{employee_id}_{uuid.uuid4().hex}.{ext}"
        photo_path = os.path.join(settings.PHOTOS_PATH, filename)
        try:
            os.makedirs(settings.PHOTOS_PATH, exist_ok=True)
            with open(photo_path, "wb") as f:
                f.write(content)
        except (PermissionError, OSError) as perm_err:
            # Fail gracefully: photo is optional evidence. If face verification
            # is required, the check below rejects the mark because photo_path
            # stays None (fail-closed).
            logger.error("[attendance] No se pudo guardar la foto en %s: %s. La marcación continúa sin foto.", settings.PHOTOS_PATH, perm_err)
            photo_path = None

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

    # SECURITY: if the company requires face verification, the selfie photo is
    # MANDATORY. Omitting the file must never bypass the biometric check.
    if face_required and not photo_path:
        return AttendanceResponse(
            status="warning",
            alert_type="red",
            title="Verificación facial requerida",
            message="Debes capturar y enviar una selfie para verificar tu identidad. Inténtalo nuevamente con la cámara activada.",
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

    # ── Atomic evaluation + insert (advisory lock held for the whole
    # sequence): prevents duplicate marks and lost streak updates under
    # concurrent requests from the same employee.
    async with database.transaction():
        await database.fetch_one(
            "SELECT pg_advisory_xact_lock(hashtext(:lock_key))",
            {"lock_key": f"attendance_mark:{employee_id}"}
        )
        mark_type = await get_next_mark_type(employee_id, company_id, current_dt=timestamp)
        if mark_type == "already_completed":
            # Remove the already-saved photo so it does not become an orphan
            if photo_path and os.path.exists(photo_path):
                try:
                    os.remove(photo_path)
                except OSError:
                    pass
            return AttendanceResponse(
                status="warning",
                alert_type="yellow",
                title="Jornada completa",
                message="Ya has completado todos los registros del día."
            )
        feedback = await evaluate_mark(employee_id, company_id, mark_type, timestamp)
        sched_id = str(schedule["id"]) if schedule and "id" in schedule else None

        # Late-sync annotation: the device timestamp was not trusted and the
        # mark was registered with the server time (offline sync too delayed
        # or clock manipulation). Surface it to the employee and store it.
        if late_synced:
            feedback["late_synced"] = True
            feedback["alert_type"] = "yellow" if feedback.get("alert_type") != "red" else "red"
            feedback["title"] = f"{feedback.get('title', 'Marcación')} — sync tardío"
            feedback["message"] = (
                (feedback.get("message") or "")
                + " La hora de tu dispositivo no era confiable; se registró con la hora del servidor."
            )

        try:
            log_id = await database.execute(
                """
                INSERT INTO attendance_logs
                (company_id, employee_id, schedule_id, type, timestamp, latitude, longitude, gps_accuracy, photo_path, status, early_minutes, streak_day, synced_late)
                VALUES (:cid, :eid, :sched_id, :type, :ts, :lat, :lng, :acc, :photo, :status, :early_min, :streak, :late_sync)
                RETURNING id
                """,
                {
                    "cid": company_id,
                    "eid": employee_id,
                    "sched_id": sched_id,
                    "type": mark_type,
                    "ts": timestamp,
                    "lat": lat_val,
                    "lng": lng_val,
                    "acc": acc_val,
                    "photo": photo_path,
                    "status": feedback["status"],
                    "early_min": feedback.get("early_minutes", 0),
                    "streak": feedback.get("streak") or 0,
                    "late_sync": late_synced,
                }
            )
        except Exception as db_err:
            logger.error("[attendance] Fallo al insertar registro de asistencia en BD: %s", db_err, exc_info=True)
            raise HTTPException(
                status_code=500,
                detail=f"Error al registrar la marcación en base de datos: {str(db_err)}"
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

    feedback["next_action"] = await get_next_mark_type(employee_id, company_id, current_dt=timestamp)
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
    tz = ZoneInfo(settings.TIMEZONE)
    now_local = datetime.now(tz)
    employee_id = str(current_user["id"])
    company_id = str(current_user["company_id"])
    today = now_local.date()
    now_time = now_local.time()
    weekday = now_local.weekday()

    logs = await database.fetch_all(
        """
        SELECT id, type, timestamp, status, latitude, longitude, early_minutes
        FROM attendance_logs
        WHERE employee_id = :eid AND company_id = :cid AND DATE(timestamp) = :today
        ORDER BY timestamp ASC
        """,
        {"eid": employee_id, "cid": company_id, "today": today}
    )
    next_action = await get_next_mark_type(employee_id, company_id, current_dt=now_local.replace(tzinfo=None))
    active_sched = await get_employee_schedule(employee_id, company_id, weekday, current_time=now_time)

    geofence_name = "Ubicación General"
    if active_sched and active_sched.get("geofence_id"):
        try:
            gf = await database.fetch_one(
                "SELECT name FROM geofences WHERE id = :gid AND company_id = :cid",
                {"gid": active_sched["geofence_id"], "cid": company_id},
            )
            if gf:
                geofence_name = gf["name"]
        except Exception as e:
            logger.warning("[attendance] Fallo al recuperar nombre de geocerca activa: %s", e)

    streak_row = await database.fetch_one(
        "SELECT current_streak FROM streaks WHERE employee_id = :eid AND company_id = :cid",
        {"eid": employee_id, "cid": company_id}
    )
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
