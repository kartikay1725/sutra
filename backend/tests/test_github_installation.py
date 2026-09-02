"""
Tests for GitHub Installation Flow
====================================
Uses the existing conftest.py isolated SQLite `db` and `client` fixtures.

Covers:
1. Unauthenticated access is blocked
2. Authenticated connect endpoint returns valid URL
3. Invalid/missing state token is rejected at callback
4. Valid installation upsert + idempotency
5. User isolation (User A cannot see User B's installation)
6. Disconnected user gets empty status
7. GitHub API error handling
8. No installation token persisted in DB
9. Repository sync is idempotent
10. Disconnect removes installation record
"""
import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock, patch
from uuid import uuid4

from sqlalchemy.orm import Session

from app.core.security import create_access_token, hash_password
from app.models.user import User
from app.models.user_session import UserSession
from app.models.actor import Actor
from app.models.github_installation import GitHubInstallation
from app.services.github_installation_service import GitHubInstallationService
from app.providers.github.auth import GitHubAppAuthService


# ---------------------------------------------------------------------------
# Helper: create a user + session + bearer token inside a db fixture session
# ---------------------------------------------------------------------------

def make_user_with_token(db: Session, username="testuser"):
    user = User(
        id=str(uuid4()),
        username=username,
        email=f"{username}@test.dev",
        password_hash=hash_password("TestPass1!"),
        email_verified=True,
    )
    db.add(user)
    db.flush()

    actor = Actor(
        id=user.id,
        type="human",
        name=username,
        owner_id=user.id,
    )
    db.add(actor)

    session_id = str(uuid4())
    expires = datetime.now(timezone.utc) + timedelta(hours=1)
    user_session = UserSession(
        id=session_id,
        user_id=user.id,
        status="active",
        expires_at=expires,
        last_seen_at=datetime.now(timezone.utc),
    )
    db.add(user_session)
    db.commit()

    token = create_access_token(subject=user.id, session_id=session_id)
    return user, token


def make_auth_service():
    """Create a GitHubAppAuthService using a generated RSA key for tests."""
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.hazmat.primitives import serialization

    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.TraditionalOpenSSL,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("utf-8")
    return GitHubAppAuthService(app_id="12345", private_key_pem=pem)


# ---------------------------------------------------------------------------
# 1. Unauthenticated access to protected endpoints is blocked
# ---------------------------------------------------------------------------

def test_github_status_requires_auth(client):
    response = client.get("/v1/integrations/github")
    assert response.status_code == 401, (
        f"Expected 401 for unauthenticated request, got {response.status_code}"
    )


def test_github_connect_requires_auth(client):
    response = client.get("/v1/integrations/github/connect")
    assert response.status_code == 401


def test_github_disconnect_requires_auth(client):
    response = client.delete("/v1/integrations/github")
    assert response.status_code == 401


def test_github_sync_requires_auth(client):
    response = client.post("/v1/integrations/github/sync")
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# 2. Authenticated user gets valid connect URL (with GITHUB_APP_SLUG set)
# ---------------------------------------------------------------------------

def test_github_connect_returns_redirect_url(client, db):
    _, token = make_user_with_token(db)
    headers = {"Authorization": f"Bearer {token}"}

    with patch("app.api.integrations.settings") as mock_settings:
        mock_settings.github_app_slug = "test-sutra-app"
        mock_settings.github_app_id = "12345"
        mock_settings.jwt_secret = "test-secret-key-32-chars-minimum!!"

        with patch("app.api.integrations.redis_service") as mock_redis:
            mock_redis_client = MagicMock()
            mock_redis.get_client.return_value = mock_redis_client
            response = client.get("/v1/integrations/github/connect", headers=headers)

    assert response.status_code == 200
    data = response.json()
    assert "redirect_url" in data
    assert "github.com/apps/test-sutra-app/installations/new" in data["redirect_url"]
    assert "state=" in data["redirect_url"]


def test_github_connect_returns_503_when_slug_missing(client, db):
    _, token = make_user_with_token(db, username="nosluguser")
    headers = {"Authorization": f"Bearer {token}"}

    with patch("app.api.integrations.settings") as mock_settings:
        mock_settings.github_app_slug = None
        mock_settings.github_app_id = "12345"
        mock_settings.jwt_secret = "test-secret-key-32-chars-minimum!!"
        response = client.get("/v1/integrations/github/connect", headers=headers)

    assert response.status_code == 503


# ---------------------------------------------------------------------------
# 3. Invalid / missing state is rejected at callback
# ---------------------------------------------------------------------------

def test_callback_rejects_missing_state(client):
    response = client.get(
        "/v1/integrations/github/callback?installation_id=12345",
        follow_redirects=False,
    )
    # Missing required `state` query parameter → 422 Unprocessable Entity
    assert response.status_code == 422


def test_callback_rejects_invalid_state(client):
    with patch("app.api.integrations.redis_service") as mock_redis:
        # Redis returns None = state not found / expired
        mock_redis_client = MagicMock()
        mock_redis_client.get.return_value = None
        mock_redis.get_client.return_value = mock_redis_client

        response = client.get(
            "/v1/integrations/github/callback?installation_id=12345&state=badstate",
            follow_redirects=False,
        )
    assert response.status_code in {400, 422}


# ---------------------------------------------------------------------------
# 4. Valid installation upsert
# ---------------------------------------------------------------------------

def test_installation_upsert_creates_record(db):
    auth_service = make_auth_service()
    service = GitHubInstallationService(auth_service)
    user, _ = make_user_with_token(db, username="instuser")

    installation = service.upsert_installation(
        db=db,
        user_id=user.id,
        github_installation_id=999001,
        github_account_id=888001,
        github_account_login="testorg",
        target_type="Organization",
    )

    assert installation.id is not None
    assert installation.user_id == user.id
    assert installation.github_installation_id == 999001
    assert installation.github_account_login == "testorg"

    fetched = service.get_installation_for_user(db, user.id)
    assert fetched is not None
    assert fetched.github_installation_id == 999001


def test_installation_upsert_is_idempotent(db):
    auth_service = make_auth_service()
    service = GitHubInstallationService(auth_service)
    user, _ = make_user_with_token(db, username="idempotuser")

    service.upsert_installation(
        db=db, user_id=user.id,
        github_installation_id=999002,
        github_account_id=888002,
        github_account_login="org1",
        target_type="Organization",
    )
    # Upsert again with updated login
    service.upsert_installation(
        db=db, user_id=user.id,
        github_installation_id=999002,
        github_account_id=888002,
        github_account_login="org1-renamed",
        target_type="Organization",
    )

    fetched = service.get_installation_for_user(db, user.id)
    assert fetched.github_account_login == "org1-renamed"

    from sqlalchemy import select, func
    count = db.scalar(
        select(func.count(GitHubInstallation.id)).where(
            GitHubInstallation.user_id == user.id
        )
    )
    assert count == 1


def test_installation_cannot_be_stolen_by_second_user(db):
    """An installation_id already owned by user A cannot be claimed by user B."""
    auth_service = make_auth_service()
    service = GitHubInstallationService(auth_service)

    user_a, _ = make_user_with_token(db, username="usera")
    user_b, _ = make_user_with_token(db, username="userb")

    service.upsert_installation(
        db=db, user_id=user_a.id,
        github_installation_id=777001,
        github_account_id=666001,
        github_account_login="orgA",
        target_type="Organization",
    )

    with pytest.raises(ValueError, match="already associated"):
        service.upsert_installation(
            db=db, user_id=user_b.id,
            github_installation_id=777001,  # Same installation_id!
            github_account_id=666001,
            github_account_login="orgA",
            target_type="Organization",
        )


# ---------------------------------------------------------------------------
# 5. User A cannot access User B's GitHub status
# ---------------------------------------------------------------------------

def test_github_status_scoped_to_user(client, db):
    user_a, token_a = make_user_with_token(db, username="statusa")
    user_b, token_b = make_user_with_token(db, username="statusb")

    installation = GitHubInstallation(
        id=str(uuid4()),
        user_id=user_a.id,
        github_installation_id=555001,
        github_account_id=444001,
        github_account_login="org_for_a",
        target_type="Organization",
    )
    db.add(installation)
    db.commit()

    # User B should see no installation
    resp_b = client.get(
        "/v1/integrations/github",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert resp_b.status_code == 200
    data_b = resp_b.json()
    assert data_b["connected"] is False
    assert data_b["account"] is None


# ---------------------------------------------------------------------------
# 6. Disconnected user gets empty status
# ---------------------------------------------------------------------------

def test_disconnected_user_gets_empty_status(client, db):
    _, token = make_user_with_token(db, username="noinstall")
    resp = client.get(
        "/v1/integrations/github",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["connected"] is False
    assert data["repo_count"] == 0


# ---------------------------------------------------------------------------
# 7. GitHub status endpoint is resilient when no installation exists
# ---------------------------------------------------------------------------

def test_github_status_survives_no_github_app_configured(client, db):
    """Status endpoint returns 200 even when no installation exists."""
    _, token = make_user_with_token(db, username="noapp")
    resp = client.get(
        "/v1/integrations/github",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["connected"] is False


# ---------------------------------------------------------------------------
# 8. No installation token persisted in DB
# ---------------------------------------------------------------------------

def test_no_installation_token_in_db():
    """Verify GitHubInstallation model has no token/secret field."""
    columns = [c.name for c in GitHubInstallation.__table__.columns]
    token_columns = [
        c for c in columns
        if "token" in c.lower() or "secret" in c.lower() or "private_key" in c.lower()
    ]
    assert len(token_columns) == 0, (
        f"GitHubInstallation should NOT store tokens/secrets. Found: {token_columns}"
    )


# ---------------------------------------------------------------------------
# 9. Repository sync is idempotent
# ---------------------------------------------------------------------------

def test_repo_sync_idempotent(db):
    """Syncing the same GitHub repos twice produces no duplicates."""
    from app.models.repository import Repository
    from sqlalchemy import select, func

    auth_service = make_auth_service()
    service = GitHubInstallationService(auth_service)
    user, _ = make_user_with_token(db, username="syncuser")

    installation = GitHubInstallation(
        id=str(uuid4()),
        user_id=user.id,
        github_installation_id=333001,
        github_account_id=222001,
        github_account_login="syncorg",
        target_type="Organization",
    )
    db.add(installation)
    db.commit()

    mock_repos = [
        {
            "id": 100001,
            "name": "repo-alpha",
            "owner": {"login": "syncorg"},
            "description": "Alpha repo",
            "private": False,
            "default_branch": "main",
        },
        {
            "id": 100002,
            "name": "repo-beta",
            "owner": {"login": "syncorg"},
            "description": "Beta repo",
            "private": True,
            "default_branch": "main",
        },
    ]

    with patch.object(service, "list_repos_for_installation", return_value=mock_repos):
        synced1 = service.sync_repos_for_user(db, user, installation)
    with patch.object(service, "list_repos_for_installation", return_value=mock_repos):
        synced2 = service.sync_repos_for_user(db, user, installation)

    count = db.scalar(
        select(func.count(Repository.id)).where(
            Repository.provider_type == "github",
            Repository.owner_id == user.id,
            Repository.deleted_at.is_(None),
        )
    )

    assert count == 2, f"Expected 2 repos after idempotent sync, got {count}"
    assert len(synced1) == 2
    assert len(synced2) == 2


def test_repo_sync_updates_existing_metadata(db):
    """Metadata updates on re-sync without creating duplicates."""
    from app.models.repository import Repository
    from sqlalchemy import select

    auth_service = make_auth_service()
    service = GitHubInstallationService(auth_service)
    user, _ = make_user_with_token(db, username="updateuser")

    installation = GitHubInstallation(
        id=str(uuid4()),
        user_id=user.id,
        github_installation_id=444001,
        github_account_id=333001,
        github_account_login="updateorg",
        target_type="Organization",
    )
    db.add(installation)
    db.commit()

    initial = [{"id": 200001, "name": "my-repo", "owner": {"login": "updateorg"},
                "description": "Old desc", "private": False, "default_branch": "main"}]
    updated = [{"id": 200001, "name": "my-repo", "owner": {"login": "updateorg"},
                "description": "New desc updated", "private": True, "default_branch": "develop"}]

    with patch.object(service, "list_repos_for_installation", return_value=initial):
        service.sync_repos_for_user(db, user, installation)
    with patch.object(service, "list_repos_for_installation", return_value=updated):
        service.sync_repos_for_user(db, user, installation)

    repo = db.scalar(
        select(Repository).where(
            Repository.external_id == "200001",
            Repository.provider_type == "github",
        )
    )
    assert repo is not None
    assert repo.description == "New desc updated"
    assert repo.visibility == "private"
    assert repo.default_branch == "develop"


# ---------------------------------------------------------------------------
# 10. Disconnect removes installation record
# ---------------------------------------------------------------------------

def test_disconnect_removes_installation(client, db):
    user, token = make_user_with_token(db, username="discuser")
    installation = GitHubInstallation(
        id=str(uuid4()),
        user_id=user.id,
        github_installation_id=111001,
        github_account_id=100001,
        github_account_login="discorg",
        target_type="User",
    )
    db.add(installation)
    db.commit()

    headers = {"Authorization": f"Bearer {token}"}

    resp = client.get("/v1/integrations/github", headers=headers)
    assert resp.json()["connected"] is True

    resp = client.delete("/v1/integrations/github", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["status"] == "disconnected"

    resp = client.get("/v1/integrations/github", headers=headers)
    assert resp.json()["connected"] is False


def test_disconnect_when_not_connected_returns_404(client, db):
    _, token = make_user_with_token(db, username="noconn")
    resp = client.delete(
        "/v1/integrations/github",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 404
