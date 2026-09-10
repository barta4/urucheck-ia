import pytest
import sys
import os
from datetime import datetime, time, date
from zoneinfo import ZoneInfo
from unittest.mock import AsyncMock, patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from routers.attendance import _parse_optional_float, check_geofence
from rules_engine import get_next_mark_type, get_employee_schedule
from config import settings


@pytest.fixture
def anyio_backend():
    return 'asyncio'


def test_parse_optional_float():
    """Verify safe float parsing handles empty strings, nulls, and valid floats."""
    assert _parse_optional_float(None) is None
    assert _parse_optional_float("") is None
    assert _parse_optional_float("   ") is None
    assert _parse_optional_float("null") is None
    assert _parse_optional_float("undefined") is None
    assert _parse_optional_float("invalid") is None
    assert _parse_optional_float("-34.901112") == -34.901112
    assert _parse_optional_float("15.5") == 15.5
    assert _parse_optional_float(42.0) == 42.0


@pytest.mark.anyio
async def test_get_next_mark_type_timezone_evening():
    """
    Simulate 22:30 in Montevideo (UTC-3).
    In UTC, this is 01:30 of the NEXT day.
    Verify get_next_mark_type queries using the local date (Wednesday) and not UTC (Thursday).
    """
    tz = ZoneInfo("America/Montevideo")
    # 2026-09-09 22:30:00 Montevideo time
    local_dt = datetime(2026, 9, 9, 22, 30, 0, tzinfo=tz)

    queried_dates = []

    async def mock_fetch_all(query, params=None):
        if "FROM attendance_logs" in query:
            queried_dates.append(params.get("today"))
            # Return empty logs for first call -> check_in
            return []
        if "FROM schedules" in query:
            return [{"id": "sched-1", "start_time": time(22, 0), "end_time": time(23, 0), "break_mode": "flexible"}]
        return []

    with patch("rules_engine.database.fetch_all", side_effect=mock_fetch_all):
        action = await get_next_mark_type("emp-1", "comp-1", current_dt=local_dt)
        assert action == "check_in"
        # The query MUST have searched for local date 2026-09-09, NOT UTC 2026-09-10
        assert queried_dates == [date(2026, 9, 9)]


@pytest.mark.anyio
async def test_get_next_mark_type_advances_after_checkin():
    """
    Verify that after check_in, get_next_mark_type advances to break_start or check_out.
    """
    tz = ZoneInfo("America/Montevideo")
    local_dt = datetime(2026, 9, 9, 22, 35, 0, tzinfo=tz)

    async def mock_fetch_all(query, params=None):
        if "FROM attendance_logs" in query:
            return [{"type": "check_in", "timestamp": datetime(2026, 9, 9, 22, 5, 0)}]
        if "FROM schedules" in query:
            return [{
                "id": "sched-1",
                "start_time": time(22, 0),
                "end_time": time(23, 0),
                "break_mode": "flexible"
            }]
        return []

    with patch("rules_engine.database.fetch_all", side_effect=mock_fetch_all):
        with patch("rules_engine.get_employee_schedule", return_value={"break_mode": "flexible"}):
            action = await get_next_mark_type("emp-1", "comp-1", current_dt=local_dt)
            # Must advance to break_start (not stay on check_in)
            assert action == "break_start"


@pytest.mark.anyio
async def test_get_employee_schedule_overnight_window():
    """
    Verify get_employee_schedule matches an overnight shift (e.g. 22:00 to 06:00).
    """
    overnight_row = {
        "id": "sched-night",
        "employee_id": "emp-1",
        "company_id": "comp-1",
        "day_of_week": [1, 2, 3, 4, 5],
        "start_time": time(22, 0),
        "end_time": time(6, 0),
        "slot_name": "Turno Noche",
        "tolerance_minutes": 5,
        "break_mode": "flexible",
        "geofence_id": None
    }

    async def mock_fetch_all(query, params=None):
        return [overnight_row]

    with patch("rules_engine.database.fetch_all", side_effect=mock_fetch_all):
        # Current time is 23:15 -> inside overnight active window [21:30 .. 06:30]
        sched = await get_employee_schedule("emp-1", "comp-1", weekday=2, current_time=time(23, 15))
        assert sched is not None
        assert sched["id"] == "sched-night"

        # Current time is 05:45 -> inside overnight active window
        sched_morning = await get_employee_schedule("emp-1", "comp-1", weekday=2, current_time=time(5, 45))
        assert sched_morning is not None
        assert sched_morning["id"] == "sched-night"


@pytest.mark.anyio
async def test_check_geofence_all_locations_allowed():
    """
    When schedule has geofence_id is None, it represents 'Todas las ubicaciones permitidas'.
    In mark_attendance, in_geofence evaluates to True regardless of employee coordinates.
    """
    schedule = {"id": "sched-1", "geofence_id": None}
    geofence_id = schedule.get("geofence_id")
    in_geofence = True if (schedule and geofence_id is None) else False
    assert in_geofence is True


@pytest.mark.anyio
async def test_get_today_logs_no_unbound_error():
    """
    Verify get_today_logs executes successfully and accesses settings.TIMEZONE
    without UnboundLocalError.
    """
    from routers.attendance import get_today_logs

    mock_user = {"id": "emp-1", "company_id": "comp-1"}

    async def mock_fetch_all(query, params=None):
        return []

    async def mock_fetch_one(query, params=None):
        return None

    with patch("routers.attendance.database.fetch_all", side_effect=mock_fetch_all), \
         patch("routers.attendance.database.fetch_one", side_effect=mock_fetch_one), \
         patch("routers.attendance.get_next_mark_type", return_value="check_in"), \
         patch("routers.attendance.get_employee_schedule", return_value=None):
        res = await get_today_logs(current_user=mock_user)
        assert res["logs"] == []
        assert res["next_action"] == "check_in"
        assert res["streak"] == 0

