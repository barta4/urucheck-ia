import pytest
from datetime import time
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from schedule_validator import (
    normalize_days,
    time_to_minutes,
    get_schedule_intervals,
    intervals_overlap,
    find_schedule_conflict,
)

def test_normalize_days():
    assert normalize_days([1, 2, 3]) == [1, 2, 3]
    assert normalize_days("{1,3,5}") == [1, 3, 5]
    assert normalize_days("[2,4,6]") == [2, 4, 6]
    assert normalize_days(None) == []

def test_time_to_minutes():
    assert time_to_minutes("09:00") == 540
    assert time_to_minutes("09:00:00") == 540
    assert time_to_minutes(time(9, 30)) == 570
    assert time_to_minutes("00:00") == 0
    assert time_to_minutes("23:59") == 1439

def test_intervals_overlap():
    # Same day, overlapping: 09:00-12:00 vs 09:00-12:00
    assert intervals_overlap((1, 540, 720), (1, 540, 720)) is True
    # Same day, partial overlap: 09:00-12:00 vs 11:00-14:00
    assert intervals_overlap((1, 540, 720), (1, 660, 840)) is True
    # Same day, contiguous: 08:00-12:00 vs 12:00-16:00 (end touches start -> NO overlap)
    assert intervals_overlap((1, 480, 720), (1, 720, 960)) is False
    # Same day, completely separate
    assert intervals_overlap((1, 480, 600), (1, 720, 960)) is False
    # Different days
    assert intervals_overlap((1, 540, 720), (2, 540, 720)) is False

def test_exact_case_from_user_screenshot():
    """
    Test the exact scenario reported by the user:
    Schedule 1: 'CASA PEPE' 09:00 - 12:00 on Lun, Mié, Vie [1, 3, 5]
    Schedule 2: 'SHOPPING XXX' 09:00 - 12:00 on Lun, Mar, Jue [1, 2, 4]
    Must detect collision on Lunes (1).
    """
    existing = [
        {
            "id": "sched-1",
            "slot_name": "CASA PEPE",
            "day_of_week": [1, 3, 5],
            "start_time": time(9, 0),
            "end_time": time(12, 0),
        }
    ]

    conflict = find_schedule_conflict(
        existing_schedules=existing,
        new_days=[1, 2, 4],
        new_start="09:00",
        new_end="12:00"
    )

    assert conflict is not None
    assert conflict["conflict"] is True
    assert conflict["day"] == 1
    assert conflict["day_name"] == "Lunes"
    assert "CASA PEPE" in conflict["message"]
    assert "09:00" in conflict["message"]

def test_no_conflict_on_different_days():
    existing = [
        {
            "id": "sched-1",
            "slot_name": "CASA PEPE",
            "day_of_week": [3, 5], # Miércoles, Viernes
            "start_time": time(9, 0),
            "end_time": time(12, 0),
        }
    ]

    conflict = find_schedule_conflict(
        existing_schedules=existing,
        new_days=[1, 2, 4], # Lunes, Martes, Jueves
        new_start="09:00",
        new_end="12:00"
    )

    assert conflict is None

def test_contiguous_shifts_allowed():
    """
    Morning shift 08:00 - 12:00 and afternoon shift 12:00 - 16:00 on Monday
    should NOT be considered a conflict.
    """
    existing = [
        {
            "id": "sched-1",
            "slot_name": "Turno Mañana",
            "day_of_week": [1],
            "start_time": "08:00",
            "end_time": "12:00",
        }
    ]

    conflict = find_schedule_conflict(
        existing_schedules=existing,
        new_days=[1],
        new_start="12:00",
        new_end="16:00"
    )

    assert conflict is None

def test_nocturnal_shift_overlap():
    """
    Existing: Sunday night shift 22:00 to Monday morning 06:00 (day 7).
    Candidate: Monday morning shift 05:00 to 09:00 (day 1).
    Overlaps on Monday between 05:00 and 06:00.
    """
    existing = [
        {
            "id": "sched-night",
            "slot_name": "Guardia Nocturna",
            "day_of_week": [7], # Domingo
            "start_time": "22:00",
            "end_time": "06:00", # Cruza a lunes
        }
    ]

    conflict = find_schedule_conflict(
        existing_schedules=existing,
        new_days=[1], # Lunes
        new_start="05:00",
        new_end="09:00"
    )

    assert conflict is not None
    assert conflict["day"] == 1
    assert conflict["day_name"] == "Lunes"
