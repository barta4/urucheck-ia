"""
Tenant isolation tests: prove that the authenticated user's tenant binding
comes from the DATABASE (not stale JWT claims) and that suspending or
cancelling a company cuts API access immediately.
"""
import pytest
import sys
import os
from unittest.mock import AsyncMock, MagicMock, patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from fastapi import HTTPException
from auth import get_current_user, create_access_token
from config import settings


@pytest.fixture
def anyio_backend():
    return 'asyncio'


def _mock_db(user_row=None, revoked=False):
    """database mock: routes revoked-token lookups vs user lookups by SQL."""
    db = MagicMock()

    async def fetch_one(query, params=None):
        if "FROM revoked_tokens" in query:
            return {"jti": "revoked"} if revoked else None
        if "FROM employees e" in query:
            return user_row
        return None

    db.fetch_one = AsyncMock(side_effect=fetch_one)
    return db


def _user_row(company_status="active", is_super_admin=False, company_id="comp-1"):
    return {
        "id": "user-1",
        "company_id": company_id,
        "name": "Ana",
        "email": "ana@test.com",
        "role": "employee",
        "active": True,
        "is_super_admin": is_super_admin,
        "expo_push_token": None,
        "device_id": None,
        "company_status": company_status,
    }


@pytest.mark.anyio
async def test_active_company_user_authenticates():
    token = create_access_token({"sub": "user-1"})
    db = _mock_db(user_row=_user_row(company_status="active"))
    with patch("auth.database", db):
        user = await get_current_user(token=token)
    assert user["id"] == "user-1"
    assert user["company_id"] == "comp-1"
    # The live company status is now part of the user context
    assert user["company_status"] == "active"


@pytest.mark.anyio
async def test_suspended_company_user_blocked_immediately():
    """Suspending a company must cut API access NOW, not at JWT expiry."""
    token = create_access_token({"sub": "user-1"})
    db = _mock_db(user_row=_user_row(company_status="suspended"))
    with patch("auth.database", db):
        with pytest.raises(HTTPException) as exc:
            await get_current_user(token=token)
    assert exc.value.status_code == 403
    assert "suspendida" in exc.value.detail


@pytest.mark.anyio
async def test_cancelled_company_user_blocked():
    token = create_access_token({"sub": "user-1"})
    db = _mock_db(user_row=_user_row(company_status="cancelled"))
    with patch("auth.database", db):
        with pytest.raises(HTTPException) as exc:
            await get_current_user(token=token)
    assert exc.value.status_code == 403
    assert "cancelada" in exc.value.detail


@pytest.mark.anyio
async def test_trial_and_grace_companies_still_allowed():
    """Trial/grace are legitimate non-paid states — must keep working."""
    for status in ("trial", "grace"):
        token = create_access_token({"sub": "user-1"})
        db = _mock_db(user_row=_user_row(company_status=status))
        with patch("auth.database", db):
            user = await get_current_user(token=token)
        assert user["company_status"] == status


@pytest.mark.anyio
async def test_super_admin_bypasses_company_suspension():
    """Platform staff must keep SaaS-panel access even if their own company is suspended."""
    token = create_access_token({"sub": "user-1"})
    db = _mock_db(user_row=_user_row(company_status="suspended", is_super_admin=True))
    with patch("auth.database", db):
        user = await get_current_user(token=token)
    assert user["is_super_admin"] is True


@pytest.mark.anyio
async def test_legacy_null_company_employee_cannot_authenticate():
    """The employees↔companies INNER JOIN must drop legacy NULL-company rows."""
    token = create_access_token({"sub": "user-1"})
    db = _mock_db(user_row=None)  # JOIN produced no row
    with patch("auth.database", db):
        with pytest.raises(HTTPException) as exc:
            await get_current_user(token=token)
    assert exc.value.status_code == 401


@pytest.mark.anyio
async def test_revoked_token_rejected():
    token = create_access_token({"sub": "user-1"})
    db = _mock_db(user_row=_user_row(), revoked=True)
    with patch("auth.database", db):
        with pytest.raises(HTTPException) as exc:
            await get_current_user(token=token)
    assert exc.value.status_code == 401


@pytest.mark.anyio
async def test_unknown_user_rejected():
    token = create_access_token({"sub": "ghost"})
    db = _mock_db(user_row=None)
    with patch("auth.database", db):
        with pytest.raises(HTTPException) as exc:
            await get_current_user(token=token)
    assert exc.value.status_code == 401


# ─── Photo filename tenant scoping ────────────────────────────────────────────

def test_photo_prefix_scoping_logic():
    """The per-tenant filename prefixes used by /api/photos."""
    company_id = "11111111-1111-1111-1111-111111111111"
    valid_prefixes = (
        f"{company_id}_",
        f"logo_{company_id}_",
        f"face_{company_id}_",
        f"cert_{company_id}_",
    )
    import os
    for name in (
        f"{company_id}_user_x.jpg",
        f"face_references/face_{company_id}_user.jpg",
        f"logos/logo_{company_id}_abc.png",
        f"certificates/cert_{company_id}_u.pdf",
    ):
        assert os.path.basename(name).startswith(valid_prefixes), name

    # Another tenant's files must NOT pass
    for name in (
        "22222222-2222-2222-2222-222222222222_user_x.jpg",
        "face_references/face_22222222-2222-2222-2222-222222222222_user.jpg",
    ):
        assert not os.path.basename(name).startswith(valid_prefixes), name
