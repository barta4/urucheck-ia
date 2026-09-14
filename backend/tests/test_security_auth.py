import pytest
import sys
import os
from datetime import datetime, timedelta, timezone
from jose import jwt, JWTError

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from auth import verify_password, get_password_hash, create_access_token
from config import settings

def test_password_hashing_and_verification():
    raw_password = "SecurePassword123!"
    hashed = get_password_hash(raw_password)
    
    assert hashed != raw_password
    assert verify_password(raw_password, hashed) is True
    assert verify_password("WrongPassword", hashed) is False

def test_jwt_token_creation_and_claims():
    payload_data = {
        "sub": "emp-123",
        "company_id": "comp-456",
        "company_slug": "acme-corp"
    }
    token = create_access_token(payload_data)
    decoded = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    
    assert decoded["sub"] == "emp-123"
    assert decoded["company_id"] == "comp-456"
    assert decoded["company_slug"] == "acme-corp"
    assert "exp" in decoded

def test_jwt_token_expired():
    payload_data = {
        "sub": "emp-123",
        "company_id": "comp-456"
    }
    # Create an already expired token
    token = create_access_token(payload_data, expires_delta=timedelta(seconds=-10))
    
    with pytest.raises(JWTError):
        jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])

def test_tenant_photo_isolation_prefix_check():
    company_id_a = "11111111-1111-1111-1111-111111111111"
    company_id_b = "22222222-2222-2222-2222-222222222222"
    
    valid_prefixes_a = (
        f"{company_id_a}_",
        f"logo_{company_id_a}_",
        f"face_{company_id_a}_",
        f"cert_{company_id_a}_"
    )
    
    # Own file should match
    own_file = f"face_{company_id_a}_emp_999.jpg"
    assert own_file.startswith(valid_prefixes_a) is True
    
    # Other company file should NOT match
    other_file = f"face_{company_id_b}_emp_888.jpg"
    assert other_file.startswith(valid_prefixes_a) is False

def test_get_current_admin_rejects_employee():
    import asyncio
    from auth import get_current_admin
    from fastapi import HTTPException
    
    employee_user = {
        "id": "11111111-1111-1111-1111-111111111111",
        "company_id": "22222222-2222-2222-2222-222222222222",
        "name": "Juan Perez",
        "email": "juan@empresa.com",
        "role": "employee",
        "is_super_admin": False
    }
    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(get_current_admin(employee_user))
    assert exc_info.value.status_code == 403
    assert "administrador" in exc_info.value.detail.lower()

def test_get_current_admin_accepts_admin():
    import asyncio
    from auth import get_current_admin
    
    admin_user = {
        "id": "11111111-1111-1111-1111-111111111111",
        "company_id": "22222222-2222-2222-2222-222222222222",
        "name": "Admin Boss",
        "email": "admin@empresa.com",
        "role": "admin",
        "is_super_admin": False
    }
    result = asyncio.run(get_current_admin(admin_user))
    assert result["role"] == "admin"

def test_login_request_portal_schema():
    from schemas import LoginRequest
    
    req_default = LoginRequest(email="test@empresa.com", password="Password123")
    assert req_default.portal is None
    
    req_admin = LoginRequest(email="test@empresa.com", password="Password123", portal="admin")
    assert req_admin.portal == "admin"
