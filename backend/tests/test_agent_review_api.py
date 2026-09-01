from uuid import uuid4
import pytest
from fastapi import status

from app.models.actor import Actor
from app.models.agent import Agent
from app.models.change import Change
from app.models.pull_request import PullRequest
from app.models.repository import Repository
from app.models.user import User
from app.services.pull_request_service import PullRequestService
from app.services.repository_service import RepositoryService
from tests.conftest import ensure_test_actor


def setup_agent_api_fixtures(db):
    user_a = User(
        id=str(uuid4()),
        username=f"ag_api_a_{uuid4().hex[:8]}",
        email=f"agapia_{uuid4().hex[:8]}@example.com",
        password_hash="hash",
    )
    user_b = User(
        id=str(uuid4()),
        username=f"ag_api_b_{uuid4().hex[:8]}",
        email=f"agapib_{uuid4().hex[:8]}@example.com",
        password_hash="hash",
    )
    db.add_all([user_a, user_b])
    db.flush()

    ensure_test_actor(db, user_a)
    ensure_test_actor(db, user_b)

    repo_a = RepositoryService(db).create(
        owner_id=user_a.id,
        name=f"ag_api_repo_a_{uuid4().hex[:8]}",
        description="Agent API Repo A",
        visibility="private",
    )

    agent_a = Agent(
        id=str(uuid4()),
        owner_id=user_a.id,
        name="agent_api_a",
        token_prefix="prefix_agapi_123",
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

    agent_b = Agent(
        id=str(uuid4()),
        owner_id=user_b.id,
        name="agent_api_b",
        token_prefix="prefix_agapi_456",
        token_hash="hash",
        is_active=True,
        status="active",
    )
    db.add(agent_b)

    actor_b = Actor(
        id=agent_b.id,
        owner_id=user_b.id,
        type="agent",
        name=agent_b.name,
        capabilities='["repository.read", "repository.write", "change.create"]',
    )
    db.add(actor_b)
    db.commit()

    change_a = Change(
        id=str(uuid4()),
        repository_id=repo_a.id,
        actor_id=actor_a.id,
        intent="Agent API Change A",
        risk_level="low",
        resulting_commit="1111111111111111111111111111111111111111",
        base_commit="0000000000000000000000000000000000000000",
        operation_key=(uuid4().hex * 2)[:64],
        status="proposed",
    )
    db.add(change_a)
    db.commit()

    svc = PullRequestService(db)
    pr_a = svc.create_pull_request(repo_a.id, user_a.id, change_a.id, "Agent API PR A", "main")
    db.commit()

    return user_a, user_b, repo_a, agent_a, agent_b, change_a, pr_a


def test_agent_review_api_flow(db, client):
    user_a, user_b, repo_a, agent_a, agent_b, change_a, pr_a = setup_agent_api_fixtures(db)

    from app.api.agent_dependencies import get_current_agent
    from app.api.dependencies import get_current_user
    from app.main import app

    app.dependency_overrides[get_current_agent] = lambda: agent_a

    # 1. Agent A posts comment
    payload_comment = {
        "body": "Agent API Comment",
        "path": "src/app.py",
        "diff_side": "RIGHT",
        "line_number": 10,
    }
    res_comment = client.post(
        f"/v1/pull-requests/{pr_a.id}/agent-reviews/comments",
        json=payload_comment,
    )
    assert res_comment.status_code == status.HTTP_201_CREATED
    assert res_comment.json()["path"] == "src/app.py"

    # 2. Agent A posts finding
    payload_finding = {
        "severity": "critical",
        "category": "security",
        "message": "Found hardcoded API key",
        "path": "src/config.py",
        "line_number": 5,
        "suggested_fix": "Use environment variable",
    }
    res_finding = client.post(
        f"/v1/pull-requests/{pr_a.id}/agent-reviews/findings",
        json=payload_finding,
    )
    assert res_finding.status_code == status.HTTP_201_CREATED
    assert "[CRITICAL] [SECURITY]" in res_finding.json()["body"]

    # 3. User A gets agent review summary
    app.dependency_overrides[get_current_user] = lambda: user_a
    res_summary = client.get(f"/v1/pull-requests/{pr_a.id}/agent-reviews")
    assert res_summary.status_code == status.HTTP_200_OK
    sum_data = res_summary.json()
    assert sum_data["total_findings"] == 1
    assert sum_data["severity_distribution"]["critical"] == 1

    # 4. User B (unauthorized) attempts to view private PR agent reviews
    app.dependency_overrides[get_current_user] = lambda: user_b
    res_unauth = client.get(f"/v1/pull-requests/{pr_a.id}/agent-reviews")
    assert res_unauth.status_code == status.HTTP_404_NOT_FOUND

    app.dependency_overrides.clear()
