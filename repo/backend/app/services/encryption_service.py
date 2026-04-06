from __future__ import annotations

import os
import logging
from pathlib import Path

from cryptography.fernet import Fernet

from app.config import settings

# ---------------------------------------------------------------------------
# Fernet cipher – initialised from settings.ENCRYPTION_KEY.
# If the key is empty/missing, we attempt to load or generate a persisted key
# so the application can still boot and data survives restarts.
# ---------------------------------------------------------------------------

_logger = logging.getLogger("harborview")


def _resolve_encryption_key() -> str:
    key = getattr(settings, "ENCRYPTION_KEY", "") or ""
    if key:
        return key

    # Try to load from persisted file
    key_file = Path(settings.UPLOAD_DIR).parent / ".encryption_key"
    if key_file.exists():
        return key_file.read_text().strip()

    # Generate and persist
    new_key = Fernet.generate_key().decode()
    try:
        key_file.parent.mkdir(parents=True, exist_ok=True)
        key_file.write_text(new_key)
        _logger.warning(
            "ENCRYPTION_KEY not set. Generated and saved to %s. "
            "For production, set ENCRYPTION_KEY explicitly.", key_file
        )
    except OSError:
        _logger.warning("ENCRYPTION_KEY not set and could not persist key file. Data may be lost on restart.")
    return new_key


_encryption_key = _resolve_encryption_key()
_fernet = Fernet(_encryption_key.encode() if isinstance(_encryption_key, str) else _encryption_key)


def encrypt_field(value: str) -> bytes:
    """Encrypt a string value and return the cipher-text as bytes."""
    return _fernet.encrypt(value.encode("utf-8"))


def decrypt_field(data: bytes) -> str:
    """Decrypt cipher-text bytes back to the original string."""
    return _fernet.decrypt(data).decode("utf-8")


def mask_email(email: str) -> str:
    """Mask an email address, e.g. ``user@example.com`` -> ``****@example.com``."""
    if "@" not in email:
        return "****"
    _, domain = email.rsplit("@", 1)
    return f"****@{domain}"


def mask_phone(phone: str) -> str:
    """Mask a phone number, keeping only the last 4 digits.

    ``+1-555-867-5309`` -> ``****5309``
    """
    digits = "".join(ch for ch in phone if ch.isdigit())
    if len(digits) < 4:
        return "****"
    return f"****{digits[-4:]}"
