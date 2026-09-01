from datetime import datetime, timezone
from uuid import uuid4
import pytest
from fastapi import status

from app.models.actor import Actor
from app.models.agent import Agent
from app.models.change import Change
from app.models.change_review import ChangeReview
from app.models.pull_request import PullRequest
from app.models.repository import Repository
from app.models.user import User
from app.services.pull_request_service import PullRequestService
from app.services.repository_service import RepositoryService
from tests.conftest import ensure_test_actor


def setup_read_api_fixtures(db):
    user1 = User(
        id=str(uuid4()),
        username=f"read_user1_{uuid4().hex[:8]}",
        email=f"read1_{uuid4().hex[:8]}@example.com",
        password_hash="hash",
    )
    db.add(user1)

    user2 = User(
        id=str(uuid4()),
        username=f"read_user2_{uuid4().hex[:8]}",
        email=f"read2_{uuid4().hex[:8]}@example.com",
        password_hash="hash",
    )
    db.add(user2)
    db.flush()

    ensure_test_actor(db, user1)
    ensure_test_actor(db, user2)

    repo1 = RepositoryService(db).create(
        owner_id=user1.id,
        name=f"read_repo1_{uuid4().hex[:8]}",
        description="User 1 Repo",
        visibility="private",
    )

    repo2 = RepositoryService(db).create(
        owner_id=user2.id,
        name=f"read_repo2_{uuid4().hex[:8]}",
        description="User 2 Repo",
        visibility="private",
    )

    repo_deleted = RepositoryService(db).create(
        owner_id=user1.id,
        name=f"deleted_repo_{uuid4().hex[:8]}",
        description="Deleted Repo",
        visibility="private",
    )
    repo_deleted.deleted_at = datetime.now(timezone.utc)
    db.commit()

    agent1 = Agent(
        id=str(uuid4()),
        owner_id=user1.id,
        name="agent1",
        token_prefix="prefix1_12345",
        token_hash="hash",
        is_active=True,
        status="active",
    )
    db.add(agent1)

    actor1 = Actor(
        id=agent1.id,
        owner_id=user1.id,
        type="agent",
        name=agent1.name,
        capabilities='["repository.read", "repository.write", "change.create"]',
    )
    db.add(actor1)
    db.commit()

    change1 = Change(
        id=str(uuid4()),
        repository_id=repo1.id,
        actor_id=actor1.id,
        intent="Change 1",
        resulting_commit="1111111111111111111111111111111111111111",
        base_commit="0000000000000000000000000000000000000000",
        operation_key=(uuid4().hex * 2)[:64],
        status="proposed",
    )
    db.add(change1)

    change_del = Change(
        id=str(uuid4()),
        repository_id=repo_deleted.id,
        actor_id=actor1.id,
        intent="Deleted Repo Change",
        operation_key=(uuid4().hex * 2)[:64],
        status="proposed",
    )
    db.add(change_del)
    db.commit()

    review1 = ChangeReview(
        change_id=change1.id,
        requested_by=user1.id,
        reviewer_id=user2.id,
        status="approved",
        reason="Approved for testing",
    )
    db.add(review1)
    db.commit()

    svc = PullRequestService(db)
    pr1 = svc.create_pull_request(repo1.id, user1.id, change1.id, "PR 1", "main")
    pr_deleted = PullRequest(
        repository_id=repo_deleted.id,
        author_id=user1.id,
        source_change_id=change_del.id,
        title="Deleted PR",
        target_branch="main",
        status="open",
    )
    db.add(pr_deleted)
    db.commit()

    return user1, user2, repo1, repo2, repo_deleted, change1, pr1, pr_deleted, review1


def test_pr_read_unauthenticated_rejected(client):
    res1 = client.get(f"/v1/pull-requests/{uuid4()}")
    assert res1.status_code == status.HTTP_401_UNAUTHORIZED

    res2 = client.get("/v1/pull-requests")
    assert res2.status_code == status.HTTP_401_UNAUTHORIZED

    res3 = client.get(f"/v1/pull-requests/{uuid4()}/changes")
    assert res3.status_code == status.HTTP_401_UNAUTHORIZED

    res4 = client.get(f"/v1/pull-requests/{uuid4()}/reviews")
    assert res4.status_code == status.HTTP_401_UNAUTHORIZED


def test_pr_read_single_by_id_and_isolation(db, client):
    user1, user2, repo1, repo2, repo_deleted, change1, pr1, pr_deleted, review1 = setup_read_api_fixtures(db)

    from app.api.dependencies import get_current_user
    from app.main import app

    # Owner (user1) can read PR1
    app.dependency_overrides[get_current_user] = lambda: user1
    res1 = client.get(f"/v1/pull-requests/{pr1.id}")
    assert res1.status_code == status.HTTP_200_OK
    data1 = res1.json()
    assert data1["id"] == pr1.id
    assert data1["title"] == "PR 1"
    assert data1["repository_id"] == repo1.id
    assert data1["source_change_id"] == change1.id

    # Unauthorized user (user2) receives 404 (private repo isolation)
    app.dependency_overrides[get_current_user] = lambda: user2
    res2 = client.get(f"/v1/pull-requests/{pr1.id}")
    assert res2.status_code == status.HTTP_404_NOT_FOUND

    # Deleted repository PR cannot be accessed by owner (returns 404)
    app.dependency_overrides[get_current_user] = lambda: user1
    res_del = client.get(f"/v1/pull-requests/{pr_deleted.id}")
    assert res_del.status_code == status.HTTP_404_NOT_FOUND

    # Nonexistent PR returns 404
    res_non = client.get(f"/v1/pull-requests/{uuid4()}")
    assert res_non.status_code == status.HTTP_404_NOT_FOUND

    app.dependency_overrides.clear()


def test_pr_list_and_repository_filter(db, client):
    user1, user2, repo1, repo2, repo_deleted, change1, pr1, pr_deleted, review1 = setup_read_api_fixtures(db)

    from app.api.dependencies import get_current_user
    from app.main import app

    # User 1 lists all PRs -> gets only PR1 (PR of deleted repo is excluded)
    app.dependency_overrides[get_current_user] = lambda: user1
    res_all = client.get("/v1/pull-requests")
    assert res_all.status_code == status.HTTP_200_OK
    items = res_all.json()
    assert len(items) == 1
    assert items[0]["id"] == pr1.id

    # Filter by valid repository_id
    res_filter = client.get(f"/v1/pull-requests?repository_id={repo1.id}")
    assert res_filter.status_code == status.HTTP_200_OK
    assert len(res_filter.json()) == 1

    # Filter by unauthorized repository_id returns 403 Forbidden
    res_unauth = client.get(f"/v1/pull-requests?repository_id={repo2.id}")
    assert res_unauth.status_code == status.HTTP_403_FORBIDDEN

    # Malformed repository UUID parameter rejected with 404
    res_bad_uuid = client.get("/v1/pull-requests?repository_id=not-a-valid-uuid")
    assert res_bad_uuid.status_code == status.HTTP_404_NOT_FOUND

    # User 2 lists all PRs -> empty list (does not leak user1's private PRs)
    app.dependency_overrides[get_current_user] = lambda: user2
    res_u2 = client.get("/v1/pull-requests")
    assert res_u2.status_code == status.HTTP_200_OK
    assert len(res_u2.json()) == 0

    app.dependency_overrides.clear()


def test_pr_read_changes_endpoint(db, client):
    user1, user2, repo1, repo2, repo_deleted, change1, pr1, pr_deleted, review1 = setup_read_api_fixtures(db)

    from app.api.dependencies import get_current_user
    from app.main import app

    # Authorized user reads change
    app.dependency_overrides[get_current_user] = lambda: user1
    res_change = client.get(f"/v1/pull-requests/{pr1.id}/changes")
    assert res_change.status_code == status.HTTP_200_OK
    data = res_change.json()
    assert data["id"] == change1.id
    assert data["intent"] == "Change 1"
    assert data["repository_id"] == repo1.id

    # Unauthorized user receives 404
    app.dependency_overrides[get_current_user] = lambda: user2
    res_unauth = client.get(f"/v1/pull-requests/{pr1.id}/changes")
    assert res_unauth.status_code == status.HTTP_404_NOT_FOUND

    # Cross-repository mismatch safety check: if PR's change belongs to another repo, returns 404 safely
    change_mismatch = Change(
        id=str(uuid4()),
        repository_id=repo2.id,
        actor_id=user1.id,
        intent="Cross repo change",
        operation_key=(uuid4().hex * 2)[:64],
        status="proposed",
    )
    db.add(change_mismatch)

    pr_mismatch = PullRequest(
        repository_id=repo1.id,
        author_id=user1.id,
        source_change_id=change_mismatch.id,
        title="Mismatch PR",
        target_branch="main",
        status="open",
    )
    db.add(pr_mismatch)
    db.commit()

    app.dependency_overrides[get_current_user] = lambda: user1
    res_mis = client.get(f"/v1/pull-requests/{pr_mismatch.id}/changes")
    assert res_mis.status_code == status.HTTP_404_NOT_FOUND

    app.dependency_overrides.clear()


def test_pr_read_reviews_endpoint(db, client):
    user1, user2, repo1, repo2, repo_deleted, change1, pr1, pr_deleted, review1 = setup_read_api_fixtures(db)

    from app.api.dependencies import get_current_user
    from app.main import app

    # Authorized user reads reviews
    app.dependency_overrides[get_current_user] = lambda: user1
    res_rev = client.get(f"/v1/pull-requests/{pr1.id}/reviews")
    assert res_rev.status_code == status.HTTP_200_OK
    items = res_rev.json()
    assert len(items) == 1
    assert items[0]["id"] == review1.id
    assert items[0]["status"] == "approved"
    assert items[0]["reason"] == "Approved for testing"

    # Unauthorized user receives 404
    app.dependency_overrides[get_current_user] = lambda: user2
    res_unauth = client.get(f"/v1/pull-requests/{pr1.id}/reviews")
    assert res_unauth.status_code == status.HTTP_404_NOT_FOUND

    app.dependency_overrides.clear()
