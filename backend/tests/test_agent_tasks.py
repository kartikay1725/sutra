from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from sqlalchemy import select

from app.api.agent_dependencies import (
    SESSION_IDLE_TIMEOUT_SECONDS,
)
from app.core.security import hash_password
from app.models.agent import Agent
from app.models.agent_session import AgentSession
from app.models.repository import Repository
from app.models.task import Task
from app.models.user import User


def make_user(db, suffix=None):
    suffix = suffix or uuid4().hex[:8]

    user = User(
        id=f"agent-task-user-{suffix}",
        username=f"agent-task-user-{suffix}",
        email=f"agent-task-{suffix}@example.com",
        password_hash=hash_password("password"),
    )

    db.add(user)
    db.commit()
    db.refresh(user)

    return user


def make_agent(
    db,
    owner_id,
    agent_id=None,
):
    agent_id = agent_id or f"agent-{uuid4().hex[:8]}"

    raw_token = (
        f"sutra_agent_task_{uuid4().hex}"
    )

    agent = Agent(
        id=agent_id,
        owner_id=owner_id,
        name="Task Test Agent",
        description="Agent task test",
        provider="test",
        model="test",
        token_hash=hash_password(raw_token),
        token_prefix=raw_token[:16],
        status="active",
        is_active=True,
    )

    db.add(agent)
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
    repository = Repository(
    id=str(uuid4()),
    owner_id=owner.id,
    name=f"Agent Task Repo {uuid4().hex[:8]}",
    slug=f"agent-task-{uuid4().hex[:8]}",
    description="Agent task test repository",
    visibility="private",
    storage_key=f"agent-task-storage-{uuid4().hex}",
    )

    db.add(repository)
    db.commit()
    db.refresh(repository)

    return repository


def make_task(
    db,
    repository,
    owner,
    agent,
):
    task = Task(
        id=str(uuid4()),
        repository_id=repository.id,
        created_by=owner.id,
        assigned_agent_id=agent.id,
        title="Agent execution task",
        description="Test agent execution",
        status=Task.STATUS_ASSIGNED,
        priority=Task.PRIORITY_MEDIUM,
        task_type=Task.TYPE_FEATURE,
        source="user",
    )

    db.add(task)
    db.commit()
    db.refresh(task)

    return task


def bearer(token):
    return {
        "Authorization": f"Bearer {token}",
    }


def get_session(db, session_id):
    return db.scalar(
        select(AgentSession).where(
            AgentSession.id == session_id
        )
    )


def get_task(db, task_id):
    return db.scalar(
        select(Task).where(
            Task.id == task_id
        )
    )


def test_agent_can_claim_assigned_task(
    client,
    db,
):
    owner = make_user(db)
    agent, raw_token = make_agent(
        db,
        owner.id,
    )
    repository = make_repository(
        db,
        owner,
    )
    task = make_task(
        db,
        repository,
        owner,
        agent,
    )

    session = create_session(
        client,
        raw_token,
    )

    response = client.post(
        f"/v1/agent/tasks/{task.id}/claim",
        headers=bearer(session["token"]),
    )

    assert response.status_code == 200

    body = response.json()

    assert body["id"] == task.id
    assert body["assigned_agent_id"] == agent.id
    assert body["status"] == Task.STATUS_IN_PROGRESS
    assert (
        body["claimed_by_session_id"]
        == session["session_id"]
    )
    assert body["lease_expires_at"] is not None

    saved = get_task(db, task.id)

    assert (
        saved.claimed_by_session_id
        == session["session_id"]
    )
    assert saved.lease_expires_at is not None


def test_wrong_agent_cannot_claim_task(
    client,
    db,
):
    owner = make_user(db)

    assigned_agent, _ = make_agent(
        db,
        owner.id,
        agent_id="assigned-agent",
    )

    other_agent, other_token = make_agent(
        db,
        owner.id,
        agent_id="other-agent",
    )

    repository = make_repository(
        db,
        owner,
    )

    task = make_task(
        db,
        repository,
        owner,
        assigned_agent,
    )

    session = create_session(
        client,
        other_token,
    )

    response = client.post(
        f"/v1/agent/tasks/{task.id}/claim",
        headers=bearer(session["token"]),
    )

    assert response.status_code == 403
    assert (
        response.json()["detail"]
        == "Task is not assigned to this agent"
    )

    saved = get_task(db, task.id)

    assert saved.claimed_by_session_id is None
    assert saved.status == Task.STATUS_ASSIGNED


def test_second_session_cannot_steal_active_lease(
    client,
    db,
):
    owner = make_user(db)

    agent, raw_token = make_agent(
        db,
        owner.id,
    )

    repository = make_repository(
        db,
        owner,
    )

    task = make_task(
        db,
        repository,
        owner,
        agent,
    )

    first = create_session(
        client,
        raw_token,
    )

    second = create_session(
        client,
        raw_token,
    )

    first_response = client.post(
        f"/v1/agent/tasks/{task.id}/claim",
        headers=bearer(first["token"]),
    )

    assert first_response.status_code == 200

    second_response = client.post(
        f"/v1/agent/tasks/{task.id}/claim",
        headers=bearer(second["token"]),
    )

    assert second_response.status_code == 403
    assert (
        second_response.json()["detail"]
        == "Task is already claimed by another session"
    )

    saved = get_task(db, task.id)

    assert (
        saved.claimed_by_session_id
        == first["session_id"]
    )


def test_same_session_can_reclaim_idempotently(
    client,
    db,
):
    owner = make_user(db)
    agent, raw_token = make_agent(
        db,
        owner.id,
    )
    repository = make_repository(
        db,
        owner,
    )
    task = make_task(
        db,
        repository,
        owner,
        agent,
    )

    session = create_session(
        client,
        raw_token,
    )

    first = client.post(
        f"/v1/agent/tasks/{task.id}/claim",
        headers=bearer(session["token"]),
    )

    second = client.post(
        f"/v1/agent/tasks/{task.id}/claim",
        headers=bearer(session["token"]),
    )

    assert first.status_code == 200
    assert second.status_code == 200

    assert (
        second.json()["claimed_by_session_id"]
        == session["session_id"]
    )


def test_heartbeat_extends_lease(
    client,
    db,
):
    owner = make_user(db)
    agent, raw_token = make_agent(
        db,
        owner.id,
    )
    repository = make_repository(
        db,
        owner,
    )
    task = make_task(
        db,
        repository,
        owner,
        agent,
    )

    session = create_session(
        client,
        raw_token,
    )

    claim = client.post(
        f"/v1/agent/tasks/{task.id}/claim",
        headers=bearer(session["token"]),
    )

    assert claim.status_code == 200

    before = get_task(
        db,
        task.id,
    ).lease_expires_at

    response = client.post(
        f"/v1/agent/tasks/{task.id}/heartbeat",
        headers=bearer(session["token"]),
    )

    assert response.status_code == 200

    after = get_task(
        db,
        task.id,
    ).lease_expires_at

    assert after is not None
    assert before is not None

    before_utc = (
        before.replace(tzinfo=timezone.utc)
        if before.tzinfo is None
        else before
    )

    after_utc = (
        after.replace(tzinfo=timezone.utc)
        if after.tzinfo is None
        else after
    )

    assert after_utc >= before_utc


def test_wrong_session_cannot_heartbeat(
    client,
    db,
):
    owner = make_user(db)
    agent, raw_token = make_agent(
        db,
        owner.id,
    )
    repository = make_repository(
        db,
        owner,
    )
    task = make_task(
        db,
        repository,
        owner,
        agent,
    )

    first = create_session(
        client,
        raw_token,
    )

    second = create_session(
        client,
        raw_token,
    )

    claim = client.post(
        f"/v1/agent/tasks/{task.id}/claim",
        headers=bearer(first["token"]),
    )

    assert claim.status_code == 200

    response = client.post(
        f"/v1/agent/tasks/{task.id}/heartbeat",
        headers=bearer(second["token"]),
    )

    assert response.status_code == 403
    assert (
        response.json()["detail"]
        == "Task is not claimed by this session"
    )


def test_release_returns_task_to_assigned(
    client,
    db,
):
    owner = make_user(db)
    agent, raw_token = make_agent(
        db,
        owner.id,
    )
    repository = make_repository(
        db,
        owner,
    )
    task = make_task(
        db,
        repository,
        owner,
        agent,
    )

    session = create_session(
        client,
        raw_token,
    )

    claim = client.post(
        f"/v1/agent/tasks/{task.id}/claim",
        headers=bearer(session["token"]),
    )

    assert claim.status_code == 200

    response = client.post(
        f"/v1/agent/tasks/{task.id}/release",
        headers=bearer(session["token"]),
    )

    assert response.status_code == 200

    saved = get_task(db, task.id)

    assert saved.status == Task.STATUS_ASSIGNED
    assert saved.claimed_by_session_id is None
    assert saved.lease_expires_at is None


def test_expired_lease_can_be_reclaimed(
    client,
    db,
):
    owner = make_user(db)
    agent, raw_token = make_agent(
        db,
        owner.id,
    )
    repository = make_repository(
        db,
        owner,
    )
    task = make_task(
        db,
        repository,
        owner,
        agent,
    )

    first = create_session(
        client,
        raw_token,
    )

    second = create_session(
        client,
        raw_token,
    )

    claim = client.post(
        f"/v1/agent/tasks/{task.id}/claim",
        headers=bearer(first["token"]),
    )

    assert claim.status_code == 200

    saved = get_task(
        db,
        task.id,
    )

    saved.lease_expires_at = (
        datetime.now(timezone.utc)
        - timedelta(seconds=1)
    )

    db.commit()

    response = client.post(
        f"/v1/agent/tasks/{task.id}/claim",
        headers=bearer(second["token"]),
    )

    assert response.status_code == 200

    body = response.json()

    assert (
        body["claimed_by_session_id"]
        == second["session_id"]
    )


def test_expired_lease_cannot_heartbeat(
    client,
    db,
):
    owner = make_user(db)
    agent, raw_token = make_agent(
        db,
        owner.id,
    )
    repository = make_repository(
        db,
        owner,
    )
    task = make_task(
        db,
        repository,
        owner,
        agent,
    )

    session = create_session(
        client,
        raw_token,
    )

    claim = client.post(
        f"/v1/agent/tasks/{task.id}/claim",
        headers=bearer(session["token"]),
    )

    assert claim.status_code == 200

    saved = get_task(
        db,
        task.id,
    )

    saved.lease_expires_at = (
        datetime.now(timezone.utc)
        - timedelta(seconds=1)
    )

    db.commit()

    response = client.post(
        f"/v1/agent/tasks/{task.id}/heartbeat",
        headers=bearer(session["token"]),
    )

    assert response.status_code == 409
    assert (
        response.json()["detail"]
        == "Task lease expired"
    )

    saved = get_task(
        db,
        task.id,
    )

    assert saved.claimed_by_session_id is None
    assert saved.lease_expires_at is None
    assert saved.status == Task.STATUS_ASSIGNED


def test_expired_session_cannot_claim(
    client,
    db,
):
    owner = make_user(db)
    agent, raw_token = make_agent(
        db,
        owner.id,
    )
    repository = make_repository(
        db,
        owner,
    )
    task = make_task(
        db,
        repository,
        owner,
        agent,
    )

    session = create_session(
        client,
        raw_token,
    )

    saved_session = get_session(
        db,
        session["session_id"],
    )

    saved_session.expires_at = (
        datetime.now(timezone.utc)
        - timedelta(seconds=1)
    )

    db.commit()

    response = client.post(
        f"/v1/agent/tasks/{task.id}/claim",
        headers=bearer(session["token"]),
    )

    assert response.status_code == 401
    detail = response.json()["detail"]

    assert isinstance(detail, dict)
    assert detail["http_status"] == 401
    assert "expired" in detail["reason"].lower()


def test_revoked_session_cannot_claim(
    client,
    db,
):
    owner = make_user(db)
    agent, raw_token = make_agent(
        db,
        owner.id,
    )
    repository = make_repository(
        db,
        owner,
    )
    task = make_task(
        db,
        repository,
        owner,
        agent,
    )

    session = create_session(
        client,
        raw_token,
    )

    saved_session = get_session(
        db,
        session["session_id"],
    )

    saved_session.status = "revoked"
    saved_session.revoked_at = (
        datetime.now(timezone.utc)
    )

    db.commit()

    response = client.post(
        f"/v1/agent/tasks/{task.id}/claim",
        headers=bearer(session["token"]),
    )

    assert response.status_code == 401


def test_revoked_agent_cannot_execute(
    client,
    db,
):
    owner = make_user(db)
    agent, raw_token = make_agent(
        db,
        owner.id,
    )
    repository = make_repository(
        db,
        owner,
    )
    task = make_task(
        db,
        repository,
        owner,
        agent,
    )

    session = create_session(
        client,
        raw_token,
    )

    claim = client.post(
        f"/v1/agent/tasks/{task.id}/claim",
        headers=bearer(session["token"]),
    )

    assert claim.status_code == 200

    agent.is_active = False
    agent.status = "revoked"

    db.commit()

    response = client.post(
        f"/v1/agent/tasks/{task.id}/execute",
        headers=bearer(session["token"]),
    )

    assert response.status_code == 401


def test_execute_requires_current_session_lease(
    client,
    db,
):
    owner = make_user(db)
    agent, raw_token = make_agent(
        db,
        owner.id,
    )
    repository = make_repository(
        db,
        owner,
    )
    task = make_task(
        db,
        repository,
        owner,
        agent,
    )

    session = create_session(
        client,
        raw_token,
    )

    response = client.post(
        f"/v1/agent/tasks/{task.id}/execute",
        headers=bearer(session["token"]),
    )

    assert response.status_code == 403
    assert (
        response.json()["detail"]
        == "Task is not claimed by this session"
    )


def test_execute_rejects_expired_lease(
    client,
    db,
):
    owner = make_user(db)
    agent, raw_token = make_agent(
        db,
        owner.id,
    )
    repository = make_repository(
        db,
        owner,
    )
    task = make_task(
        db,
        repository,
        owner,
        agent,
    )

    session = create_session(
        client,
        raw_token,
    )

    claim = client.post(
        f"/v1/agent/tasks/{task.id}/claim",
        headers=bearer(session["token"]),
    )

    assert claim.status_code == 200

    saved = get_task(
        db,
        task.id,
    )

    saved.lease_expires_at = (
        datetime.now(timezone.utc)
        - timedelta(seconds=1)
    )

    db.commit()

    response = client.post(
        f"/v1/agent/tasks/{task.id}/execute",
        headers=bearer(session["token"]),
    )

    assert response.status_code == 409
    assert (
        response.json()["detail"]
        == "Task lease expired"
    )


def test_missing_agent_auth_is_rejected(
    client,
    db,
):
    owner = make_user(db)
    agent, _ = make_agent(
        db,
        owner.id,
    )
    repository = make_repository(
        db,
        owner,
    )
    task = make_task(
        db,
        repository,
        owner,
        agent,
    )

    response = client.post(
        f"/v1/agent/tasks/{task.id}/claim",
    )

    assert response.status_code == 401


def test_permanent_agent_token_cannot_claim(
    client,
    db,
):
    owner = make_user(db)
    agent, raw_token = make_agent(
        db,
        owner.id,
    )
    repository = make_repository(
        db,
        owner,
    )
    task = make_task(
        db,
        repository,
        owner,
        agent,
    )

    response = client.post(
        f"/v1/agent/tasks/{task.id}/claim",
        headers=bearer(raw_token),
    )

    assert response.status_code == 401

def test_valid_agent_task_lease_allows_execution(
    client,
    db,
):
    owner = make_user(db)

    agent, raw_token = make_agent(
        db,
        owner.id,
    )

    repository = make_repository(
        db,
        owner,
    )

    task = make_task(
        db,
        repository,
        owner,
        agent,
    )

    session = create_session(
        client,
        raw_token,
    )

    claim = client.post(
        f"/v1/agent/tasks/{task.id}/claim",
        headers=bearer(session["token"]),
    )

    assert claim.status_code == 200

    execute = client.post(
        f"/v1/agent/tasks/{task.id}/execute",
        headers=bearer(session["token"]),
    )

    assert execute.status_code == 200

    body = execute.json()

    assert body["id"] == task.id
    assert body["status"] == Task.STATUS_IN_PROGRESS
    assert body["claimed_by_session_id"] == session["session_id"]
    assert body["lease_expires_at"] is not None

def test_expired_agent_task_lease_blocks_execution_and_releases_task(
    client,
    db,
):
    owner = make_user(db)

    agent, raw_token = make_agent(
        db,
        owner.id,
    )

    repository = make_repository(
        db,
        owner,
    )

    task = make_task(
        db,
        repository,
        owner,
        agent,
    )

    session = create_session(
        client,
        raw_token,
    )

    claim = client.post(
        f"/v1/agent/tasks/{task.id}/claim",
        headers=bearer(session["token"]),
    )

    assert claim.status_code == 200

    saved = get_task(
        db,
        task.id,
    )

    saved.lease_expires_at = (
        datetime.now(timezone.utc)
        - timedelta(seconds=1)
    )

    db.commit()

    response = client.post(
        f"/v1/agent/tasks/{task.id}/execute",
        headers=bearer(session["token"]),
    )

    assert response.status_code == 409

    assert (
        response.json()["detail"]
        == "Task lease expired"
    )

    saved = get_task(
        db,
        task.id,
    )

    assert saved.claimed_by_session_id is None
    assert saved.lease_expires_at is None
    assert saved.status == Task.STATUS_ASSIGNED


def test_agent_task_execution_is_idempotent(
    client,
    db,
):
    owner = make_user(db)

    agent, raw_token = make_agent(
        db,
        owner.id,
    )

    repository = make_repository(
        db,
        owner,
    )

    task = make_task(
        db,
        repository,
        owner,
        agent,
    )

    session = create_session(
        client,
        raw_token,
    )

    claim = client.post(
        f"/v1/agent/tasks/{task.id}/claim",
        headers=bearer(session["token"]),
    )

    assert claim.status_code == 200

    first = client.post(
        f"/v1/agent/tasks/{task.id}/execute",
        headers=bearer(session["token"]),
    )

    assert first.status_code == 200

    first_body = first.json()

    first_change_id = (
        first_body["resulting_change_id"]
    )

    assert first_change_id is not None

    second = client.post(
        f"/v1/agent/tasks/{task.id}/execute",
        headers=bearer(session["token"]),
    )

    assert second.status_code == 200

    second_body = second.json()

    assert (
        second_body["resulting_change_id"]
        == first_change_id
    )

    saved = get_task(
        db,
        task.id,
    )

    assert (
        saved.resulting_change_id
        == first_change_id
    )


def test_create_and_claim_agent_task_mode_b(client, db):
    from app.services.task_service import TaskService
    from app.models.agent_repository_access import AgentRepositoryAccess

    owner = make_user(db)
    agent, raw_token = make_agent(db, owner.id)
    repository = make_repository(db, owner)

    access = AgentRepositoryAccess(
        agent_id=agent.id,
        repository_id=repository.id,
        enabled=True,
    )
    db.add(access)
    db.commit()

    session_data = create_session(client, raw_token)
    session = get_session(db, session_data["session_id"])

    task_service = TaskService(db)
    task = task_service.create_and_claim_agent_task(
        session=session,
        title="Fix OAuth token expiration bug",
        description="Users report 401 when token expires after 1 hour. Please fix.",
        repository=repository.name,
    )

    assert task.id is not None
    assert task.title == "Fix OAuth token expiration bug"
    assert task.description == "Users report 401 when token expires after 1 hour. Please fix."
    assert task.source == "agent"
    assert task.created_by == owner.id
    assert task.assigned_agent_id == agent.id
    assert task.claimed_by_session_id == session.id
    assert task.status == Task.STATUS_IN_PROGRESS
    assert task.lease_expires_at is not None


def test_create_and_claim_agent_task_auto_resolve_repository(client, db):
    from app.services.task_service import TaskService
    from app.models.agent_repository_access import AgentRepositoryAccess

    owner = make_user(db)
    agent, raw_token = make_agent(db, owner.id)
    repository = make_repository(db, owner)

    access = AgentRepositoryAccess(
        agent_id=agent.id,
        repository_id=repository.id,
        enabled=True,
    )
    db.add(access)
    db.commit()

    session_data = create_session(client, raw_token)
    session = get_session(db, session_data["session_id"])

    task_service = TaskService(db)
    # Repository omitted -> should auto-resolve to the single authorized repo
    task = task_service.create_and_claim_agent_task(
        session=session,
        description="Add health check endpoint and verify return code.",
    )

    assert task.repository_id == repository.id
    assert task.title == "Add health check endpoint and verify return code."
    assert task.source == "agent"


def test_create_and_claim_agent_task_unauthorized_repository(client, db):
    from app.services.task_service import TaskService

    owner = make_user(db)
    agent, raw_token = make_agent(db, owner.id)
    unauthorized_repo = make_repository(db, owner)

    session_data = create_session(client, raw_token)
    session = get_session(db, session_data["session_id"])

    task_service = TaskService(db)
    with pytest.raises(PermissionError, match="does not have repository access grant"):
        task_service.create_and_claim_agent_task(
            session=session,
            description="Unauthorized change request",
            repository=unauthorized_repo.name,
        )


def test_complete_agent_task_stores_summaries(client, db):
    from app.services.task_service import TaskService
    from app.models.agent_repository_access import AgentRepositoryAccess

    owner = make_user(db)
    agent, raw_token = make_agent(db, owner.id)
    repository = make_repository(db, owner)

    access = AgentRepositoryAccess(
        agent_id=agent.id,
        repository_id=repository.id,
        enabled=True,
    )
    db.add(access)
    db.commit()

    session_data = create_session(client, raw_token)
    session = get_session(db, session_data["session_id"])

    task_service = TaskService(db)
    task = task_service.create_and_claim_agent_task(
        session=session,
        title="Documentation update",
        description="Update README with architecture diagrams.",
    )

    completed_task = task_service.complete_agent_task(
        task_id=task.id,
        session=session,
        outcome="completed",
        execution_summary="Updated README.md with comprehensive mermaid diagrams.",
        validation_summary="Markdown linter passed with 0 warnings.",
    )

    assert completed_task.status == Task.STATUS_COMPLETED
    assert completed_task.execution_summary == "Updated README.md with comprehensive mermaid diagrams."
    assert completed_task.validation_summary == "Markdown linter passed with 0 warnings."
    assert completed_task.completed_at is not None


def test_complete_agent_task_blocked_by_unmerged_pr(client, db):
    from app.services.task_service import TaskService
    from app.models.agent_repository_access import AgentRepositoryAccess
    from app.models.actor import Actor
    from app.models.change import Change
    from app.models.pull_request import PullRequest

    owner = make_user(db)
    agent, raw_token = make_agent(db, owner.id)
    repository = make_repository(db, owner)

    access = AgentRepositoryAccess(
        agent_id=agent.id,
        repository_id=repository.id,
        enabled=True,
    )
    db.add(access)

    actor = db.scalar(select(Actor).where(Actor.id == agent.id))
    if not actor:
        actor = Actor(
            id=agent.id,
            type="agent",
            name=agent.name,
        )
        db.add(actor)
        db.flush()

    task = make_task(db, repository, owner, agent)

    change = Change(
        id=str(uuid4()),
        repository_id=repository.id,
        actor_id=actor.id,
        status="proposed",
        intent="Test intent",
        operation_key=str(uuid4()),
    )
    db.add(change)
    db.flush()

    pr = PullRequest(
        id=str(uuid4()),
        repository_id=repository.id,
        author_id=actor.id,
        source_change_id=change.id,
        title="Unmerged Governed PR",
        target_branch="main",
        source_commit="1111111111111111111111111111111111111111",
        target_commit="0000000000000000000000000000000000000000",
        status=PullRequest.STATUS_OPEN,
    )
    db.add(pr)
    task.resulting_pull_request_id = pr.id
    task.status = Task.STATUS_IN_PROGRESS
    db.commit()

    session_data = create_session(client, raw_token)
    session = get_session(db, session_data["session_id"])
    task.claimed_by_session_id = session.id
    task.lease_expires_at = datetime.now(timezone.utc) + timedelta(minutes=30)
    db.commit()

    task_service = TaskService(db)
    with pytest.raises(PermissionError, match="Cannot mark task completed"):
        task_service.complete_agent_task(
            task_id=task.id,
            session=session,
            outcome="completed",
            execution_summary="Attempting premature completion.",
        )

