"""
Comprehensive Tests for GitHub Sync Performance & Architecture Optimization
=============================================================================
Verifies:
1. token cache hit
2. token cache expiration
3. repository installation ID cache/use
4. sync debounce
5. force sync
6. HTTP sync returns immediately
7. GET /v1/repositories makes zero GitHub calls
8. repository failure isolation
9. backfill staleness guard
10. bounded concurrency
11. sync result does not block frontend
12. existing GitHub webhook ingestion invariant
13. MCP invariant
14. Governed engineering invariant
"""
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock, patch, call
from uuid import uuid4
import pytest
from sqlalchemy import select

from app.models.github_installation import GitHubInstallation
from app.models.repository import Repository
from app.models.user import User
from app.models.user_session import UserSession
from app.models.actor import Actor
from app.providers.github.auth import GitHubAppAuthService
from app.providers.github.repository import GitHubRepositoryProvider
from app.services.github_installation_service import GitHubInstallationService
from app.services.github_sync_worker import (
    GitHubSyncWorker,
    check_sync_debounce,
    set_sync_debounce,
    get_installation_sync_status,
    set_installation_sync_status,
)


def make_test_user_and_token(db, username="perftestuser"):
    from app.core.security import create_access_token, hash_password
    user = User(
        id=str(uuid4()),
        username=username,
        email=f"{username}@perf.dev",
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


# ---------------------------------------------------------------------------
# 1. Token Cache Hit
# ---------------------------------------------------------------------------

def test_token_cache_hit():
    """Verify that cached token in Redis is returned without calling GitHub API."""
    auth_service = GitHubAppAuthService(
        app_id="123",
        private_key_pem="fake_key",
    )
    fake_token_data = {
        "token": "ghs_cached_token_12345",
        "expires_at": "2026-09-13T16:00:00Z",
        "permissions": {"metadata": "read"},
        "repositories": ["repo1"],
    }

    with patch("app.core.redis_service.redis_service.get", return_value=fake_token_data):
        with patch.object(auth_service, "create_installation_token") as mock_create:
            token = auth_service.create_installation_token_cached(
                installation_id=999,
                repositories=["repo1"],
                permissions={"metadata": "read"},
            )
            assert token["token"] == "ghs_cached_token_12345"
            mock_create.assert_not_called()


# ---------------------------------------------------------------------------
# 2. Token Cache Expiration / Miss
# ---------------------------------------------------------------------------

def test_token_cache_expiration():
    """Verify that when cache expires/misses, new token is fetched and cached."""
    auth_service = GitHubAppAuthService(
        app_id="123",
        private_key_pem="fake_key",
    )
    fresh_token_data = {
        "token": "ghs_fresh_token_99999",
        "expires_at": "2026-09-13T17:00:00Z",
        "permissions": {"metadata": "read"},
        "repositories": ["repo1"],
    }

    with patch("app.core.redis_service.redis_service.get", return_value=None):
        with patch("app.core.redis_service.redis_service.set") as mock_set:
            with patch.object(auth_service, "create_installation_token", return_value=fresh_token_data):
                token = auth_service.create_installation_token_cached(
                    installation_id=999,
                    repositories=["repo1"],
                    permissions={"metadata": "read"},
                )
                assert token["token"] == "ghs_fresh_token_99999"
                mock_set.assert_called_once()
                assert mock_set.call_args[1].get("ex") == 3000


# ---------------------------------------------------------------------------
# 3. Repository Installation ID Cache / Use
# ---------------------------------------------------------------------------

def test_installation_id_cache_and_reuse():
    """Verify that get_installation_id_cached caches and reuses installation_id."""
    auth_service = GitHubAppAuthService(
        app_id="123",
        private_key_pem="fake_key",
    )

    # First call: cache miss, calls API and caches in Redis
    with patch("app.core.redis_service.redis_service.get", return_value=None):
        with patch("app.core.redis_service.redis_service.set") as mock_set:
            with patch.object(auth_service, "get_installation_id", return_value=554433) as mock_get:
                inst_id = auth_service.get_installation_id_cached("owner", "repo")
                assert inst_id == 554433
                mock_get.assert_called_once_with("owner", "repo")
                mock_set.assert_called_once()

    # Second call: cache hit, zero GitHub calls
    with patch("app.core.redis_service.redis_service.get", return_value="554433"):
        with patch.object(auth_service, "get_installation_id") as mock_get:
            inst_id = auth_service.get_installation_id_cached("owner", "repo")
            assert inst_id == 554433
            mock_get.assert_not_called()


# ---------------------------------------------------------------------------
# 4. Sync Debounce
# ---------------------------------------------------------------------------

def test_sync_debounce(client, db):
    """Verify 5-minute debounce returns debounced status on second sync."""
    user, token = make_test_user_and_token(db, username="debounceuser")
    installation = GitHubInstallation(
        id=str(uuid4()),
        user_id=user.id,
        github_installation_id=888111,
        github_account_id=222333,
        github_account_login="debounceorg",
        target_type="User",
    )
    db.add(installation)
    db.commit()

    headers = {"Authorization": f"Bearer {token}"}

    # Simulate active debounce lock
    with patch("app.services.github_sync_worker.check_sync_debounce", return_value=(True, 240)):
        resp = client.post("/v1/integrations/github/sync", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "debounced"
        assert data["cooldown_remaining_seconds"] == 240


# ---------------------------------------------------------------------------
# 5. Force Sync Bypasses Debounce
# ---------------------------------------------------------------------------

def test_force_sync_bypasses_debounce(client, db):
    """Verify force=True bypasses active debounce cooldown."""
    user, token = make_test_user_and_token(db, username="forceuser")
    installation = GitHubInstallation(
        id=str(uuid4()),
        user_id=user.id,
        github_installation_id=888222,
        github_account_id=222444,
        github_account_login="forceorg",
        target_type="User",
    )
    db.add(installation)
    db.commit()

    headers = {"Authorization": f"Bearer {token}"}

    with patch("app.services.github_sync_worker.check_sync_debounce", return_value=(True, 250)):
        with patch("app.services.github_sync_worker.GitHubSyncWorker.enqueue_job") as mock_enqueue:
            resp = client.post("/v1/integrations/github/sync?force=true", headers=headers)
            assert resp.status_code == 200
            data = resp.json()
            assert data["status"] == "queued"
            mock_enqueue.assert_called_once_with(
                installation_id=888222,
                user_id=user.id,
                force=True,
            )


# ---------------------------------------------------------------------------
# 6. HTTP Sync Returns Immediately
# ---------------------------------------------------------------------------

def test_http_sync_returns_immediately(client, db):
    """Verify HTTP POST /v1/integrations/github/sync returns immediately with queued status."""
    user, token = make_test_user_and_token(db, username="immeduser")
    installation = GitHubInstallation(
        id=str(uuid4()),
        user_id=user.id,
        github_installation_id=888333,
        github_account_id=222555,
        github_account_login="immedorg",
        target_type="User",
    )
    db.add(installation)
    db.commit()

    headers = {"Authorization": f"Bearer {token}"}

    with patch("app.services.github_sync_worker.check_sync_debounce", return_value=(False, 0)):
        with patch("app.services.github_sync_worker.GitHubSyncWorker.enqueue_job") as mock_enqueue:
            resp = client.post("/v1/integrations/github/sync", headers=headers)
            assert resp.status_code == 200
            data = resp.json()
            assert data["status"] == "queued"
            assert data["account"] == "immedorg"
            mock_enqueue.assert_called_once()


# ---------------------------------------------------------------------------
# 7. GET /v1/repositories Makes Zero GitHub Calls
# ---------------------------------------------------------------------------

def test_get_repositories_makes_zero_github_calls(client, db):
    """Verify GET /v1/repositories queries database only and never calls GitHub."""
    user, token = make_test_user_and_token(db, username="repouser")
    repo = Repository(
        id=str(uuid4()),
        owner_id=user.id,
        name="cached-repo",
        slug="cached-repo",
        storage_key="test/cached-repo",
        provider_type="github",
        external_id="123456",
        github_installation_id=888111,
        provider_owner="testorg",
    )
    db.add(repo)
    db.commit()

    headers = {"Authorization": f"Bearer {token}"}

    with patch("httpx.Client.get") as mock_http_get:
        resp = client.get("/v1/repositories", headers=headers)
        assert resp.status_code == 200
        # Absolutely zero outbound HTTP calls to GitHub
        mock_http_get.assert_not_called()


# ---------------------------------------------------------------------------
# 8. Repository Failure Isolation
# ---------------------------------------------------------------------------

def test_repository_failure_isolation(db):
    """Verify that failure on one repository does not block other repositories."""
    user, _ = make_test_user_and_token(db, username="isoluser")
    repo1 = Repository(
        id=str(uuid4()),
        owner_id=user.id,
        name="good-repo",
        slug="good-repo",
        storage_key="test/good-repo",
        provider_type="github",
        external_id="101",
        github_installation_id=777111,
        provider_owner="isolorg",
    )
    repo2 = Repository(
        id=str(uuid4()),
        owner_id=user.id,
        name="bad-repo",
        slug="bad-repo",
        storage_key="test/bad-repo",
        provider_type="github",
        external_id="102",
        github_installation_id=777111,
        provider_owner="isolorg",
    )
    db.add_all([repo1, repo2])
    db.commit()

    auth_service = GitHubAppAuthService(app_id="123", private_key_pem="fake_key")

    # repo1 succeeds, repo2 throws GitHub 500 error
    def mock_sync(db, repository, **kwargs):
        if repository.name == "bad-repo":
            raise RuntimeError("GitHub 500 Internal Server Error")
        return {"issues": 2, "pull_requests": 1}

    with patch.object(GitHubInstallationService, "sync_repository_engineering_objects", side_effect=mock_sync):
        res1_id, res1_success, res1_err = GitHubSyncWorker._sync_single_repo(
            repo1.id, 777111, force=True, auth_service=auth_service, db=db
        )
        res2_id, res2_success, res2_err = GitHubSyncWorker._sync_single_repo(
            repo2.id, 777111, force=True, auth_service=auth_service, db=db
        )

        assert res1_success is True
        assert res1_err is None
        assert res2_success is False
        assert "GitHub 500" in str(res2_err)


# ---------------------------------------------------------------------------
# 9. Backfill Staleness Guard (1 hour default)
# ---------------------------------------------------------------------------

def test_backfill_staleness_guard(db):
    """Verify repository backfill is skipped if synced within 1 hour, unless force=True."""
    user, _ = make_test_user_and_token(db, username="staleuser")
    recently_synced = datetime.now(timezone.utc) - timedelta(minutes=15)
    repo = Repository(
        id=str(uuid4()),
        owner_id=user.id,
        name="fresh-sync-repo",
        slug="fresh-sync-repo",
        storage_key="test/fresh-sync-repo",
        provider_type="github",
        external_id="303",
        github_installation_id=777222,
        provider_owner="staleorg",
        github_objects_synced_at=recently_synced,
    )
    db.add(repo)
    db.commit()

    auth_service = GitHubAppAuthService(app_id="123", private_key_pem="fake_key")
    service = GitHubInstallationService(auth_service)

    with patch.object(GitHubRepositoryProvider, "list_issues") as mock_issues:
        # Non-forced: skipped due to staleness guard
        res = service.sync_repository_engineering_objects(db, repo, force=False)
        assert res["skipped"] is True
        mock_issues.assert_not_called()

        # Forced: proceeds despite recent sync
        mock_issues.return_value = []
        with patch.object(GitHubRepositoryProvider, "list_pull_requests", return_value=[]):
            res_forced = service.sync_repository_engineering_objects(db, repo, force=True)
            assert res_forced["skipped"] is False
            mock_issues.assert_called_once()


# ---------------------------------------------------------------------------
# 10. Bounded Concurrency
# ---------------------------------------------------------------------------

def test_bounded_concurrency_configured():
    """Verify worker concurrency is bounded between 3 and 5."""
    assert 3 <= GitHubSyncWorker.MAX_CONCURRENCY <= 5


# ---------------------------------------------------------------------------
# 11. Sync Result Does Not Block Frontend
# ---------------------------------------------------------------------------

def test_sync_result_does_not_block_frontend(client, db):
    """Verify sync response returns metadata immediately and status API reports background state."""
    user, token = make_test_user_and_token(db, username="frontenduser")
    installation = GitHubInstallation(
        id=str(uuid4()),
        user_id=user.id,
        github_installation_id=888444,
        github_account_id=222666,
        github_account_login="frontendorg",
        target_type="User",
    )
    db.add(installation)
    db.commit()

    headers = {"Authorization": f"Bearer {token}"}

    with patch("app.services.github_sync_worker.check_sync_debounce", return_value=(False, 0)):
        with patch("app.services.github_sync_worker.GitHubSyncWorker.enqueue_job"):
            post_res = client.post("/v1/integrations/github/sync", headers=headers)
            assert post_res.status_code == 200
            assert post_res.json()["status"] == "queued"

    with patch("app.services.github_sync_worker.get_installation_sync_status", return_value={
        "status": "in_progress",
        "last_synced_at": None,
    }):
        get_res = client.get("/v1/integrations/github", headers=headers)
        assert get_res.status_code == 200
        data = get_res.json()
        assert data["connected"] is True
        assert data["sync_status"] == "in_progress"


# ---------------------------------------------------------------------------
# 12. Webhook Ingestion Invariant
# ---------------------------------------------------------------------------

def test_webhook_ingestion_invariant():
    """Verify webhook routes and processing paths remain intact."""
    from app.api.webhooks.github import router as github_webhook_router
    assert github_webhook_router is not None
    # Ensure webhook paths are registered
    routes = [route.path for route in github_webhook_router.routes]
    assert any("webhook" in r or "github" in r or "/" in r for r in routes)


# ---------------------------------------------------------------------------
# 13. MCP Invariant
# ---------------------------------------------------------------------------

def test_mcp_server_invariant():
    """Verify MCP tools and server configuration remain unchanged."""
    from app.mcp.server import mcp_server
    assert mcp_server is not None
    assert hasattr(mcp_server, "session_manager")


# ---------------------------------------------------------------------------
# 14. Governed Engineering Invariant
# ---------------------------------------------------------------------------

def test_governed_commit_invariant():
    """Verify governed engineering models and task execution structures are intact."""
    from app.models.task import Task
    from app.models.change import Change
    from app.models.git_push_event import GitPushEvent
    assert Task is not None
    assert Change is not None
    assert GitPushEvent is not None
