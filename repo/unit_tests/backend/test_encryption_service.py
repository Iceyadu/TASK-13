"""Unit tests for app.services.encryption_service -- no database required."""

from app.services.encryption_service import (
    encrypt_field,
    decrypt_field,
    mask_email,
    mask_phone,
)


def test_encrypt_decrypt_roundtrip():
    original = "sensitive-data-12345"
    encrypted = encrypt_field(original)
    assert isinstance(encrypted, bytes)
    assert encrypted != original.encode("utf-8"), "Encrypted data should differ from plaintext"
    decrypted = decrypt_field(encrypted)
    assert decrypted == original


def test_mask_email_returns_starred_domain_format():
    masked = mask_email("alice@example.com")
    assert masked == "****@example.com", f"Expected '****@example.com', got '{masked}'"


def test_mask_phone_returns_starred_last_four():
    masked = mask_phone("+1-555-867-5309")
    assert masked == "****5309", f"Expected '****5309', got '{masked}'"
