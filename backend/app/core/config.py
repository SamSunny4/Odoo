import os
from typing import List
from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


DEVELOPMENT_SECRET_KEY = "insecure-change-in-production-brightloop-secret-key-32-chars-min"


class Settings(BaseSettings):
    PROJECT_NAME: str = "Brightloop Subscription Management"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True

    # Security & Auth
    SECRET_KEY: str = DEVELOPMENT_SECRET_KEY
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440  # 24 hours
    SESSION_COOKIE_NAME: str = "brightloop_session"
    SESSION_COOKIE_SECURE: bool = False
    SESSION_COOKIE_SAMESITE: str = "lax"
    TRUST_PROXY_HEADERS: bool = False

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT.lower() == "production"

    @property
    def effective_cookie_secure(self) -> bool:
        """Enforces Secure flag on session cookies in production, or when explicitly enabled."""
        return self.is_production or self.SESSION_COOKIE_SECURE

    @model_validator(mode="after")
    def validate_production_secret(self):
        """Reject the known development key and short keys in production."""
        if self.is_production and (
            self.SECRET_KEY == DEVELOPMENT_SECRET_KEY or len(self.SECRET_KEY) < 32
        ):
            raise ValueError(
                "Production requires a unique SECRET_KEY with at least 32 characters."
            )
        return self

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/brightloop_subscriptions"
    SYNC_DATABASE_URL: str = "postgresql://postgres:postgres@localhost:5432/brightloop_subscriptions"

    # Business Rules Defaults
    ORGANIZATION_CURRENCY: str = "USD"
    ORGANIZATION_TIMEZONE: str = "UTC"

    # Background Services
    REDIS_URL: str = "redis://localhost:6379/0"
    SMTP_HOST: str = "localhost"
    SMTP_PORT: int = 1025
    SMTP_FROM: str = "billing@brightloop.local"
    FRONTEND_URL: str = "http://localhost:5173"

    # CORS
    CORS_ORIGINS: str = "http://localhost:5173,http://localhost:3000"

    @property
    def cors_origins_list(self) -> List[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]

    _backend_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    _project_root = os.path.dirname(_backend_dir)

    model_config = SettingsConfigDict(
        env_file=[
            os.path.join(_project_root, ".env"),
            os.path.join(_backend_dir, ".env"),
        ],
        env_file_encoding="utf-8",
        extra="ignore"
    )


settings = Settings()

