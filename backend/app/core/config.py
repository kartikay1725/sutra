import os
from functools import lru_cache
from pathlib import Path
from typing import Any

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

CANONICAL_PRODUCTION_API_URL: str = "https://api.sutra.sudarshanai.com"


class Settings(BaseSettings):
    app_name: str = "SUTRA"
    app_env: str = "development"
    debug: bool = True

    database_url: str
    redis_url: str

    @field_validator("database_url")
    @classmethod
    def normalize_database_url(cls, v: str) -> str:
        """
        Normalize PostgreSQL database URLs to use the Psycopg 3 dialect.

        SQLAlchemy 2.x defaults 'postgresql://' to 'postgresql+psycopg2://'.
        Cloud providers (Supabase, Railway, Render, Heroku) supply connection
        strings starting with 'postgres://' or 'postgresql://'.
        Since SUTRA declares psycopg 3 ('psycopg[binary]>=3.2,<4') rather than
        psycopg2, normalize these schemes to 'postgresql+psycopg://' so
        SQLAlchemy selects the Psycopg 3 DBAPI driver consistently.
        """
        if v.startswith("postgres://"):
            return "postgresql+psycopg://" + v[len("postgres://"):]
        if v.startswith("postgresql://"):
            return "postgresql+psycopg://" + v[len("postgresql://"):]
        return v

    jwt_secret: str
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60

    # ---------------------------------------------------------
    # EVENT INTEGRITY
    #
    # This secret MUST NOT be stored in PostgreSQL.
    #
    # HMAC-SHA256 is used to authenticate persisted Git events.
    # Minimum recommended size: 32 random bytes.
    # ---------------------------------------------------------

    event_integrity_key: str = Field(
        min_length=32,
    )

    repository_storage_path: str = "./data/repositories"
    sutra_base_url: str = "http://localhost:8000"
    sutra_public_api_url: str | None = None
    cors_origins: str = "http://localhost:3000"

    @field_validator("sutra_public_api_url")
    @classmethod
    def normalize_public_api_url(cls, v: str | None) -> str | None:
        if v is None:
            return None
        v = v.strip().rstrip("/")
        if not v:
            return None
        if "api.sutra.sudarshanai.com" in v:
            return CANONICAL_PRODUCTION_API_URL
        return v

    # ---------------------------------------------------------
    # GITHUB SUBSTRATE & APP INTEGRATION
    # ---------------------------------------------------------
    github_app_id: str | None = None
    github_private_key_pem: str | None = None
    github_webhook_secret: str | None = None
    github_test_repo_owner: str | None = None
    github_test_repo_name: str | None = None
    github_api_base_url: str = "https://api.github.com"
    # GitHub App slug — used to build the installation URL:
    # https://github.com/apps/{github_app_slug}/installations/new
    # Find this on GitHub → Settings → Developer settings → GitHub Apps → your app
    github_app_slug: str | None = None

    groq_api_key: str = Field(min_length=1,)

    worker_enabled: bool = True

    worker_interval_seconds: float = 2.0
    worker_batch_size: int = 100
    worker_stale_timeout_seconds: int = 300

    worker_max_attempts: int = Field(default=5, ge=1)
    worker_retry_base_delay_seconds: float = 2.0
    worker_retry_max_delay_seconds: float = 3600.0

    # ---------------------------------------------------------
    # EMAIL & AUTHENTICATION SETTINGS
    # ---------------------------------------------------------
    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_username: str | None = None
    smtp_password: str | None = None
    smtp_use_tls: bool = True
    email_sender: str = "no-reply@sutra.dev"

    otp_expire_minutes: int = 10
    otp_resend_cooldown_seconds: int = 60
    otp_max_attempts: int = 5

    password_reset_expire_minutes: int = 15
    password_reset_cooldown_seconds: int = 60
    password_reset_max_attempts: int = 5

    frontend_base_url: str = "http://localhost:3000"
    rate_limit_enabled: bool = True

    # ---------------------------------------------------------
    # REDIS BETA RATE LIMITS
    # ---------------------------------------------------------
    rate_limit_register_per_hour: int = 30
    rate_limit_login_per_minute: int = 5
    rate_limit_otp_verify_per_10min: int = 30
    rate_limit_otp_resend_cooldown_seconds: int = 60
    rate_limit_forgot_password_per_hour: int = 20
    rate_limit_reset_password_per_hour: int = 20
    rate_limit_agent_register_per_hour: int = 20
    rate_limit_agent_session_per_15min: int = 30
    rate_limit_agent_poll_per_minute: int = 120
    rate_limit_temp_push_token_per_hour: int = 30

    _PROJECT_ROOT = Path(
        os.environ.get(
            "SUTRA_PROJECT_ROOT",
            Path(__file__).resolve().parents[2],
        )
    )

    _ENV_FILE = _PROJECT_ROOT / ".env"

    model_config = SettingsConfigDict(
        env_file=str(_ENV_FILE),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def cors_origin_list(self) -> list[str]:
        return [
            origin.strip()
            for origin in self.cors_origins.split(",")
            if origin.strip()
        ]

    INSECURE_DEFAULTS: set[str] = {
        "dev-secret-key-change-in-production",
        "insecure-default-jwt-secret-key-32-chars-long",
        "dev-event-integrity-key-32-bytes-long",
        "secret",
        "password",
    }

    @model_validator(mode="after")
    def validate_production_security(self) -> 'Settings':
        if self.app_env.lower() in ("production", "prod", "staging"):
            if self.debug:
                raise ValueError("DEBUG must be False in production")
            if len(self.jwt_secret) < 32:
                raise ValueError("JWT secret must be at least 32 characters in production")
            if self.jwt_secret in self.INSECURE_DEFAULTS:
                raise ValueError("Insecure default JWT secret cannot be used in production")
            if len(self.event_integrity_key) < 32:
                raise ValueError("Event integrity key must be at least 32 characters in production")
            if self.event_integrity_key in self.INSECURE_DEFAULTS:
                raise ValueError("Insecure default event integrity key cannot be used in production")
            if self.sutra_public_api_url and not self.sutra_public_api_url.startswith("https://"):
                raise ValueError("SUTRA_PUBLIC_API_URL must use HTTPS in production")
        return self

    def get_public_api_url(self, request: Any = None) -> str:
        """
        Return the canonical public API origin without trailing slash.

        Resolution Priority:
        1. Explicitly configured sutra_public_api_url (e.g. SUTRA_PUBLIC_API_URL env var).
        2. Production or staging environment: always return CANONICAL_PRODUCTION_API_URL.
        3. If request is provided and the host (or X-Forwarded-Host) is api.sutra.sudarshanai.com,
           always return CANONICAL_PRODUCTION_API_URL.
        4. In local development / test environments:
           - If request is provided, derive from request.base_url (e.g. http://localhost:8000).
           - Otherwise, fallback to sutra_base_url.
        """
        if self.sutra_public_api_url:
            return self.sutra_public_api_url.rstrip("/")

        if self.app_env.lower() in ("production", "prod", "staging"):
            return CANONICAL_PRODUCTION_API_URL

        if request is not None:
            try:
                host = request.headers.get("host", "").split(":")[0].lower()
                if host == "api.sutra.sudarshanai.com":
                    return CANONICAL_PRODUCTION_API_URL
                f_host = request.headers.get("x-forwarded-host", "").split(":")[0].lower()
                if f_host == "api.sutra.sudarshanai.com":
                    return CANONICAL_PRODUCTION_API_URL
                return str(request.base_url).rstrip("/")
            except Exception:
                pass

        return self.sutra_base_url.rstrip("/")

    def __repr__(self) -> str:
        return f"<Settings app_name={self.app_name!r} app_env={self.app_env!r} debug={self.debug} database_url='[REDACTED]' jwt_secret='[REDACTED]'>"

    def __str__(self) -> str:
        return repr(self)


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()