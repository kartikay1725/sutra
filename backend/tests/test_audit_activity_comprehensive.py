import pytest
from uuid import uuid4
from datetime import datetime, timezone

from app.models.user import User
from app.models.repository import Repository
from app.models.task import Task
from app.models.task_event import TaskEvent
from app.models.change import Change
from app.models.change_event import ChangeEvent
from app.models.pull_request import PullRequest
from app.models.agent import Agent
from app.models.actor import Actor
from app.models.discussion import Discussion
from app.core.security import hash_password
from app.services.repository_service import RepositoryService


def setup_audit_activity_fixtures(db):
    from tests.conftest import ensure_test_actor

    user = User(
        id=str(uuid4()),
        username=f"act_user_{uuid4().hex[:8]}",
        email=f"act_user_{uuid4().hex[:8]}@example.com",
        password_hash=hash_password("password"),
    )
    db.add(user)
    db.flush()
    ensure_test_actor(db, user)

    repo = RepositoryService(db).create(
        owner_id=user.id,
        name=f"act_repo_{uuid4().hex[:8]}",
        description="Audit Activity Test Repo",
        visibility="private",
    )

    agent = Agent(
        id=str(uuid4()),
        owner_id=user.id,
        name="Atlas-Audit-Agent",
        description="Autonomous agent for audit tests",
        token_hash=hash_password("agent-token"),
        token_prefix="sutra_agent_t",
        status="active",
        is_active=True,
    )
    db.add(agent)
    db.flush()

    agent_actor = Actor(
        id=agent.id,
        owner_id=user.id,
        type="agent",
        name=agent.name,
        capabilities='["repository.read", "repository.write", "change.create"]',
    )
    db.add(agent_actor)
    db.flush()

    # 1. Create a Task
    task = Task(
        id=str(uuid4()),
        repository_id=repo.id,
        created_by=user.id,
        assigned_agent_id=agent.id,
        title="Audit Fix for Session TTL",
        description="Ensure sessions expire properly",
        status="in_progress",
    )
    db.add(task)
    db.flush()

    task_evt = TaskEvent(
        id=str(uuid4()),
        task_id=task.id,
        actor_id=agent.id,
        event_type="task.started",
        from_status="open",
        to_status="in_progress",
    )
    db.add(task_evt)
    db.flush()

    # 2. Create a Change
    change = Change(
        id=str(uuid4()),
        repository_id=repo.id,
        actor_id=agent.id,
        status="proposed",
        intent="Set session idle timeout to 30 minutes",
    )
    db.add(change)
    db.flush()

    # 3. Create a ChangeEvent
    change_evt = ChangeEvent(
        id=str(uuid4()),
        change_id=change.id,
        actor_id=agent.id,
        event_type="change.created",
        from_status="none",
        to_status="proposed",
        metadata_json='{"intent": "Set session idle timeout"}',
    )
    db.add(change_evt)
    db.flush()

    # 4. Create a PR
    pr = PullRequest(
        id=str(uuid4()),
        repository_id=repo.id,
        source_change_id=change.id,
        author_id=agent.id,
        target_branch="main",
        status="open",
        title="feat: Session idle timeout",
    )
    db.add(pr)
    db.flush()

    # 5. Create a Discussion
    disc = Discussion(
        id=str(uuid4()),
        repository_id=repo.id,
        author_id=user.id,
        title="Discussion on timeout thresholds",
        body="Are 30 minutes sufficient for long-running workflows?",
        category="RFC",
    )
    db.add(disc)
    db.commit()

    return user, repo, task, change, pr, disc, agent


def test_unified_activity_and_audit_logs(client, db):
    user, repo, task, change, pr, disc, agent = setup_audit_activity_fixtures(db)

    # 1. Login user
    login_resp = client.post("/v1/auth/login", json={"login": user.email, "password": "password"})
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 2. Global Activity timeline
    act_resp = client.get("/v1/activity", headers=headers)
    assert act_resp.status_code == 200
    items = act_resp.json()
    assert len(items) >= 4

    # Verify resource types
    resource_types = {item["resource_type"] for item in items}
    assert "task" in resource_types
    assert "change" in resource_types
    assert "pull_request" in resource_types
    assert "discussion" in resource_types

    # Verify actors
    actors = {item["actor_name"] for item in items}
    assert any("Atlas" in a for a in actors)

    # Verify no secrets in metadata
    for item in items:
        meta_str = str(item.get("metadata_json", {}))
        assert "password" not in meta_str.lower()
        assert "token_hash" not in meta_str.lower()

    # 3. Repository-scoped activity timeline
    repo_act_resp = client.get(
        f"/v1/repositories/{user.username}/{repo.name}/activity",
        headers=headers,
    )
    assert repo_act_resp.status_code == 200
    repo_items = repo_act_resp.json()
    assert len(repo_items) >= 4

    # 4. Audit logs endpoint
    audit_resp = client.get("/v1/audit-logs", headers=headers)
    assert audit_resp.status_code == 200
    audit_items = audit_resp.json()
    assert len(audit_items) >= 4
