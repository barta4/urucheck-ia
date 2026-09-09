import pytest
from datetime import date, timedelta
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from routers.dashboard import _resolve_date_range, _build_log_filters

def test_resolve_date_range_empty_defaults_to_last_month():
    today = date.today()
    d_from, d_to = _resolve_date_range(None, None, default_to_last_month=True)
    assert d_to == today
    assert d_from == today - timedelta(days=30)

def test_resolve_date_range_empty_strings_default_to_last_month():
    today = date.today()
    d_from, d_to = _resolve_date_range("", "  ", default_to_last_month=True)
    assert d_to == today
    assert d_from == today - timedelta(days=30)

def test_resolve_date_range_only_date_from():
    today = date.today()
    d_from, d_to = _resolve_date_range("2026-08-01", "", default_to_last_month=True)
    assert d_from == date(2026, 8, 1)
    assert d_to == today

def test_resolve_date_range_only_date_to():
    target_to = date(2026, 9, 30)
    d_from, d_to = _resolve_date_range("", "2026-09-30", default_to_last_month=True)
    assert d_to == target_to
    assert d_from == target_to - timedelta(days=30)

def test_resolve_date_range_both_dates_provided():
    d_from, d_to = _resolve_date_range("2026-08-01", "2026-09-30", default_to_last_month=True)
    assert d_from == date(2026, 8, 1)
    assert d_to == date(2026, 9, 30)

def test_resolve_date_range_invalid_date_fallback():
    today = date.today()
    d_from, d_to = _resolve_date_range("invalid-date", "another-invalid", default_to_last_month=True)
    assert d_to == today
    assert d_from == today - timedelta(days=30)

def test_build_log_filters():
    params = {"cid": "company-123"}
    conditions = _build_log_filters(
        params=params,
        employee_id="emp-1",
        date_from=date(2026, 8, 1),
        date_to=date(2026, 8, 31),
        status="on_time"
    )
    where = " AND ".join(conditions)
    assert "al.company_id = :cid" in where
    assert "al.employee_id = :eid" in where
    assert "DATE(al.timestamp) >= :date_from" in where
    assert "DATE(al.timestamp) <= :date_to" in where
    assert "al.status = :status" in where
    assert params["eid"] == "emp-1"
    assert params["date_from"] == date(2026, 8, 1)
    assert params["date_to"] == date(2026, 8, 31)
    assert params["status"] == "on_time"
