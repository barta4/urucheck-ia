"""
Cryptographic utilities for encrypting and decrypting sensitive data at rest
(e.g., SMTP credentials, API tokens) using symmetric Fernet encryption.
"""
import base64
import hashlib
import logging
from typing import Optional
from cryptography.fernet import Fernet, InvalidToken
from config import settings

logger = logging.getLogger(__name__)

_fernet_instance: Optional[Fernet] = None


def _get_fernet() -> Fernet:
    """
    Get or create a cached Fernet instance.
    Uses settings.ENCRYPTION_KEY if provided; otherwise derives a stable 32-byte
    base64 urlsafe key from settings.SECRET_KEY.
    """
    global _fernet_instance
    if _fernet_instance is not None:
        return _fernet_instance

    raw_key = (settings.ENCRYPTION_KEY or "").strip()
    if raw_key:
        try:
            _fernet_instance = Fernet(raw_key.encode("utf-8"))
            return _fernet_instance
        except Exception as e:
            logger.warning(
                f"[Crypto] Invalid ENCRYPTION_KEY provided: {e}. Falling back to key derived from SECRET_KEY."
            )

    # Derive 32-byte key from SECRET_KEY using SHA-256 and base64 urlsafe encoding
    derived_bytes = hashlib.sha256(settings.SECRET_KEY.encode("utf-8")).digest()
    derived_b64 = base64.urlsafe_b64encode(derived_bytes)
    _fernet_instance = Fernet(derived_b64)
    return _fernet_instance


def encrypt_secret(plain_text: Optional[str]) -> Optional[str]:
    """
    Encrypt a plaintext string using Fernet.
    Returns base64 ciphertext string, or None if input is empty.
    If already encrypted (starts with 'gAAAAA'), returns as is to avoid double encryption.
    """
    if not plain_text:
        return None
    plain_str = str(plain_text).strip()
    if not plain_str:
        return ""
    if plain_str.startswith("gAAAAA"):
        # Already a Fernet token
        return plain_str

    f = _get_fernet()
    encrypted = f.encrypt(plain_str.encode("utf-8"))
    return encrypted.decode("utf-8")


def decrypt_secret(cipher_text: Optional[str]) -> Optional[str]:
    """
    Decrypt a Fernet ciphertext string.
    If not encrypted (legacy plaintext), returns as is gracefully.
    """
    if not cipher_text:
        return None
    cipher_str = str(cipher_text).strip()
    if not cipher_str:
        return ""
    if not cipher_str.startswith("gAAAAA"):
        # Unencrypted / legacy value
        return cipher_str

    try:
        f = _get_fernet()
        decrypted = f.decrypt(cipher_str.encode("utf-8"))
        return decrypted.decode("utf-8")
    except InvalidToken:
        logger.error("[Crypto] Failed to decrypt secret: invalid token or wrong key")
        return None
    except Exception as e:
        logger.error(f"[Crypto] Decryption error: {e}")
        return None


def mask_secret(value: Optional[str], visible_chars: int = 0) -> str:
    """
    Return a masked representation of a secret for display in API responses.
    """
    if not value:
        return ""
    return "********"
