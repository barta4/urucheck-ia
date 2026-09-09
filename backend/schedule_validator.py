import logging
from datetime import time as time_type, datetime
from typing import Optional, List, Dict, Any, Tuple

logger = logging.getLogger(__name__)

DAY_NAMES: Dict[int, str] = {
    1: "Lunes",
    2: "Martes",
    3: "Miércoles",
    4: "Jueves",
    5: "Viernes",
    6: "Sábado",
    7: "Domingo",
}

def normalize_days(days: Any) -> List[int]:
    """
    Normalizes day_of_week inputs into a clean list of integers (1..7).
    Supports list/tuple/set, PostgreSQL array string '{1,2,3}', or JSON '[1,2,3]'.
    """
    if days is None:
        return []
    if isinstance(days, (list, tuple, set)):
        result = []
        for d in days:
            try:
                result.append(int(d))
            except (ValueError, TypeError):
                pass
        return result
    if isinstance(days, str):
        cleaned = days.strip("{}[]")
        if not cleaned:
            return []
        result = []
        for part in cleaned.split(","):
            part = part.strip()
            if part.isdigit():
                result.append(int(part))
        return result
    return []

def time_to_minutes(t: Any) -> int:
    """
    Converts a time, datetime, or time-string ('HH:MM' or 'HH:MM:SS') into total minutes from midnight (0..1439).
    """
    if isinstance(t, str):
        parts = t.split(":")
        if len(parts) >= 2:
            return int(parts[0]) * 60 + int(parts[1])
        raise ValueError(f"Formato de hora inválido: {t}")
    if isinstance(t, time_type):
        return t.hour * 60 + t.minute
    if isinstance(t, datetime):
        return t.hour * 60 + t.minute
    raise ValueError(f"Tipo de dato de hora no soportado: {type(t)}")

def format_time_display(t: Any) -> str:
    """
    Formats a time into HH:MM string for clean user-facing error messages.
    """
    if t is None:
        return ""
    if isinstance(t, str):
        return t[:5]
    if hasattr(t, "strftime"):
        return t.strftime("%H:%M")
    return str(t)

def get_schedule_intervals(days: Any, start_t: Any, end_t: Any) -> List[Tuple[int, int, int]]:
    """
    Expands a schedule into a list of (day_of_week, start_minute, end_minute).
    Handles standard daytime shifts (start < end) and overnight shifts (start > end) crossing midnight.
    day_of_week is 1 (Monday) through 7 (Sunday).
    """
    norm_days = normalize_days(days)
    if not norm_days or start_t is None or end_t is None:
        return []

    start_min = time_to_minutes(start_t)
    end_min = time_to_minutes(end_t)

    intervals = []
    if start_min < end_min:
        # Standard daytime shift within same calendar day
        for d in norm_days:
            intervals.append((d, start_min, end_min))
    elif start_min > end_min:
        # Nocturnal shift crossing midnight into the next day
        for d in norm_days:
            # Segment on shift start day (start_min to midnight 1440)
            intervals.append((d, start_min, 1440))
            # Segment on following day (midnight 0 to end_min)
            next_day = (d % 7) + 1
            intervals.append((next_day, 0, end_min))
    # If start_min == end_min, duration is 0, no interval added

    return intervals

def intervals_overlap(int1: Tuple[int, int, int], int2: Tuple[int, int, int]) -> bool:
    """
    Checks if two schedule intervals collide.
    Two intervals collide iff they occur on the same day and their time ranges strictly overlap:
    start1 < end2 and start2 < end1.
    Note: Contiguous shifts (e.g. 08:00-12:00 and 12:00-16:00) do NOT overlap.
    """
    day1, s1, e1 = int1
    day2, s2, e2 = int2
    if day1 != day2:
        return False
    return s1 < e2 and s2 < e1

def find_schedule_conflict(
    existing_schedules: List[Dict[str, Any]],
    new_days: Any,
    new_start: Any,
    new_end: Any,
    exclude_id: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    """
    Compares a candidate schedule against existing schedules of the employee.
    Returns None if no conflict exists, or a descriptive dictionary if a collision is found.
    """
    try:
        new_intervals = get_schedule_intervals(new_days, new_start, new_end)
    except Exception as e:
        logger.warning(f"Error parsing candidate schedule intervals: {e}")
        return None

    if not new_intervals:
        return None

    for sched in existing_schedules:
        if exclude_id and str(sched.get("id")) == str(exclude_id):
            continue

        try:
            old_intervals = get_schedule_intervals(
                sched.get("day_of_week", []),
                sched.get("start_time"),
                sched.get("end_time")
            )
        except Exception as e:
            logger.warning(f"Error parsing existing schedule intervals for sched {sched.get('id')}: {e}")
            continue

        for n_int in new_intervals:
            for o_int in old_intervals:
                if intervals_overlap(n_int, o_int):
                    day_num = n_int[0]
                    day_name = DAY_NAMES.get(day_num, f"Día {day_num}")
                    slot_name = sched.get("slot_name") or "Turno Regular"
                    o_start_str = format_time_display(sched.get("start_time"))
                    o_end_str = format_time_display(sched.get("end_time"))

                    return {
                        "conflict": True,
                        "day": day_num,
                        "day_name": day_name,
                        "conflicting_schedule": sched,
                        "message": (
                            f"Conflicto de horario: El día {day_name} se superpone con el turno existente "
                            f"'{slot_name}' ({o_start_str} – {o_end_str}). "
                            f"No es posible asignar dos servicios en el mismo horario."
                        )
                    }

    return None
