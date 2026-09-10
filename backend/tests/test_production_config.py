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


def test_database_url_normalization_to_psycopg3():
    """
    Ensure standard postgres:// and postgresql:// connection strings
    (such as those provided by Supabase or Railway) are normalized to
    postgresql+psycopg:// to use Psycopg 3 without requiring psycopg2.
    """
    # 1. postgres:// scheme (common Supabase default)
    s1 = Settings(
        app_env="production",
        debug=False,
        jwt_secret="a" * 32,
        database_url="postgres://user:pass@db.supabase.co:5432/postgres",
        redis_url="redis://localhost:6379",
        event_integrity_key="b" * 32,
    )
    assert s1.database_url == "postgresql+psycopg://user:pass@db.supabase.co:5432/postgres"

    # 2. postgresql:// scheme (SQLAlchemy defaults to psycopg2 without explicit driver)
    s2 = Settings(
        app_env="production",
        debug=False,
        jwt_secret="a" * 32,
        database_url="postgresql://user:pass@db.supabase.co:5432/postgres",
        redis_url="redis://localhost:6379",
        event_integrity_key="b" * 32,
    )
    assert s2.database_url == "postgresql+psycopg://user:pass@db.supabase.co:5432/postgres"

    # 3. postgresql+psycopg:// scheme (already explicit, should remain unchanged)
    s3 = Settings(
        app_env="production",
        debug=False,
        jwt_secret="a" * 32,
        database_url="postgresql+psycopg://user:pass@localhost:5432/db",
        redis_url="redis://localhost:6379",
        event_integrity_key="b" * 32,
    )
    assert s3.database_url == "postgresql+psycopg://user:pass@localhost:5432/db"

    # 4. sqlite schemes should remain untouched
    s4 = Settings(
        app_env="development",
        debug=True,
        jwt_secret="weak",
        database_url="sqlite:///./test.db",
        redis_url="redis://localhost:6379",
        event_integrity_key="a" * 32,
    )
    assert s4.database_url == "sqlite:///./test.db"


def test_postgresql_engine_resolves_psycopg3_driver(monkeypatch):
    """
    Verify that an engine constructed with a normalized database_url resolves
    to dialect 'postgresql' with driver 'psycopg' (Psycopg 3), and functions
    even when psycopg2 is completely missing/unimportable.
    """
    import sys
    from sqlalchemy import create_engine

    # Simulate an environment where psycopg2 is NOT installed (like the production container)
    monkeypatch.setitem(sys.modules, "psycopg2", None)

    s = Settings(
        app_env="production",
        debug=False,
        jwt_secret="a" * 32,
        database_url="postgresql://user:pass@db.railway.app:5432/railway",
        redis_url="redis://localhost:6379",
        event_integrity_key="b" * 32,
    )

    # Engine construction must succeed and resolve dialect driver to psycopg
    engine = create_engine(s.database_url)
    assert engine.dialect.name == "postgresql"
    assert engine.dialect.driver == "psycopg"


def test_sutra_public_api_url_normalization_and_https_enforcement():
    """Verify that sutra_public_api_url is normalized and enforced to HTTPS in production."""
    # 1. Normalization of production origin
    s1 = Settings(
        app_env="production",
        debug=False,
        jwt_secret="a" * 32,
        database_url="postgresql+psycopg://user:pass@localhost:5432/db",
        redis_url="redis://localhost:6379",
        event_integrity_key="b" * 32,
        sutra_public_api_url="http://api.sutra.sudarshanai.com/",
    )
    assert s1.sutra_public_api_url == "https://api.sutra.sudarshanai.com"
    assert s1.get_public_api_url() == "https://api.sutra.sudarshanai.com"

    # 2. Rejects insecure HTTP public API URL in production
    with pytest.raises(ValueError, match="SUTRA_PUBLIC_API_URL must use HTTPS in production"):
        Settings(
            app_env="production",
            debug=False,
            jwt_secret="a" * 32,
            database_url="postgresql+psycopg://user:pass@localhost:5432/db",
            redis_url="redis://localhost:6379",
            event_integrity_key="b" * 32,
            sutra_public_api_url="http://custom-domain.example.com",
        )

    # 3. Default production canonical URL when sutra_public_api_url is None
    s3 = Settings(
        app_env="production",
        debug=False,
        jwt_secret="a" * 32,
        database_url="postgresql+psycopg://user:pass@localhost:5432/db",
        redis_url="redis://localhost:6379",
        event_integrity_key="b" * 32,
        sutra_public_api_url=None,
    )
    assert s3.get_public_api_url() == "https://api.sutra.sudarshanai.com"

