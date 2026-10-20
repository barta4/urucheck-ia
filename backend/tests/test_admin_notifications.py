"""
Tests for admin notification channels: outbound webhooks (delivery status,
retry, HMAC signing) and the monthly report email (HTML escaping, notify
flag, result propagation).
"""
import hashlib
import hmac
import json
import pytest
import sys
import os
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from agent_controller import (
    build_webhook_body,
    sign_webhook_body,
    build_monthly_report_html,
    run_monthly_report_for_company,
)


@pytest.fixture
def anyio_backend():
    return 'asyncio'


# ─── 1. Webhook signing ──────────────────────────────────────────────────────

def test_sign_webhook_body_is_verifiable():
    """The signature must be reproducible on the receiver side (HMAC-SHA256 over timestamp.body)."""
    body = build_webhook_body("employee_checkin", {"employee_name": "Ana"}, "2026-10-20T09:00:00-03:00")
    secret = "mi_secreto_de_firma"
    ts = "1729417200"

    signature = sign_webhook_body(body, secret, ts)
    assert signature.startswith("sha256=")

    # Receiver-side verification
    expected = "sha256=" + hmac.new(
        secret.encode("utf-8"),
        ts.encode("utf-8") + b"." + body,
        hashlib.sha256,
    ).hexdigest()
    assert signature == expected


def test_signature_changes_with_body():
    body_a = build_webhook_body("event", {"a": 1}, "t1")
    body_b = build_webhook_body("event", {"a": 2}, "t1")
    assert sign_webhook_body(body_a, "s", "1") != sign_webhook_body(body_b, "s", "1")


def test_build_webhook_body_is_deterministic():
    """Same input → same bytes (required for stable signatures)."""
    a = build_webhook_body("e", {"x": 1}, "t")
    b = build_webhook_body("e", {"x": 1}, "t")
    assert a == b
    parsed = json.loads(a.decode("utf-8"))
    assert parsed == {"event": "e", "data": {"x": 1}, "timestamp": "t"}


# ─── 2. Webhook delivery status ──────────────────────────────────────────────

@pytest.mark.anyio
async def test_send_webhook_4xx_is_failure_not_success():
    """A 404 endpoint must NOT be logged as 'sent' — the old code ignored resp.status."""
    from agent_controller import send_webhook

    class FakeResponse:
        status_code = 404
        text = "not found"

    mock_client = MagicMock()
    mock_client.post = AsyncMock(return_value=FakeResponse())
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    mock_db = MagicMock()
    mock_db.fetch_one = AsyncMock(return_value={
        "webhook_url": "https://example.com/hook",
        "webhook_secret": "sec",
        "webhook_notify_checkin": True,
    })

    with patch("agent_controller.database", mock_db), \
         patch("agent_controller.httpx.AsyncClient", return_value=mock_client):
        result = await send_webhook("employee_checkin", {"a": 1}, "comp-1", notify_flag="webhook_notify_checkin")

    assert result is False


@pytest.mark.anyio
async def test_send_webhook_2xx_sends_signed_headers():
    """A 200 delivery must include the HMAC signature headers."""
    from agent_controller import send_webhook

    class FakeResponse:
        status_code = 200

    mock_client = MagicMock()
    mock_client.post = AsyncMock(return_value=FakeResponse())
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    mock_db = MagicMock()
    mock_db.fetch_one = AsyncMock(return_value={
        "webhook_url": "https://example.com/hook",
        "webhook_secret": "sec",
        "webhook_notify_checkin": True,
    })

    with patch("agent_controller.database", mock_db), \
         patch("agent_controller.httpx.AsyncClient", return_value=mock_client):
        result = await send_webhook("employee_checkin", {"a": 1}, "comp-1", notify_flag="webhook_notify_checkin")

    assert result is True
    call = mock_client.post.call_args
    headers = call.kwargs["headers"]
    assert headers["X-UruCheck-Signature"].startswith("sha256=")
    assert headers["X-UruCheck-Timestamp"]
    # Signature must verify against the exact bytes sent
    body = call.kwargs["content"]
    expected = "sha256=" + hmac.new(
        b"sec", headers["X-UruCheck-Timestamp"].encode() + b"." + body, hashlib.sha256
    ).hexdigest()
    assert headers["X-UruCheck-Signature"] == expected


@pytest.mark.anyio
async def test_send_webhook_retries_5xx_then_succeeds():
    """A transient 500 must be retried, and succeed on a later attempt."""
    from agent_controller import send_webhook

    class R500:
        status_code = 500
    class R200:
        status_code = 200

    mock_client = MagicMock()
    mock_client.post = AsyncMock(side_effect=[R500(), R200()])
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    mock_db = MagicMock()
    mock_db.fetch_one = AsyncMock(return_value={"webhook_url": "https://example.com/hook", "webhook_secret": "s"})

    with patch("agent_controller.database", mock_db), \
         patch("agent_controller.httpx.AsyncClient", return_value=mock_client), \
         patch("agent_controller.asyncio.sleep", new=AsyncMock()):
        result = await send_webhook("monthly_attendance_report", {"a": 1}, "comp-1")

    assert result is True
    assert mock_client.post.await_count == 2


@pytest.mark.anyio
async def test_send_webhook_respects_disabled_flag():
    """The per-event toggle must silence the webhook entirely."""
    from agent_controller import send_webhook

    mock_db = MagicMock()
    mock_db.fetch_one = AsyncMock(return_value={
        "webhook_url": "https://example.com/hook",
        "webhook_notify_absence": False,   # flag OFF
    })

    with patch("agent_controller.database", mock_db):
        result = await send_webhook("employee_absent", {}, "comp-1", notify_flag="webhook_notify_absence")

    assert result is False


# ─── 3. Monthly report HTML escaping ──────────────────────────────────────────

def test_monthly_report_html_escapes_employee_data():
    """Employee names with HTML must be escaped — no markup injection in the admin's mail."""
    report = [{
        "name": "O'Brien <script>alert(1)</script>",
        "document_id": "1.234.567-8",
        "phone": "099 123 456",
        "address": "Av. 18 <b>Julio</b>",
        "dias_asistidos": 20,
        "tardanzas": 0,
        "horas_totales": 160.5,
        "bono_elegible": True,
    }]
    html = build_monthly_report_html(report, "Octubre 2026")
    import html as _html
    # Raw markup must never reach the email body
    assert "<script>" not in html
    assert "<b>Julio</b>" not in html
    # …but the escaped versions do
    assert _html.escape("<script>") in html
    assert _html.escape("<b>Julio</b>") in html
    # Apostrophe in "O'Brien" is escaped too (html.escape default)
    assert "O" + _html.escape("'") + "Brien" in html


# ─── 4. Monthly report email flag + result ─────────────────────────────────────

def _mock_report_database(config: dict):
    """database mock routing by SQL content for run_monthly_report_for_company."""
    db = MagicMock()
    emp_row = {"id": "e-1", "name": "Ana", "document_id": "1", "address": "Av 1", "phone": "099"}
    hours_row = {"day": None, "ci": datetime(2026, 9, 1, 9, 0), "co": datetime(2026, 9, 1, 18, 0)}

    async def fetch_all(query, params=None):
        if "FROM employees WHERE active = true AND company_id" in query:
            return [emp_row]
        if "GROUP BY DATE(timestamp)" in query:
            return [hours_row]
        return []

    async def fetch_one(query, params=None):
        if "FROM company_config" in query:
            return config
        if "status = 'late'" in query:
            return {"count": 0}
        if "COUNT(*)" in query:
            return {"count": 5}
        return None

    db.fetch_all = AsyncMock(side_effect=fetch_all)
    db.fetch_one = AsyncMock(side_effect=fetch_one)
    return db


@pytest.mark.anyio
async def test_monthly_email_skipped_when_notify_flag_off():
    """honor_notify_flag=True + admin toggle OFF → email NOT sent (webhook still goes)."""
    config = {
        "webhook_url": None,
        "webhook_secret": None,
        "smtp_host": "smtp.test",
        "smtp_port": 587,
        "smtp_username": "u",
        "smtp_password": "gAAAAAencrypted",
        "smtp_from_email": None,
        "smtp_to_email": "admin@test.com",
        "email_notify_monthly_report": False,
    }
    mock_db = _mock_report_database(config)
    smtp_mock = MagicMock(return_value=True)

    with patch("agent_controller.database", mock_db), \
         patch("email_service.send_smtp_email", smtp_mock):
        result = await run_monthly_report_for_company("comp-1", honor_notify_flag=True)

    assert result["employees"] == 1
    smtp_mock.assert_not_called()
    assert result["email_sent"] is None


@pytest.mark.anyio
async def test_monthly_email_sent_when_notify_flag_on():
    config = {
        "webhook_url": None,
        "webhook_secret": None,
        "smtp_host": "smtp.test",
        "smtp_port": 587,
        "smtp_username": "u",
        "smtp_password": "gAAAAAencrypted",
        "smtp_from_email": None,
        "smtp_to_email": "admin@test.com",
        "email_notify_monthly_report": True,
    }
    mock_db = _mock_report_database(config)
    smtp_mock = MagicMock(return_value=True)

    with patch("agent_controller.database", mock_db), \
         patch("email_service.send_smtp_email", smtp_mock):
        result = await run_monthly_report_for_company("comp-1", honor_notify_flag=True)

    assert result["email_sent"] is True
    smtp_mock.assert_called_once()


@pytest.mark.anyio
async def test_monthly_email_manual_send_ignores_flag():
    """Manual send (honor_notify_flag=False) sends even with the toggle OFF — explicit intent."""
    config = {
        "webhook_url": None,
        "webhook_secret": None,
        "smtp_host": "smtp.test",
        "smtp_port": 587,
        "smtp_username": "u",
        "smtp_password": "gAAAAAencrypted",
        "smtp_from_email": None,
        "smtp_to_email": "admin@test.com",
        "email_notify_monthly_report": False,
    }
    mock_db = _mock_report_database(config)
    smtp_mock = MagicMock(return_value=True)

    with patch("agent_controller.database", mock_db), \
         patch("email_service.send_smtp_email", smtp_mock):
        result = await run_monthly_report_for_company("comp-1", honor_notify_flag=False)

    assert result["email_sent"] is True
    smtp_mock.assert_called_once()


@pytest.mark.anyio
async def test_monthly_email_failure_is_propagated():
    """SMTP failure must surface in the result — no more false 'sent successfully'."""
    config = {
        "webhook_url": None,
        "webhook_secret": None,
        "smtp_host": "smtp.test",
        "smtp_port": 587,
        "smtp_username": "u",
        "smtp_password": "gAAAAAencrypted",
        "smtp_from_email": None,
        "smtp_to_email": "admin@test.com",
        "email_notify_monthly_report": True,
    }
    mock_db = _mock_report_database(config)
    smtp_mock = MagicMock(return_value=False)  # SMTP rejected the send

    with patch("agent_controller.database", mock_db), \
         patch("email_service.send_smtp_email", smtp_mock):
        result = await run_monthly_report_for_company("comp-1", honor_notify_flag=False)

    assert result["email_sent"] is False
    assert result["email_error"]


# ─── 5. SMTP TLS policy ──────────────────────────────────────────────────────

SMTP_CONFIG = {
    "smtp_host": "smtp.test",
    "smtp_port": 587,
    "smtp_username": "user@test",
    "smtp_password": "plaintext-legacy",   # decrypt_secret passes non-encrypted values through
    "smtp_from_email": "noreply@test",
    "smtp_to_email": "admin@test",
}


def test_smtp_starttls_handshake_failure_aborts_without_login():
    """A broken STARTTLS handshake must ABORT — credentials never sent in plaintext."""
    import smtplib
    import email_service

    mock_server = MagicMock()
    mock_server.starttls.side_effect = RuntimeError("TLS handshake failed")

    with patch("email_service.smtplib.SMTP", return_value=mock_server):
        result = email_service.send_smtp_email(SMTP_CONFIG, "Asunto", "<p>hola</p>")

    assert result is False
    mock_server.login.assert_not_called()
    mock_server.sendmail.assert_not_called()
    # The socket is still closed on abort
    mock_server.quit.assert_called_once()


def test_smtp_starttls_not_supported_continues():
    """A legacy relay without STARTTLS support still delivers (with a warning)."""
    import smtplib
    import email_service

    mock_server = MagicMock()
    mock_server.starttls.side_effect = smtplib.SMTPNotSupportedError("STARTTLS not supported")

    with patch("email_service.smtplib.SMTP", return_value=mock_server):
        result = email_service.send_smtp_email(SMTP_CONFIG, "Asunto", "<p>hola</p>")

    assert result is True
    mock_server.login.assert_called_once()
    mock_server.sendmail.assert_called_once()
