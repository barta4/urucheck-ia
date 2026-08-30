import logging
from datetime import datetime, date, timedelta, time as time_type
from typing import Optional, TypedDict
import math
from database import database
from config import settings

logger = logging.getLogger(__name__)


# ─── TypedDicts for evaluate_mark return value ────────────────────────────────

class AttendanceResult(TypedDict, total=False):
    status: str
    alert_type: str
    title: str
    message: str
    minutes_late: int
    early_departure: bool
    early_minutes: int
    slot_name: str
    expected_end_time: str
    streak: Optional[int]
    days_to_bonus: Optional[int]
    streak_message: str
    geofence_name: str
    next_action: str
    log_id: str
    face_verified: bool
    face_confidence: float


# ─── Helpers ──────────────────────────────────────────────────────────────────

def ensure_time(t) -> Optional[time_type]:
    if t is None:
        return None
    if isinstance(t, time_type):
        return t
    if isinstance(t, str):
        try:
            return datetime.strptime(t, "%H:%M:%S").time()
        except ValueError:
            try:
                return datetime.strptime(t, "%H:%M").time()
            except ValueError:
                pass
    if isinstance(t, datetime):
        return t.time()
    return None


async def get_employee_schedule(
    employee_id: str,
    company_id: str,
    weekday: int,
    current_time: Optional[time_type] = None,
) -> Optional[dict]:
    """
    Return the schedule for an employee on a given weekday.

    weekday: 0=Monday … 6=Sunday (stored in DB as 1-7).
    If multiple schedules exist for the day:
      1. First checks if current_time falls within [start_time - 30m, end_time + 30m].
      2. If not inside any active window, selects the schedule with start_time closest to current_time.
    """
    rows = await database.fetch_all(
        """
        SELECT id, employee_id, company_id, day_of_week,
               start_time, end_time, slot_name, tolerance_minutes,
               break_mode, break_start_time, break_end_time, break_duration_minutes,
               geofence_id
        FROM schedules
        WHERE employee_id = :eid AND company_id = :cid AND :day = ANY(day_of_week)
        ORDER BY start_time ASC
        """,
        {"eid": employee_id, "cid": company_id, "day": weekday + 1},
    )
    if not rows:
        return None
    if len(rows) == 1 or current_time is None:
        return dict(rows[0])

    current_minutes = current_time.hour * 60 + current_time.minute
    
    # 1. Look for active window
    for row in rows:
        s_start = ensure_time(row["start_time"])
        s_end = ensure_time(row["end_time"])
        if not s_start or not s_end:
            continue
        start_min = s_start.hour * 60 + s_start.minute - 30
        end_min = s_end.hour * 60 + s_end.minute + 30
        if start_min <= current_minutes <= end_min:
            return dict(row)

    # 2. Fallback: closest start time
    best_schedule = None
    min_diff = None
    for row in rows:
        sched_time = ensure_time(row["start_time"])
        if sched_time is None:
            continue
        sched_minutes = sched_time.hour * 60 + sched_time.minute
        diff = abs(current_minutes - sched_minutes)
        if min_diff is None or diff < min_diff:
            min_diff = diff
            best_schedule = dict(row)

    return best_schedule or dict(rows[0])


async def get_or_create_streak(employee_id: str, company_id: str) -> dict:
    row = await database.fetch_one(
        "SELECT current_streak, last_on_time_date FROM streaks WHERE employee_id = :eid AND company_id = :cid",
        {"eid": employee_id, "cid": company_id},
    )
    if not row:
        await database.execute(
            "INSERT INTO streaks (company_id, employee_id) VALUES (:cid, :eid) ON CONFLICT DO NOTHING",
            {"cid": company_id, "eid": employee_id},
        )
        return {"current_streak": 0, "last_on_time_date": None}
    return dict(row)


async def update_streak(employee_id: str, company_id: str, is_on_time: bool, today: date) -> int:
    streak = await get_or_create_streak(employee_id, company_id)
    last_date = streak["last_on_time_date"]
    current = streak["current_streak"]

    if is_on_time:
        yesterday = today - timedelta(days=1)
        if last_date is None or last_date == yesterday:
            new_streak = current + 1
        elif last_date == today:
            new_streak = current
        else:
            new_streak = 1

        await database.execute(
            """
            UPDATE streaks SET current_streak = :streak, last_on_time_date = :today, updated_at = NOW()
            WHERE employee_id = :eid AND company_id = :cid
            """,
            {"streak": new_streak, "today": today, "eid": employee_id, "cid": company_id},
        )
        return new_streak
    else:
        await database.execute(
            "UPDATE streaks SET current_streak = 0, updated_at = NOW() WHERE employee_id = :eid AND company_id = :cid",
            {"eid": employee_id, "cid": company_id},
        )
        return 0


async def get_next_mark_type(employee_id: str, company_id: str) -> str:
    """
    Determine the next expected attendance action for an employee.
    Supports multi-slot days and break_mode ('none', 'flexible', 'fixed').
    """
    today = date.today()
    now_time = datetime.now().time()
    weekday = datetime.now().weekday()

    logs = await database.fetch_all(
        """
        SELECT type, timestamp FROM attendance_logs
        WHERE employee_id = :eid AND company_id = :cid AND DATE(timestamp) = :today
        ORDER BY timestamp ASC
        """,
        {"eid": employee_id, "cid": company_id, "today": today},
    )

    # Fetch all schedules for today
    day_schedules = await database.fetch_all(
        """
        SELECT * FROM schedules
        WHERE employee_id = :eid AND company_id = :cid AND :day = ANY(day_of_week)
        ORDER BY start_time ASC
        """,
        {"eid": employee_id, "cid": company_id, "day": weekday + 1},
    )

    if not logs:
        return "check_in"

    last_type = logs[-1]["type"]

    # If last mark is check_in:
    if last_type == "check_in":
        # Check current schedule break_mode
        active_sched = await get_employee_schedule(employee_id, company_id, weekday, current_time=now_time)
        if active_sched and active_sched.get("break_mode") == "none":
            return "check_out"
        return "break_start"

    # If last mark is break_start:
    if last_type == "break_start":
        return "break_end"

    # If last mark is break_end:
    if last_type == "break_end":
        return "check_out"

    # If last mark is check_out:
    if last_type == "check_out":
        check_out_count = sum(1 for log in logs if log["type"] == "check_out")
        total_schedules_count = len(day_schedules)

        # If there are more shifts scheduled for today that haven't been completed
        if total_schedules_count > check_out_count:
            return "check_in"
        return "already_completed"

    return "check_in"


async def evaluate_mark(
    employee_id: str,
    company_id: str,
    mark_type: str,
    timestamp: datetime,
) -> AttendanceResult:
    """
    Core attendance business logic.
    Validates punctuality, break excesses, anti-fraud check-out intervals, and early departures.
    """
    today = timestamp.date()
    weekday = timestamp.weekday()

    # Determine closest schedule
    schedule = await get_employee_schedule(employee_id, company_id, weekday, current_time=timestamp.time())

    # Get geofence name
    geofence_name = "Ubicación General"
    if schedule and schedule.get("geofence_id"):
        try:
            gf = await database.fetch_one(
                "SELECT name FROM geofences WHERE id = :gid",
                {"gid": schedule["geofence_id"]},
            )
            if gf:
                geofence_name = gf["name"]
        except Exception:
            pass

    slot_name = (schedule.get("slot_name") if schedule else None) or "Turno Regular"

    # ─── BREAK_START EVALUATION ───────────────────────────────────────────────
    if mark_type == "break_start":
        if schedule and schedule.get("break_mode") == "fixed" and schedule.get("break_start_time"):
            tolerance = timedelta(minutes=schedule.get("tolerance_minutes", 5))
            b_start = ensure_time(schedule["break_start_time"])
            if b_start:
                scheduled_start = datetime.combine(today, b_start)
                deadline = scheduled_start + tolerance
                if timestamp > deadline:
                    minutes_late = max(0, int((timestamp - deadline).total_seconds() / 60))
                    return {
                        "status": "warning",
                        "alert_type": "yellow",
                        "title": "Salida a descanso tardía",
                        "message": f"Iniciaste tu descanso {minutes_late} minuto(s) tarde respecto al horario fijo ({b_start.strftime('%H:%M')}).",
                        "minutes_late": minutes_late,
                        "slot_name": slot_name,
                        "geofence_name": geofence_name,
                    }
        return {
            "status": "on_time",
            "alert_type": "green",
            "title": "Inicio de descanso",
            "message": "Tu descanso ha comenzado. ¡Descansa bien!",
            "slot_name": slot_name,
            "geofence_name": geofence_name,
        }

    # ─── BREAK_END EVALUATION ─────────────────────────────────────────────────
    if mark_type == "break_end":
        tolerance_min = schedule.get("tolerance_minutes", 5) if schedule else 5
        tolerance = timedelta(minutes=tolerance_min)

        # Mode: Fixed break hours
        if schedule and schedule.get("break_mode") == "fixed" and schedule.get("break_end_time"):
            b_end = ensure_time(schedule["break_end_time"])
            if b_end:
                scheduled_end = datetime.combine(today, b_end)
                deadline = scheduled_end + tolerance
                if timestamp > deadline:
                    minutes_late = max(0, int((timestamp - deadline).total_seconds() / 60))
                    return {
                        "status": "late",
                        "alert_type": "red",
                        "title": "Regreso de descanso tardío",
                        "message": f"Regresaste de tu descanso {minutes_late} minuto(s) tarde respecto al horario programado ({b_end.strftime('%H:%M')}).",
                        "minutes_late": minutes_late,
                        "slot_name": slot_name,
                        "geofence_name": geofence_name,
                    }

        # Mode: Flexible duration
        if schedule and schedule.get("break_mode") == "flexible":
            allowed_duration = schedule.get("break_duration_minutes") or 45
            # Find the latest break_start today
            last_start = await database.fetch_one(
                """
                SELECT timestamp FROM attendance_logs
                WHERE employee_id = :eid AND company_id = :cid AND type = 'break_start' AND DATE(timestamp) = :today
                ORDER BY timestamp DESC LIMIT 1
                """,
                {"eid": employee_id, "cid": company_id, "today": today},
            )
            if last_start:
                actual_duration = max(0, int((timestamp - last_start["timestamp"]).total_seconds() / 60))
                max_allowed = allowed_duration + tolerance_min
                if actual_duration > max_allowed:
                    excess_min = actual_duration - allowed_duration
                    return {
                        "status": "warning",
                        "alert_type": "yellow",
                        "title": "Exceso en tiempo de descanso",
                        "message": f"Tu descanso duró {actual_duration} min (máximo permitido: {allowed_duration} min). Excediste por {excess_min} min.",
                        "minutes_late": excess_min,
                        "slot_name": slot_name,
                        "geofence_name": geofence_name,
                    }

        return {
            "status": "on_time",
            "alert_type": "green",
            "title": "Fin de descanso",
            "message": "Bienvenido de vuelta. ¡A continuar con la jornada!",
            "slot_name": slot_name,
            "geofence_name": geofence_name,
        }

    # ─── CHECK_OUT EVALUATION ─────────────────────────────────────────────────
    if mark_type == "check_out":
        # 1. Anti-fraud check: Check time since last check_in
        last_checkin = await database.fetch_one(
            """
            SELECT timestamp FROM attendance_logs
            WHERE employee_id = :eid AND company_id = :cid AND type = 'check_in' AND DATE(timestamp) = :today
            ORDER BY timestamp DESC LIMIT 1
            """,
            {"eid": employee_id, "cid": company_id, "today": today},
        )
        if last_checkin:
            seconds_worked = (timestamp - last_checkin["timestamp"]).total_seconds()
            if seconds_worked < 300:  # < 5 minutes
                return {
                    "status": "warning",
                    "alert_type": "red",
                    "title": "Salida inmediata / prematura",
                    "message": "Marcaste salida a menos de 5 minutos de haber ingresado. Esto queda asentado como salida irregular para revisión de RRHH.",
                    "early_departure": True,
                    "early_minutes": 0,
                    "slot_name": slot_name,
                    "geofence_name": geofence_name,
                }

        # 2. Check scheduled end time
        if schedule:
            s_end = ensure_time(schedule.get("end_time"))
            tolerance_min = schedule.get("tolerance_minutes", 5)
            if s_end:
                scheduled_end = datetime.combine(today, s_end)
                min_departure_time = scheduled_end - timedelta(minutes=tolerance_min)

                if timestamp < min_departure_time:
                    early_seconds = (scheduled_end - timestamp).total_seconds()
                    early_min = max(1, int(early_seconds / 60))
                    hours = early_min // 60
                    mins = early_min % 60
                    time_str = f"{hours}h {mins}m" if hours > 0 else f"{mins} min"

                    return {
                        "status": "warning",
                        "alert_type": "yellow",
                        "title": "Salida anticipada registrada",
                        "message": f"Tu horario de salida es a las {s_end.strftime('%H:%M')}. Te retiras {time_str} antes de finalizar tu turno.",
                        "early_departure": True,
                        "early_minutes": early_min,
                        "expected_end_time": s_end.strftime("%H:%M"),
                        "slot_name": slot_name,
                        "geofence_name": geofence_name,
                    }

        return {
            "status": "on_time",
            "alert_type": "green",
            "title": "Salida registrada",
            "message": f"¡Hasta luego! Jornada de '{slot_name}' completada exitosamente.",
            "early_departure": False,
            "early_minutes": 0,
            "slot_name": slot_name,
            "geofence_name": geofence_name,
        }

    # ─── CHECK_IN EVALUATION ──────────────────────────────────────────────────
    if not schedule:
        return {
            "status": "warning",
            "alert_type": "yellow",
            "title": "Sin horario asignado",
            "message": "No tienes un horario asignado para hoy en esta sucursal. Contacta a tu supervisor.",
            "streak": None,
            "days_to_bonus": None,
            "geofence_name": geofence_name,
            "slot_name": "Sin turno",
        }

    s_start = ensure_time(schedule["start_time"])
    scheduled_start = datetime.combine(today, s_start) if s_start else datetime.combine(today, time_type(9, 0))
    tolerance = timedelta(minutes=schedule.get("tolerance_minutes", 5))
    deadline = scheduled_start + tolerance

    is_on_time = timestamp <= deadline
    minutes_late = max(0, int((timestamp - deadline).total_seconds() / 60))

    streak = await update_streak(employee_id, company_id, is_on_time, today)

    bonus_days = settings.BONUS_STREAK_DAYS
    days_to_bonus = max(0, bonus_days - streak)

    try:
        config_row = await database.fetch_one(
            "SELECT bonus_success_message, bonus_pending_message FROM company_config WHERE company_id = :cid",
            {"cid": company_id},
        )
    except Exception as exc:
        logger.error("[rules_engine] Fallo al recuperar mensajes de bono para empresa %s: %s", company_id, exc)
        config_row = None

    msg_success = config_row["bonus_success_message"] if config_row else "¡Bonus asegurado!"
    msg_pending = config_row["bonus_pending_message"] if config_row else "Faltan {days} días para asegurar tu bono."
    msg_pending_formatted = msg_pending.replace("{days}", str(days_to_bonus))

    if is_on_time:
        return {
            "status": "on_time",
            "alert_type": "green",
            "title": "¡Entrada registrada!",
            "message": f"¡Excelente puntualidad en {slot_name}! Ubicación confirmada.",
            "streak": streak,
            "days_to_bonus": days_to_bonus,
            "streak_message": f"Llevas {streak} día(s) seguido(s). {msg_success if days_to_bonus == 0 else msg_pending_formatted}",
            "geofence_name": geofence_name,
            "slot_name": slot_name,
        }
    else:
        return {
            "status": "late",
            "alert_type": "red",
            "title": "Llegada tarde registrada",
            "message": f"Llegaste {minutes_late} minuto(s) tarde a {slot_name}. Has perdido el bono de puntualidad de este mes. Intenta llegar en hora.",
            "minutes_late": minutes_late,
            "streak": 0,
            "days_to_bonus": bonus_days,
            "streak_message": "La racha de puntualidad se ha reiniciado.",
            "geofence_name": geofence_name,
            "slot_name": slot_name,
        }

