import time
import hmac
import hashlib
import pytest
from payment_service import verify_mp_signature


def test_verify_mp_signature_valid():
    secret = "my_webhook_secret_key"
    ts = str(int(time.time()))
    req_id = "req-12345"
    data_id = "pay-98765"

    manifest = f"id:{data_id};request-id:{req_id};ts:{ts};"
    expected_v1 = hmac.new(
        secret.encode("utf-8"),
        manifest.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()

    x_signature = f"ts={ts},v1={expected_v1}"

    assert verify_mp_signature(
        x_signature=x_signature,
        x_request_id=req_id,
        data_id=data_id,
        secret=secret,
        max_age_seconds=600,
    ) is True


def test_verify_mp_signature_invalid_hash():
    secret = "my_webhook_secret_key"
    ts = str(int(time.time()))
    req_id = "req-12345"
    data_id = "pay-98765"

    x_signature = f"ts={ts},v1=fake_invalid_hash_value"

    assert verify_mp_signature(
        x_signature=x_signature,
        x_request_id=req_id,
        data_id=data_id,
        secret=secret,
        max_age_seconds=600,
    ) is False


def test_verify_mp_signature_expired_timestamp():
    secret = "my_webhook_secret_key"
    # 2 hours ago (expired)
    ts = str(int(time.time()) - 7200)
    req_id = "req-12345"
    data_id = "pay-98765"

    manifest = f"id:{data_id};request-id:{req_id};ts:{ts};"
    expected_v1 = hmac.new(
        secret.encode("utf-8"),
        manifest.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()

    x_signature = f"ts={ts},v1={expected_v1}"

    assert verify_mp_signature(
        x_signature=x_signature,
        x_request_id=req_id,
        data_id=data_id,
        secret=secret,
        max_age_seconds=600,
    ) is False


def test_verify_mp_signature_missing_headers():
    assert verify_mp_signature(None, "req-1", "123", "secret") is False
    assert verify_mp_signature("ts=123", None, "123", "secret") is False
    assert verify_mp_signature("ts=123", "req-1", "123", "") is False
