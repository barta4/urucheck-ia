import pytest
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock
from fastapi import HTTPException
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from routers.employees import delete_employee

def test_delete_employee_prevents_self_deletion():
    current_admin = {
        "id": "11111111-1111-1111-1111-111111111111",
        "company_id": "22222222-2222-2222-2222-222222222222",
        "role": "admin"
    }

    mock_db = MagicMock()
    mock_db.fetch_one = AsyncMock(return_value={
        "id": current_admin["id"],
        "name": "Admin Boss",
        "email": "admin@empresa.com",
        "role": "admin",
        "face_reference_path": None
    })

    with patch("routers.employees.database", mock_db):
        with pytest.raises(HTTPException) as exc_info:
            asyncio.run(delete_employee(current_admin["id"], current_admin))
        assert exc_info.value.status_code == 400
        assert "propia cuenta" in exc_info.value.detail.lower()

def test_delete_employee_prevents_single_admin_deletion():
    current_admin = {
        "id": "11111111-1111-1111-1111-111111111111",
        "company_id": "22222222-2222-2222-2222-222222222222",
        "role": "admin"
    }
    target_admin_id = "33333333-3333-3333-3333-333333333333"

    mock_db = MagicMock()
    # First fetch_one: target employee exists and is an admin
    # Second fetch_one: admin_count returns 1
    mock_db.fetch_one = AsyncMock(side_effect=[
        {
            "id": target_admin_id,
            "name": "Another Admin",
            "email": "admin2@empresa.com",
            "role": "admin",
            "face_reference_path": None
        },
        {"cnt": 1}
    ])

    with patch("routers.employees.database", mock_db):
        with pytest.raises(HTTPException) as exc_info:
            asyncio.run(delete_employee(target_admin_id, current_admin))
        assert exc_info.value.status_code == 400
        assert "único administrador" in exc_info.value.detail.lower()

def test_delete_employee_success():
    current_admin = {
        "id": "11111111-1111-1111-1111-111111111111",
        "company_id": "22222222-2222-2222-2222-222222222222",
        "role": "admin"
    }
    target_emp_id = "44444444-4444-4444-4444-444444444444"

    mock_db = MagicMock()
    mock_db.fetch_one = AsyncMock(return_value={
        "id": target_emp_id,
        "name": "Juan Perez",
        "email": "juan@empresa.com",
        "role": "employee",
        "face_reference_path": None
    })
    mock_db.fetch_all = AsyncMock(return_value=[])
    mock_db.execute = AsyncMock(return_value=None)

    with patch("routers.employees.database", mock_db):
        res = asyncio.run(delete_employee(target_emp_id, current_admin))
        assert "eliminados permanentemente" in res["message"]
        assert res["id"] == target_emp_id
        # Verify execute was called to delete employee record
        mock_db.execute.assert_any_call(
            "DELETE FROM employees WHERE id = :eid AND company_id = :cid",
            {"eid": target_emp_id, "cid": current_admin["company_id"]}
        )
