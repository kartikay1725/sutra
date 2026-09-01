from datetime import datetime, timezone
from uuid import uuid4
import pytest
from fastapi import status

from app.models.actor import Actor
from app.models.agent import Agent
from app.models.change import Change
from app.models.change_file import ChangeFile
from app.models.pull_request import PullRequest
from app.models.repository import Repository
from app.models.user import User
from app.services.conflict_service import ConflictResult, ConflictService
from app.services.pull_request_service import PullRequestService
from app.services.repository_service import RepositoryService
from tests.conftest import ensure_test_actor


def setup_conflict_fixtures(db):
    user1 = User(
        id=str(uuid4()),
        username=f"conf_user1_{uuid4().hex[:8]}",
        email=f"conf1_{uuid4().hex[:8]}@example.com",
        password_hash="hash",
    )
    db.add(user1)

    user2 = User(
        id=str(uuid4()),
        username=f"conf_user2_{uuid4().hex[:8]}",
        email=f"conf2_{uuid4().hex[:8]}@example.com",
        password_hash="hash",
    )
    db.add(user2)
    db.flush()

    ensure_test_actor(db, user1)
    ensure_test_actor(db, user2)

    repo1 = RepositoryService(db).create(
        owner_id=user1.id,
        name=f"conf_repo1_{uuid4().hex[:8]}",
        description="Conflict Test Repo 1",
        visibility="private",
    )

    repo2 = RepositoryService(db).create(
        owner_id=user2.id,
        name=f"conf_repo2_{uuid4().hex[:8]}",
        description="Conflict Test Repo 2",
        visibility="private",
    )

    repo_del = RepositoryService(db).create(
        owner_id=user1.id,
        name=f"conf_repo_del_{uuid4().hex[:8]}",
        description="Deleted Repo",
        visibility="private",
    )
    repo_del.deleted_at = datetime.now(timezone.utc)
    db.commit()

    agent1 = Agent(
        id=str(uuid4()),
        owner_id=user1.id,
        name="agent1",
        token_prefix="prefix_conf_123",
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

    # Base change with resulting commit
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

    change_no_commit = Change(
        id=str(uuid4()),
        repository_id=repo1.id,
        actor_id=actor1.id,
        intent="Change No Commit",
        operation_key=(uuid4().hex * 2)[:64],
        status="proposed",
    )
    db.add(change_no_commit)

    change_del = Change(
        id=str(uuid4()),
        repository_id=repo_del.id,
        actor_id=actor1.id,
        intent="Change Deleted Repo",
        operation_key=(uuid4().hex * 2)[:64],
        status="proposed",
    )
    db.add(change_del)
    db.commit()

    svc = PullRequestService(db)
    pr1 = svc.create_pull_request(repo1.id, user1.id, change1.id, "PR 1", "main")
    pr_no_commit = svc.create_pull_request(repo1.id, user1.id, change_no_commit.id, "PR No Commit", "main")
    pr_del = PullRequest(
        repository_id=repo_del.id,
        author_id=user1.id,
        source_change_id=change_del.id,
        title="PR Deleted",
        target_branch="main",
        status="open",
    )
    db.add(pr_del)
    db.commit()

    return user1, user2, repo1, repo2, repo_del, actor1, change1, change_no_commit, pr1, pr_no_commit, pr_del


def test_pr_conflict_endpoint_success_no_conflict(db, client):
    user1, user2, repo1, repo2, repo_del, actor1, change1, change_no_commit, pr1, pr_no_commit, pr_del = setup_conflict_fixtures(db)

    from app.api.dependencies import get_current_user
    from app.main import app

    app.dependency_overrides[get_current_user] = lambda: user1

    res = client.get(f"/v1/pull-requests/{pr1.id}/conflicts")
    assert res.status_code == status.HTTP_200_OK
    data = res.json()
    assert data["level"] == "none"
    assert "reason" in data
    assert isinstance(data["paths"], list)
    assert isinstance(data["related_change_ids"], list)

    app.dependency_overrides.clear()


def test_pr_conflict_missing_resulting_commit(db, client):
    user1, user2, repo1, repo2, repo_del, actor1, change1, change_no_commit, pr1, pr_no_commit, pr_del = setup_conflict_fixtures(db)

    from app.api.dependencies import get_current_user
    from app.main import app

    app.dependency_overrides[get_current_user] = lambda: user1

    # Recorded change without resulting commit to compare against
    recorded_change = Change(
        id=str(uuid4()),
        repository_id=repo1.id,
        actor_id=actor1.id,
        intent="Recorded Change No Commit",
        operation_key=(uuid4().hex * 2)[:64],
        status="recorded",
    )
    db.add(recorded_change)

    f1 = ChangeFile(change_id=change_no_commit.id, path="src/file.py", operation="modify")
    f2 = ChangeFile(change_id=recorded_change.id, path="src/file.py", operation="modify")
    db.add_all([f1, f2])
    db.commit()

    res = client.get(f"/v1/pull-requests/{pr_no_commit.id}/conflicts")
    assert res.status_code == status.HTTP_200_OK
    data = res.json()
    assert data["level"] == "potential_conflict"
    assert "resulting commit" in data["reason"].lower()

    app.dependency_overrides.clear()


def test_pr_conflict_private_repository_isolation_and_idor(db, client):
    user1, user2, repo1, repo2, repo_del, actor1, change1, change_no_commit, pr1, pr_no_commit, pr_del = setup_conflict_fixtures(db)

    from app.api.dependencies import get_current_user
    from app.main import app

    # Unauthorized user (user2) requesting user1's private repo PR conflicts returns 404
    app.dependency_overrides[get_current_user] = lambda: user2
    res_unauth = client.get(f"/v1/pull-requests/{pr1.id}/conflicts")
    assert res_unauth.status_code == status.HTTP_404_NOT_FOUND

    app.dependency_overrides.clear()


def test_pr_conflict_deleted_repo_and_malformed_id(db, client):
    user1, user2, repo1, repo2, repo_del, actor1, change1, change_no_commit, pr1, pr_no_commit, pr_del = setup_conflict_fixtures(db)

    from app.api.dependencies import get_current_user
    from app.main import app

    app.dependency_overrides[get_current_user] = lambda: user1

    # Deleted repo PR returns 404
    res_del = client.get(f"/v1/pull-requests/{pr_del.id}/conflicts")
    assert res_del.status_code == status.HTTP_404_NOT_FOUND

    # Malformed UUID returns 404
    res_bad = client.get("/v1/pull-requests/invalid-uuid-string/conflicts")
    assert res_bad.status_code == status.HTTP_404_NOT_FOUND

    app.dependency_overrides.clear()


def test_pr_conflict_cross_repository_invariant_violation(db, client):
    user1, user2, repo1, repo2, repo_del, actor1, change1, change_no_commit, pr1, pr_no_commit, pr_del = setup_conflict_fixtures(db)

    from app.api.dependencies import get_current_user
    from app.main import app

    app.dependency_overrides[get_current_user] = lambda: user1

    # Mismatched Change belonging to repo2 attached to PR in repo1
    mismatch_change = Change(
        id=str(uuid4()),
        repository_id=repo2.id,
        actor_id=user1.id,
        intent="Mismatch Change",
        operation_key=(uuid4().hex * 2)[:64],
        status="proposed",
    )
    db.add(mismatch_change)

    mismatch_pr = PullRequest(
        repository_id=repo1.id,
        author_id=user1.id,
        source_change_id=mismatch_change.id,
        title="Mismatch PR",
        target_branch="main",
        status="open",
    )
    db.add(mismatch_pr)
    db.commit()

    res_mis = client.get(f"/v1/pull-requests/{mismatch_pr.id}/conflicts")
    assert res_mis.status_code == status.HTTP_404_NOT_FOUND

    app.dependency_overrides.clear()


def test_pr_conflict_safe_path_normalization(db):
    user1, user2, repo1, repo2, repo_del, actor1, change1, change_no_commit, pr1, pr_no_commit, pr_del = setup_conflict_fixtures(db)

    recorded_change = Change(
        id=str(uuid4()),
        repository_id=repo1.id,
        actor_id=actor1.id,
        intent="Recorded Change for Overlap",
        resulting_commit="2222222222222222222222222222222222222222",
        base_commit="0000000000000000000000000000000000000000",
        operation_key=(uuid4().hex * 2)[:64],
        status="recorded",
    )
    db.add(recorded_change)

    # Path normalization check for backslashes in ChangeFile path
    f1 = ChangeFile(change_id=change1.id, path="src/file.py", operation="modify")
    f2 = ChangeFile(change_id=recorded_change.id, path="src\\file.py", operation="modify")
    db.add_all([f1, f2])
    db.commit()

    svc = ConflictService(db)
    result = svc.compare_changes(change1, recorded_change)
    assert result.paths == ["src/file.py"]
