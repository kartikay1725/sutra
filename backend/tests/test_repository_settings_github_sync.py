import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient

from app.main import app
from app.api.dependencies import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.models.actor import Actor
from app.models.repository import Repository
from app.providers.base import ProviderBranch


@pytest.fixture
def mock_user_and_actor(db):
    user = User(
        id="user-settings-sync-test",
        email="settings_sync@example.com",
        username="testuser",
        password_hash="fakehashedpassword",
    )
    actor = Actor(
        id="user-settings-sync-test",
        name="testuser",
        type="user",
    )
    db.add(user)
    db.add(actor)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def client_authenticated(db, mock_user_and_actor):
    def override_get_current_user():
        return mock_user_and_actor

    def override_get_db():
        return db

    app.dependency_overrides[get_current_user] = override_get_current_user
    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)
    yield client
    app.dependency_overrides.pop(get_current_user, None)
    app.dependency_overrides.pop(get_db, None)


def test_github_repo_settings_update(db, client_authenticated, mock_user_and_actor):
    # Create a GitHub-connected repository in the database
    repo = Repository(
        id="repo-github-sync-001",
        owner_id=mock_user_and_actor.id,
        name="sync-repo",
        slug="sync-repo",
        provider_type="github",
        provider_owner="gh-org",
        default_branch="main",
        visibility="private",
        settings={"policies": {"require_task_linkage": True}},
        storage_key="mock/storage/sync-repo",
    )
    db.add(repo)
    db.commit()

    mock_provider = MagicMock()
    mock_provider.get_branch.return_value = ProviderBranch(
        name="develop",
        commit_sha="abcdef1234567890",
        is_protected=False,
    )
    mock_provider.update_repository.return_value = {"status": "updated"}

    with patch("app.api.repositories._get_github_repo_provider", return_value=mock_provider):
        # PATCH settings with provider_owner in the path
        res = client_authenticated.patch(
            "/v1/repositories/gh-org/sync-repo/settings",
            json={
                "description": "Updated GitHub integrated repo description",
                "default_branch": "develop",
                "settings": {
                    "policies": {
                        "require_ci_passed": True,
                    }
                },
            },
        )
        assert res.status_code == 200, res.text
        data = res.json()
        assert data["status"] == "ok"
        assert data["description"] == "Updated GitHub integrated repo description"
        assert data["default_branch"] == "develop"
        assert data["provider_type"] == "github"
        assert data["github_sync"]["synced"] is True
        assert data["settings"]["policies"]["require_ci_passed"] is True
        assert data["settings"]["policies"]["require_task_linkage"] is True

        # Verify provider methods were invoked
        mock_provider.get_branch.assert_called_with("gh-org", "sync-repo", "develop")
        assert mock_provider.update_repository.call_count >= 1


def test_github_repo_settings_rejects_nonexistent_branch(db, client_authenticated, mock_user_and_actor):
    repo = Repository(
        id="repo-github-sync-002",
        owner_id=mock_user_and_actor.id,
        name="sync-repo-invalid-branch",
        slug="sync-repo-invalid-branch",
        provider_type="github",
        provider_owner="gh-org",
        default_branch="main",
        visibility="private",
        settings={},
        storage_key="mock/storage/sync-repo-2",
    )
    db.add(repo)
    db.commit()

    mock_provider = MagicMock()
    mock_provider.get_branch.return_value = None
    mock_provider.list_branches.return_value = [
        ProviderBranch(name="main", commit_sha="111", is_protected=False)
    ]

    with patch("app.api.repositories._get_github_repo_provider", return_value=mock_provider):
        res = client_authenticated.patch(
            "/v1/repositories/gh-org/sync-repo-invalid-branch/settings",
            json={
                "default_branch": "nonexistent-branch",
            },
        )
        assert res.status_code == 400
        assert "does not exist on GitHub" in res.json()["detail"]


def test_github_repo_visibility_and_delete(db, client_authenticated, mock_user_and_actor):
    repo = Repository(
        id="repo-github-sync-003",
        owner_id=mock_user_and_actor.id,
        name="sync-repo-danger",
        slug="sync-repo-danger",
        provider_type="github",
        provider_owner="gh-org",
        default_branch="main",
        visibility="private",
        settings={},
        storage_key="mock/storage/sync-repo-3",
    )
    db.add(repo)
    db.commit()

    mock_provider = MagicMock()
    mock_provider.update_repository.return_value = {}
    mock_provider.delete_repository.return_value = True

    with patch("app.api.repositories._get_github_repo_provider", return_value=mock_provider):
        # Update visibility
        vis_res = client_authenticated.patch(
            "/v1/repositories/gh-org/sync-repo-danger/visibility",
            json={"visibility": "public"},
        )
        assert vis_res.status_code == 200
        assert vis_res.json()["visibility"] == "public"
        mock_provider.update_repository.assert_called_with("gh-org", "sync-repo-danger", is_private=False)

        # Delete repository
        del_res = client_authenticated.delete("/v1/repositories/gh-org/sync-repo-danger")
        assert del_res.status_code == 200
        assert del_res.json()["status"] == "deleted"
        mock_provider.delete_repository.assert_called_with("gh-org", "sync-repo-danger")
