import pytest
from pydantic import ValidationError

from app.core.config import DEVELOPMENT_SECRET_KEY, Settings


def test_production_rejects_development_secret():
    with pytest.raises(ValidationError, match="Production requires a unique SECRET_KEY"):
        Settings(ENVIRONMENT="production", SECRET_KEY=DEVELOPMENT_SECRET_KEY)


def test_production_rejects_short_secret():
    with pytest.raises(ValidationError, match="at least 32 characters"):
        Settings(ENVIRONMENT="production", SECRET_KEY="short-secret")


def test_production_accepts_configured_secret():
    settings = Settings(
        ENVIRONMENT="production",
        SECRET_KEY="this-is-a-long-unique-production-secret-value",
    )

    assert settings.is_production
