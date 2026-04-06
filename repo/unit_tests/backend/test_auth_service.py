"""Unit tests for app.services.auth_service -- no database required."""

from app.services.auth_service import (
    hash_password,
    verify_password,
    create_access_token,
    create_refresh_token,
    decode_token,
)


def test_hash_password_returns_bcrypt_hash():
    hashed = hash_password("TestPassword123!")
    assert isinstance(hashed, str)
    assert hashed.startswith("$2b$"), f"Expected bcrypt hash starting with $2b$, got: {hashed[:10]}"


def test_verify_password_correct():
    hashed = hash_password("CorrectPassword!")
    assert verify_password("CorrectPassword!", hashed) is True


def test_verify_password_wrong():
    hashed = hash_password("CorrectPassword!")
    assert verify_password("WrongPassword!", hashed) is False


def test_create_access_token_returns_jwt_with_three_parts():
    token = create_access_token({"sub": "user-id-123", "role": "admin"})
    assert isinstance(token, str)
    parts = token.split(".")
    assert len(parts) == 3, f"JWT should have 3 dot-separated parts, got {len(parts)}"


def test_create_refresh_token_has_refresh_type():
    token = create_refresh_token({"sub": "user-id-456", "role": "resident"})
    payload = decode_token(token)
    assert payload.get("type") == "refresh", f"Expected type='refresh', got: {payload.get('type')}"
