"""
Automated tests for UruCheck IA Security Audit remediation.
Verifies HMAC webhook validation, cryptographic encryption at rest,
password complexity enforcement, and config update whitelist protection.
"""
import pytest
import sys
import os
import time
import hmac
import hashlib
from jose import jwt

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from config import settings
from crypto import encrypt_secret, decrypt_secret, mask_secret
from routers.payments import verify_mp_signature
from routers.company import _ALLOWED_CONFIG_UPDATE_FIELDS
from schemas import validate_password_complexity, CompanyCreate, EmployeeCreate
from auth import create_access_token


# ─── 1. MercadoPago Webhook HMAC Signature Tests (H3) ──────────────────────────

def test_mp_webhook_signature_valid():
    secret = "test_webhook_secret_key_123"
    request_id = "req-uuid-456"
    data_id = "99887766"
    ts = str(int(time.time()))

    manifest = f"id:{data_id};request-id:{request_id};ts:{ts};"
    v1_hash = hmac.new(secret.encode(), manifest.encode(), hashlib.sha256).hexdigest()
    x_signature = f"ts={ts},v1={v1_hash}"

    assert verify_mp_signature(x_signature, request_id, data_id, secret) is True


def test_mp_webhook_signature_invalid_hash():
    secret = "test_webhook_secret_key_123"
    request_id = "req-uuid-456"
    data_id = "99887766"
    ts = str(int(time.time()))

    x_signature = f"ts={ts},v1=invalid_tampered_hash_value"
    assert verify_mp_signature(x_signature, request_id, data_id, secret) is False


def test_mp_webhook_signature_replay_expired():
    secret = "test_webhook_secret_key_123"
    request_id = "req-uuid-456"
    data_id = "99887766"
    # 15 minutes old (exceeds 600s max_age)
    old_ts = str(int(time.time()) - 900)

    manifest = f"id:{data_id};request-id:{request_id};ts:{old_ts};"
    v1_hash = hmac.new(secret.encode(), manifest.encode(), hashlib.sha256).hexdigest()
    x_signature = f"ts={old_ts},v1={v1_hash}"

    assert verify_mp_signature(x_signature, request_id, data_id, secret) is False


def test_mp_webhook_missing_parameters():
    assert verify_mp_signature(None, "req-1", "data-1", "secret") is False
    assert verify_mp_signature("ts=123,v1=abc", None, "data-1", "secret") is False
    assert verify_mp_signature("ts=123,v1=abc", "req-1", "data-1", "") is False


# ─── 2. Cryptography at Rest for SMTP Credentials (H5) ─────────────────────────

def test_crypto_encryption_and_decryption_cycle():
    raw_secret = "smtp_super_secret_password_123!@#"
    encrypted = encrypt_secret(raw_secret)

    assert encrypted is not None
    assert encrypted != raw_secret
    assert encrypted.startswith("gAAAAA")

    decrypted = decrypt_secret(encrypted)
    assert decrypted == raw_secret


def test_crypto_handles_legacy_plaintext_gracefully():
    legacy_plain = "my_old_unencrypted_password"
    decrypted = decrypt_secret(legacy_plain)
    assert decrypted == legacy_plain


def test_crypto_masking():
    assert mask_secret("super_secret") == "********"
    assert mask_secret(None) == ""
    assert mask_secret("") == ""


# ─── 3. Password Complexity Enforcement (H14) ──────────────────────────────────

def test_password_complexity_valid():
    assert validate_password_complexity("ValidP@ssw0rd") == "ValidP@ssw0rd"
    assert validate_password_complexity("Strong123Admin") == "Strong123Admin"


def test_password_complexity_too_short():
    with pytest.raises(ValueError, match="al menos 8 caracteres"):
        validate_password_complexity("Short1A")


def test_password_complexity_missing_number():
    with pytest.raises(ValueError, match="al menos un número"):
        validate_password_complexity("NoNumbersHere!")


def test_password_complexity_missing_uppercase():
    with pytest.raises(ValueError, match="al menos una letra mayúscula"):
        validate_password_complexity("lowercase12345")


# ─── 4. Company Config Whitelist Protection (H11) ──────────────────────────────

def test_company_config_whitelist_contents():
    # Sensitive or dangerous columns must NOT be in the whitelist
    assert "company_id" not in _ALLOWED_CONFIG_UPDATE_FIELDS
    assert "id" not in _ALLOWED_CONFIG_UPDATE_FIELDS
    assert "created_at" not in _ALLOWED_CONFIG_UPDATE_FIELDS
    assert "deleted_at" not in _ALLOWED_CONFIG_UPDATE_FIELDS

    # Legitimate config fields MUST be in whitelist
    assert "smtp_host" in _ALLOWED_CONFIG_UPDATE_FIELDS
    assert "smtp_password" in _ALLOWED_CONFIG_UPDATE_FIELDS
    assert "timezone" in _ALLOWED_CONFIG_UPDATE_FIELDS
    assert "tolerance_minutes" in _ALLOWED_CONFIG_UPDATE_FIELDS
    assert "face_verification_enabled" in _ALLOWED_CONFIG_UPDATE_FIELDS


# ─── 5. JWT jti Claim & Identification (H6) ───────────────────────────────────

def test_jwt_token_includes_jti():
    payload = {"sub": "employee-abc-123", "company_id": "company-xyz"}
    token = create_access_token(payload)
    decoded = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])

    assert "jti" in decoded
    assert len(decoded["jti"]) >= 16
