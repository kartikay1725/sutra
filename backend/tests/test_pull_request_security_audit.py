from datetime import datetime, timezone
from uuid import uuid4
import pytest
from fastapi import status
from sqlalchemy import select

from app.models.actor import Actor
from app.models.agent import Agent
from app.models.change import Change
from app.models.change_event import ChangeEvent
from app.models.change_review import ChangeReview
from app.models.pull_request import PullRequest
from app.models.repository import Repository
from app.models.user import User
from app.services.pull_request_service import PullRequestService
from app.services.repository_service import RepositoryService
from tests.conftest import ensure_test_actor


def setup_security_fixtures(db):
    user_a = User(
        id=str(uuid4()),
        username=f"sec_user_a_{uuid4().hex[:8]}",
        email=f"seca_{uuid4().hex[:8]}@example.com",
        password_hash="hash",
    )
    db.add(user_a)

    user_b = User(
        id=str(uuid4()),
        username=f"sec_user_b_{uuid4().hex[:8]}",
        email=f"secb_{uuid4().hex[:8]}@example.com",
        password_hash="hash",
    )
    db.add(user_b)
    db.flush()

    ensure_test_actor(db, user_a)
    ensure_test_actor(db, user_b)

    repo_a = RepositoryService(db).create(
        owner_id=user_a.id,
        name=f"sec_repo_a_{uuid4().hex[:8]}",
        description="User A Private Repo",
        visibility="private",
    )

    repo_b = RepositoryService(db).create(
        owner_id=user_b.id,
        name=f"sec_repo_b_{uuid4().hex[:8]}",
        description="User B Private Repo",
        visibility="private",
    )

    agent_a = Agent(
        id=str(uuid4()),
        owner_id=user_a.id,
        name="sec_agent_a",
        token_prefix="prefix_seca_123",
        token_hash="hash",
        is_active=True,
        status="active",
    )
    db.add(agent_a)

    actor_a = Actor(
        id=agent_a.id,
        owner_id=user_a.id,
        type="agent",
        name=agent_a.name,
        capabilities='["repository.read", "repository.write", "change.create"]',
    )
    db.add(actor_a)
    db.commit()

    change_a = Change(
        id=str(uuid4()),
        repository_id=repo_a.id,
        actor_id=actor_a.id,
        intent="Security Change A",
        risk_level="low",
        resulting_commit="1111111111111111111111111111111111111111",
        base_commit="0000000000000000000000000000000000000000",
        operation_key=(uuid4().hex * 2)[:64],
        status="proposed",
    )
    db.add(change_a)
    db.commit()

    svc = PullRequestService(db)
    pr_a = svc.create_pull_request(repo_a.id, user_a.id, change_a.id, "User A PR", "main")

    return user_a, user_b, repo_a, repo_b, agent_a, actor_a, change_a, pr_a


def test_idor_and_bola_matrix(db, client):
    user_a, user_b, repo_a, repo_b, agent_a, actor_a, change_a, pr_a = setup_security_fixtures(db)

    from app.api.dependencies import get_current_user
    from app.main import app

    app.dependency_overrides[get_current_user] = lambda: user_b

    # User B attempting to access User A private PRs via read/action endpoints
    endpoints_get = [
        f"/v1/pull-requests/{pr_a.id}",
        f"/v1/pull-requests/{pr_a.id}/changes",
        f"/v1/pull-requests/{pr_a.id}/reviews",
        f"/v1/pull-requests/{pr_a.id}/events",
        f"/v1/pull-requests/{pr_a.id}/conflicts",
    ]
    for ep in endpoints_get:
        res = client.get(ep)
        assert res.status_code == status.HTTP_404_NOT_FOUND

    endpoints_post = [
        f"/v1/pull-requests/{pr_a.id}/approve",
        f"/v1/pull-requests/{pr_a.id}/reject",
        f"/v1/pull-requests/{pr_a.id}/close",
        f"/v1/pull-requests/{pr_a.id}/merge",
        f"/v1/pull-requests/{pr_a.id}/reviews",
    ]
    for ep in endpoints_post:
        res = client.post(ep)
        assert res.status_code in {status.HTTP_403_FORBIDDEN, status.HTTP_404_NOT_FOUND}

    app.dependency_overrides.clear()


def test_cross_repository_change_creation_prevention(db, client):
    user_a, user_b, repo_a, repo_b, agent_a, actor_a, change_a, pr_a = setup_security_fixtures(db)

    from app.api.dependencies import get_current_user
    from app.main import app

    app.dependency_overrides[get_current_user] = lambda: user_a

    # Now create Change in repo_b
    change_b = Change(
        id=str(uuid4()),
        repository_id=repo_b.id,
        actor_id=user_b.id,
        intent="Change B",
        operation_key=(uuid4().hex * 2)[:64],
        status="proposed",
    )
    db.add(change_b)
    db.commit()

    # User A tries to create PR in Repo A attaching Change B (cross-repo attack)
    payload = {
        "repository_id": repo_a.id,
        "source_change_id": change_b.id,
        "title": "Cross Repo PR",
        "target_branch": "main",
    }
    res = client.post("/v1/pull-requests", json=payload)
    assert res.status_code in {status.HTTP_400_BAD_REQUEST, status.HTTP_409_CONFLICT}
    assert "does not belong to target repository" in res.json()["detail"]

    app.dependency_overrides.clear()


def test_git_input_injection_prevention(client, db):
    user_a, user_b, repo_a, repo_b, agent_a, actor_a, change_a, pr_a = setup_security_fixtures(db)

    from app.api.dependencies import get_current_user
    from app.main import app

    app.dependency_overrides[get_current_user] = lambda: user_a

    malicious_branches = [
        "--help",
        "--force",
        "../../etc/passwd",
        "$(whoami)",
        "`whoami`",
        ";whoami",
        "main --force",
        "refs/heads/../../evil",
    ]

    for mb in malicious_branches:
        payload = {
            "repository_id": repo_a.id,
            "source_change_id": change_a.id,
            "title": "Injection PR",
            "target_branch": mb,
        }
        res = client.post("/v1/pull-requests", json=payload)
        # Should fail Pydantic pattern validation (422) or service validation
        assert res.status_code in {status.HTTP_400_BAD_REQUEST, status.HTTP_422_UNPROCESSABLE_ENTITY, status.HTTP_409_CONFLICT}

    app.dependency_overrides.clear()


def test_uuid_and_sha_validation(client, db):
    user_a, user_b, repo_a, repo_b, agent_a, actor_a, change_a, pr_a = setup_security_fixtures(db)

    from app.api.dependencies import get_current_user
    from app.main import app

    app.dependency_overrides[get_current_user] = lambda: user_a

    malformed_ids = [
        "not-a-uuid",
        "123",
        "'; DROP TABLE pull_requests; --",
        "../../etc/passwd",
        "a" * 500,
    ]
    for mid in malformed_ids:
        res = client.get(f"/v1/pull-requests/{mid}")
        assert res.status_code in {status.HTTP_404_NOT_FOUND, status.HTTP_422_UNPROCESSABLE_ENTITY}

    app.dependency_overrides.clear()


def test_status_machine_attack_and_terminal_state_protection(db):
    user_a, user_b, repo_a, repo_b, agent_a, actor_a, change_a, pr_a = setup_security_fixtures(db)
    svc = PullRequestService(db)

    # Approve PR first, then transition to merged
    svc.create_pull_request_review_request(pr_a, requester_id=user_a.id)
    svc.approve_pull_request(pr_a, approver_id=user_b.id)
    svc.transition_pull_request(pr_a, PullRequest.STATUS_MERGED)

    # Terminal state protection: merged PR cannot be mutated to open, approved, or rejected
    with pytest.raises(ValueError, match="Cannot transition"):
        svc.transition_pull_request(pr_a, PullRequest.STATUS_OPEN)

    with pytest.raises(ValueError, match="Cannot approve PullRequest in status 'merged'"):
        svc.approve_pull_request(pr_a, approver_id=user_b.id)


def test_self_review_and_self_approval_protection(db):
    user_a, user_b, repo_a, repo_b, agent_a, actor_a, change_a, pr_a = setup_security_fixtures(db)
    svc = PullRequestService(db)

    # Self-approval by PR author fails
    with pytest.raises(ValueError, match="Self-review approval is strictly prohibited"):
        svc.approve_pull_request(pr_a, approver_id=user_a.id)


def test_audit_event_metadata_sanitization(db):
    user_a, user_b, repo_a, repo_b, agent_a, actor_a, change_a, pr_a = setup_security_fixtures(db)
    svc = PullRequestService(db)

    # Record event with sensitive metadata
    sensitive_metadata = {
        "token": "secret_token_123",
        "password": "secret_password",
        "jwt": "secret_jwt",
        "safe_key": "safe_value",
    }
    svc.transition_pull_request(
        pr_a,
        PullRequest.STATUS_CLOSED,
        actor_id=user_a.id,
        metadata=sensitive_metadata,
    )

    events = db.scalars(
        select(ChangeEvent).where(ChangeEvent.change_id == change_a.id)
    ).all()

    closed_event = next(e for e in events if e.event_type == "pull_request.closed")
    assert "token" not in closed_event.metadata_json
    assert "password" not in closed_event.metadata_json
    assert "jwt" not in closed_event.metadata_json
    assert "safe_key" in closed_event.metadata_json
