"""
Tests for the notification system: Expo ticket parsing (dead-token purge)
and the push dedup registry.
"""
import pytest
import sys
import os
from unittest.mock import AsyncMock, MagicMock, patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from routers.notifications import (
    extract_dead_tickets,
    send_push_notifications_batch,
    try_acquire_push_slot,
    _DEAD_TOKEN_ERRORS,
)


@pytest.fixture
def anyio_backend():
    return 'asyncio'


# ─── 1. Expo ticket parsing ───────────────────────────────────────────────────

def test_extract_dead_tickets_all_ok():
    messages = [{"to": "ExponentPushToken[a]"}, {"to": "ExponentPushToken[b]"}]
    tickets = [{"status": "ok", "id": "x1"}, {"status": "ok", "id": "x2"}]
    dead, ok, failed = extract_dead_tickets(messages, tickets)
    assert dead == []
    assert ok == 2
    assert failed == 0


def test_extract_dead_tickets_detects_device_not_registered():
    """A 200 response can still carry per-ticket errors — dead tokens must be detected."""
    messages = [
        {"to": "ExponentPushToken[dead1]"},
        {"to": "ExponentPushToken[alive]"},
    ]
    tickets = [
        {"status": "error", "message": "unused", "details": {"error": "DeviceNotRegistered"}},
        {"status": "ok", "id": "ok1"},
    ]
    dead, ok, failed = extract_dead_tickets(messages, tickets)
    assert dead == ["ExponentPushToken[dead1]"]
    assert ok == 1
    assert failed == 1


def test_extract_dead_tickets_transient_errors_are_not_purged():
    """MessageRateExceeded / MessageTooBig are transient — the token must be kept."""
    messages = [
        {"to": "ExponentPushToken[rate]"},
        {"to": "ExponentPushToken[big]"},
    ]
    tickets = [
        {"status": "error", "details": {"error": "MessageRateExceeded"}},
        {"status": "error", "details": {"error": "MessageTooBig"}},
    ]
    dead, ok, failed = extract_dead_tickets(messages, tickets)
    assert dead == []
    assert ok == 0
    assert failed == 2


def test_extract_dead_tickets_malformed_tickets():
    """Non-dict tickets must count as failures, never crash."""
    messages = [{"to": "ExponentPushToken[a]"}]
    dead, ok, failed = extract_dead_tickets(messages, [None])
    assert dead == []
    assert failed == 1


# ─── 2. Push dedup registry ───────────────────────────────────────────────────

@pytest.mark.anyio
async def test_try_acquire_push_slot_first_call_wins():
    """First claimant gets the slot (INSERT ... RETURNING id); the second is rejected."""
    mock_db = MagicMock()
    mock_db.fetch_one = AsyncMock(side_effect=[{"id": "row-1"}, None])

    with patch("routers.notifications.database", mock_db):
        first = await try_acquire_push_slot("emp-1", "shift_reminder", "shift:s1:2026-10-20")
        second = await try_acquire_push_slot("emp-1", "shift_reminder", "shift:s1:2026-10-20")

    assert first is True
    assert second is False


@pytest.mark.anyio
async def test_try_acquire_push_slot_fails_open():
    """If the registry is unavailable, reminders still go out (dedup is best-effort)."""
    mock_db = MagicMock()
    mock_db.fetch_one = AsyncMock(side_effect=Exception("table missing"))

    with patch("routers.notifications.database", mock_db):
        result = await try_acquire_push_slot("emp-1", "absence", "absence:emp-1:2026-10-20")
    assert result is True


# ─── 3. Batch sender purges dead tokens ───────────────────────────────────────

@pytest.mark.anyio
async def test_batch_purges_dead_tokens():
    """Dead tokens reported by Expo must be purged from the employees table."""
    dead_token = "ExponentPushToken[dead]"
    messages = [
        {"to": dead_token, "title": "t1", "body": "b1"},
        {"to": "ExponentPushToken[alive]", "title": "t2", "body": "b2"},
    ]

    class FakeResponse:
        status_code = 200
        text = '{"data": [{"status": "error", "details": {"error": "DeviceNotRegistered"}}, {"status": "ok", "id": "x"}]}'
        def json(self):
            return {"data": [
                {"status": "error", "details": {"error": "DeviceNotRegistered"}},
                {"status": "ok", "id": "x"},
            ]}

    mock_client = MagicMock()
    mock_client.post = AsyncMock(return_value=FakeResponse())
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    mock_db = MagicMock()
    mock_db.execute = AsyncMock()

    with patch("routers.notifications.httpx.AsyncClient", return_value=mock_client), \
         patch("routers.notifications.database", mock_db):
        stats = await send_push_notifications_batch(messages)

    assert stats["sent"] == 1
    assert stats["failed"] == 1
    assert stats["purged"] == 1
    # The purge UPDATE must target exactly the dead token
    mock_db.execute.assert_any_call(
        "UPDATE employees SET expo_push_token = NULL WHERE expo_push_token = :t",
        {"t": dead_token},
    )


def test_dead_token_error_set():
    """Only permanently-fatal Expo errors belong in the purge set."""
    assert _DEAD_TOKEN_ERRORS == {"DeviceNotRegistered", "InvalidRegistration"}
