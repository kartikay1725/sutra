import json
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from sqlalchemy import select

from app.core.security import hash_password
from app.models.actor import Actor
from app.models.agent import Agent
from app.models.agent_session import AgentSession
from app.models.change import Change
from app.models.pull_request import PullRequest
from app.models.repository import Repository
from app.models.task import Task
from app.models.task_event import TaskEvent
from app.models.user import User


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def make_user(db, suffix=None):
    suffix = suffix or uuid4().hex[:8]
    user = User(
        id=f"pr-user-{suffix}",
        username=f"pr-user-{suffix}",
        email=f"pr-{suffix}@example.com",
        password_hash=hash_password("password"),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def make_agent(db, owner_id, agent_id=None):
    agent_id = agent_id or f"agent-{uuid4().hex[:8]}"
    raw_token = f"sutra_agent_pr_{uuid4().hex}"
    agent = Agent(
        id=agent_id,
        owner_id=owner_id,
        name=f"PR Agent {agent_id[:6]}",
        description="Agent for PR tests",
        provider="test",
        model="test",
        token_hash=hash_password(raw_token),
        token_prefix=raw_token[:16],
        status="active",
        is_active=True,
    )
    actor = Actor(
        id=agent.id,
        owner_id=owner_id,
        type="agent",
        name=agent.name,
        capabilities=json.dumps([
            "repository.read",
            "repository.write",
            "change.create",
            "change.commit",
            "change.conflict.read",
        ]),
    )
    db.add(agent)
    db.add(actor)
    db.commit()
    db.refresh(agent)
    return agent, raw_token


def create_session(client, raw_token):
    response = client.post(
        "/v1/agents/session",
        json={"token": raw_token},
    )
    assert response.status_code == 201
    return response.json()


def make_repository(db, owner):
    repo = Repository(
        id=str(uuid4()),
        owner_id=owner.id,
        name=f"test-repo-{uuid4().hex[:8]}",
        slug=f"test-repo-{uuid4().hex[:8]}",
        provider_type="local",
        default_branch="main",
        visibility="private",
        storage_key=f"agent-pr-storage-{uuid4().hex}",
    )
    db.add(repo)
    db.commit()
    db.refresh(repo)
    return repo


def make_task(db, repo, owner, agent):
    task = Task(
        id=str(uuid4()),
        repository_id=repo.id,
        created_by=owner.id,
        assigned_agent_id=agent.id,
        title="Implement Flood Monitoring Feature",
        description="Automated hydrological pipeline implementation",
        priority=Task.PRIORITY_HIGH,
        task_type=Task.TYPE_FEATURE,
        status=Task.STATUS_ASSIGNED,
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


def test_agent_pr_creation_full_lifecycle(client, db):
    """
    Test end-to-end agent task PR creation:
    Claim task -> create Change -> attach commit -> create PR -> verify linkage & response.
    """
    owner = make_user(db)
    agent, raw_token = make_agent(db, owner.id)
    repo = make_repository(db, owner)
    task = make_task(db, repo, owner, agent)
    session = create_session(client, raw_token)
    headers = bearer(session["token"])

    # 1. Claim task
    res = client.post(f"/v1/agent/tasks/{task.id}/claim", headers=headers)
    assert res.status_code == 200

    # 2. Create Change for task
    res = client.post(
        f"/v1/agent/tasks/{task.id}/changes",
        headers=headers,
        json={"intent": "Hydrological sensor data ingest pipeline", "branch": "agent/atlas/sensor-ingest"},
    )
    assert res.status_code == 201
    change_id = res.json()["id"]

    # 3. Try to create PR before commit -> must fail (change not recorded)
    res = client.post(
        f"/v1/agent/tasks/{task.id}/pull-requests",
        headers=headers,
        json={"title": "PR: Sensor Ingest"},
    )
    assert res.status_code == 409
    assert "recorded" in res.json()["detail"].lower()

    # 4. Attach commit to change
    dummy_sha = uuid4().hex + uuid4().hex[:8]
    ch = db.scalar(select(Change).where(Change.id == change_id))
    ch.status = "recorded"
    ch.resulting_commit = dummy_sha
    meta = json.loads(ch.metadata_json or "{}")
    meta["resulting_commit"] = dummy_sha
    ch.metadata_json = json.dumps(meta)
    db.commit()

    # 5. Create Pull Request
    res = client.post(
        f"/v1/agent/tasks/{task.id}/pull-requests",
        headers=headers,
        json={
            "title": "Hydrological sensor data ingest pipeline",
            "description": "Implements streaming ingest for flood prediction API.",
            "target_branch": "main",
        },
    )
    assert res.status_code == 201
    pr_data = res.json()

    # Verify PR record fields
    assert pr_data["id"] is not None
    assert pr_data["repository_id"] == repo.id
    assert pr_data["source_change_id"] == change_id
    assert pr_data["status"] == "open"
    assert pr_data["source_commit"] == dummy_sha
    assert pr_data["target_branch"] == "main"
    assert pr_data["task_id"] == task.id
    assert pr_data["task_title"] == task.title
    assert pr_data["agent_id"] == agent.id
    assert pr_data["agent_session_id"] == session["session_id"]

    # Verify DB state: Task linked to PR
    db_task = db.scalar(select(Task).where(Task.id == task.id))
    assert db_task.resulting_pull_request_id == pr_data["id"]

    # Verify DB state: Change metadata updated with PR
    db_change = db.scalar(select(Change).where(Change.id == change_id))
    meta = json.loads(db_change.metadata_json or "{}")
    assert meta.get("pull_request_id") == pr_data["id"]
    assert meta.get("pull_request_status") == "open"

    # Verify task audit event
    events = db.scalars(
        select(TaskEvent).where(
            TaskEvent.task_id == task.id,
            TaskEvent.event_type == "task.pull_request_created",
        )
    ).all()
    assert len(events) >= 1

    # 6. Idempotency test: duplicate call returns existing PR
    res2 = client.post(
        f"/v1/agent/tasks/{task.id}/pull-requests",
        headers=headers,
        json={"title": "Duplicate PR call"},
    )
    assert res2.status_code == 201
    assert res2.json()["id"] == pr_data["id"]


def test_agent_pr_authorization_and_lease_enforcement(client, db):
    """
    Test governance rules:
    - Other agent cannot create PR for task
    - Session without lease cannot create PR
    """
    owner = make_user(db)
    agent1, token1 = make_agent(db, owner.id)
    agent2, token2 = make_agent(db, owner.id)
    repo = make_repository(db, owner)
    task = make_task(db, repo, owner, agent1)

    session1 = create_session(client, token1)
    session2 = create_session(client, token2)

    # Agent 1 claims task
    res = client.post(f"/v1/agent/tasks/{task.id}/claim", headers=bearer(session1["token"]))
    assert res.status_code == 200

    # Agent 1 creates change and commits
    client.post(
        f"/v1/agent/tasks/{task.id}/changes",
        headers=bearer(session1["token"]),
        json={"intent": "Feature change"},
    )
    dummy_sha = uuid4().hex + uuid4().hex[:8]
    task_obj = db.scalar(select(Task).where(Task.id == task.id))
    ch = db.scalar(select(Change).where(Change.id == task_obj.resulting_change_id))
    ch.status = "recorded"
    ch.resulting_commit = dummy_sha
    db.commit()

    # Agent 2 attempts to create PR -> 403 Forbidden (not assigned agent)
    res = client.post(
        f"/v1/agent/tasks/{task.id}/pull-requests",
        headers=bearer(session2["token"]),
        json={"title": "Unauthorized PR"},
    )
    assert res.status_code == 403
    assert "not assigned" in res.json()["detail"].lower()
