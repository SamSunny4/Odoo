import pytest
from app.core.security import validate_password_strength


def test_password_strength_valid():
    """Valid password matching all criteria should pass without exception."""
    validate_password_strength("Admin@12345!")
    validate_password_strength("StrongPass#2026")


def test_password_strength_too_short():
    """8 characters or fewer must be rejected (> 8 required)."""
    with pytest.raises(ValueError, match="more than 8 characters"):
        validate_password_strength("Abc@123")  # 7 chars
    with pytest.raises(ValueError, match="more than 8 characters"):
        validate_password_strength("Abc@1234")  # exactly 8 chars


def test_password_strength_missing_uppercase():
    """Must contain uppercase."""
    with pytest.raises(ValueError, match="uppercase"):
        validate_password_strength("weakpass@1234")


def test_password_strength_missing_lowercase():
    """Must contain lowercase."""
    with pytest.raises(ValueError, match="lowercase"):
        validate_password_strength("WEAKPASS@1234")


def test_password_strength_missing_special():
    """Must contain special character."""
    with pytest.raises(ValueError, match="special character"):
        validate_password_strength("WeakPass12345")

