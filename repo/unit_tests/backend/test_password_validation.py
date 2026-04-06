"""Unit tests for password validation via PasswordChangeRequest -- no database required."""

import pytest
from pydantic import ValidationError

from app.schemas.auth import PasswordChangeRequest


def _build(new_password: str) -> PasswordChangeRequest:
    """Helper to construct a PasswordChangeRequest with the given new_password."""
    return PasswordChangeRequest(
        current_password="OldPassword@123",
        new_password=new_password,
    )


def test_rejects_password_shorter_than_12_chars():
    with pytest.raises(ValidationError, match="12 characters"):
        _build("Ab1@short")


def test_rejects_password_without_uppercase():
    with pytest.raises(ValidationError, match="uppercase"):
        _build("alllowercase1@xx")


def test_rejects_password_without_digit():
    with pytest.raises(ValidationError, match="digit"):
        _build("NoDigitsHere@@!!")


def test_rejects_password_without_special_char():
    with pytest.raises(ValidationError, match="special character"):
        _build("NoSpecialChar123")


def test_valid_password_passes():
    req = _build("Admin@Harbor2026")
    assert req.new_password == "Admin@Harbor2026"
