import pytest
from pydantic import ValidationError
from app.core.config import Settings

def test_development_config_allows_weak_secrets():
    # Should not raise
    Settings(
        app_env="development",
        debug=True,
        jwt_secret="weak",
        database_url="sqlite:///:memory:",
        redis_url="redis://localhost:6379",
        event_integrity_key="a" * 32,
    )

def test_production_config_rejects_debug_true():
    with pytest.raises(ValidationError, match="DEBUG must be False in production"):
        Settings(
            app_env="production",
            debug=True,
            jwt_secret="a" * 32,
            database_url="sqlite:///:memory:",
            redis_url="redis://localhost:6379",
            event_integrity_key="a" * 32,
        )

def test_production_config_rejects_weak_jwt():
    with pytest.raises(ValidationError, match="JWT secret must be at least 32 characters in production"):
        Settings(
            app_env="production",
            debug=False,
            jwt_secret="weak",
            database_url="sqlite:///:memory:",
            redis_url="redis://localhost:6379",
            event_integrity_key="a" * 32,
        )

def test_production_config_requires_strong_integrity_key():
    with pytest.raises(ValidationError):
        # event_integrity_key must always be 32 chars, even in dev
        Settings(
            app_env="development",
            debug=True,
            jwt_secret="weak",
            database_url="sqlite:///:memory:",
            redis_url="redis://localhost:6379",
            event_integrity_key="weak",
        )

def test_valid_production_config_succeeds():
    s = Settings(
        app_env="production",
        debug=False,
        jwt_secret="a" * 32,
        database_url="postgresql+psycopg://sutra:sutra_dev_password@localhost:55432/sutra",
        redis_url="redis://localhost:6379",
        event_integrity_key="b" * 32,
    )
    assert s.app_env == "production"
    assert s.debug is False


def test_production_config_redacts_secrets_in_repr():
    s = Settings(
        app_env="production",
        debug=False,
        jwt_secret="super-secret-jwt-key-minimum-32-chars",
        database_url="postgresql+psycopg://user:pass@localhost:5432/db",
        redis_url="redis://localhost:6379",
        event_integrity_key="super-secret-integrity-key-32-chars",
    )
    repr_str = repr(s)
    assert "[REDACTED]" in repr_str
    assert "super-secret-jwt-key" not in repr_str
    assert "pass@localhost" not in repr_str
