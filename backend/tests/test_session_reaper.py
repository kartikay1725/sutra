from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from sqlalchemy import select

from app.core.security import hash_password
from app.models.agent import Agent
from app.models.agent_session import AgentSession
from app.models.repository import Repository
from app.models.task import Task
from app.models.user import User
from app.services.session_reaper_service import SessionReaperService
from app.services.task_service import TaskService


@pytest.fixture
def reaper_service():
    return SessionReaperService()


def make_user(db, user_id="reaper-user"):
    user = User(
        id=user_id,
        username=f"user-{user_id}",
        email=f"{user_id}@example.com",
        password_hash=hash_password("password"),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def make_agent(db, owner_id, agent_id="reaper-agent"):
    agent = Agent(
        id=agent_id,
        owner_id=owner_id,
        name="Reaper Test Agent",
        description="Agent session reaper test",
        provider="test",
        model="test",
        token_hash="hash",
        token_prefix="prefix",
        status="active",
        is_active=True,
    )
    db.add(agent)
    db.commit()
    db.refresh(agent)
    return agent


def make_repository(db, owner_id, repo_id="reaper-repo"):
    repo = Repository(
        id=repo_id,
        owner_id=owner_id,
        name="reaper-repo",
        slug="reaper-repo",
        description="Reaper Repo",
        visibility="public",
        storage_key="test/test",
    )
    db.add(repo)
    db.commit()
    db.refresh(repo)
    return repo


def test_revoke_idle_sessions(db, reaper_service):
    user = make_user(db)
    agent = make_agent(db, user.id)
    now = datetime.now(timezone.utc)
    
    # Active session (seen recently)
    active_session = AgentSession(
        id=str(uuid4()),
        agent_id=agent.id,
        token_hash="active_hash",
        token_prefix="active_prefix",
        status="active",
        expires_at=now + timedelta(hours=1),
        last_seen_at=now - timedelta(seconds=60),  # 60s ago, < 120s
    )
    db.add(active_session)
    
    # Idle session (seen > 120s ago)
    idle_session = AgentSession(
        id=str(uuid4()),
        agent_id=agent.id,
        token_hash="idle_hash",
        token_prefix="idle_prefix",
        status="active",
        expires_at=now + timedelta(hours=1),
        last_seen_at=now - timedelta(seconds=130),  # 130s ago, > 120s
    )
    db.add(idle_session)
    
    # Already revoked session (seen > 120s ago but status != active)
    revoked_session = AgentSession(
        id=str(uuid4()),
        agent_id=agent.id,
        token_hash="revoked_hash",
        token_prefix="revoked_prefix",
        status="revoked",
        expires_at=now + timedelta(hours=1),
        last_seen_at=now - timedelta(seconds=200),
    )
    db.add(revoked_session)
    db.commit()

    count = reaper_service.revoke_idle_sessions(db)
    assert count == 1
    
    # Verify DB states
    active = db.scalar(select(AgentSession).where(AgentSession.id == active_session.id))
    assert active.status == "active"
    
    idle = db.scalar(select(AgentSession).where(AgentSession.id == idle_session.id))
    assert idle.status == "revoked"
    assert idle.revoked_at is not None
    
    revoked = db.scalar(select(AgentSession).where(AgentSession.id == revoked_session.id))
    assert revoked.status == "revoked"


def test_revoke_expired_sessions(db, reaper_service):
    user = make_user(db)
    agent = make_agent(db, user.id)
    now = datetime.now(timezone.utc)
    
    # Active unexpired session
    active_session = AgentSession(
        id=str(uuid4()),
        agent_id=agent.id,
        token_hash="active_hash",
        token_prefix="active_prefix",
        status="active",
        expires_at=now + timedelta(hours=1),
        last_seen_at=now,
    )
    db.add(active_session)
    
    # Expired session
    expired_session = AgentSession(
        id=str(uuid4()),
        agent_id=agent.id,
        token_hash="expired_hash",
        token_prefix="expired_prefix",
        status="active",
        expires_at=now - timedelta(seconds=10),
        last_seen_at=now,
    )
    db.add(expired_session)
    db.commit()
    
    count = reaper_service.revoke_expired_sessions(db)
    assert count == 1
    
    active = db.scalar(select(AgentSession).where(AgentSession.id == active_session.id))
    assert active.status == "active"
    
    expired = db.scalar(select(AgentSession).where(AgentSession.id == expired_session.id))
    assert expired.status == "revoked"
    assert expired.revoked_at is not None


def test_task_completion_revokes_session(db):
    user = make_user(db, "tuser")
    agent = make_agent(db, user.id, "tagent")
    repo = make_repository(db, user.id, "trepo")
    
    now = datetime.now(timezone.utc)
    task_service = TaskService(db)
    
    # Create session
    session = AgentSession(
        id=str(uuid4()),
        agent_id=agent.id,
        token_hash="task_hash",
        token_prefix="task_prefix",
        status="active",
        expires_at=now + timedelta(hours=1),
        last_seen_at=now,
    )
    db.add(session)
    db.commit()
    
    # Create task
    task = task_service.create_task(
        repository_id=repo.id,
        created_by_id=user.id,
        title="Test Task",
    )
    
    # Assign and claim task
    task_service.assign_task(task.id, user.id, assigned_agent_id=agent.id)
    task_service.claim_agent_task(task.id, session)
    
    from app.models.change import Change
    from app.models.pull_request import PullRequest
    
    change = Change(
        id=str(uuid4()),
        repository_id=repo.id,
        actor_id=agent.id,
        intent="intent",
        status="proposed",
        resulting_commit="commit",
        base_commit="base",
        operation_key="op_key"
    )
    db.add(change)
    db.flush()
    
    pr = PullRequest(
        id=str(uuid4()),
        repository_id=repo.id,
        author_id=agent.id,
        title="PR",
        source_change_id=change.id,
        target_branch="main"
    )
    db.add(pr)
    db.flush()
    
    task_db = db.scalar(select(Task).where(Task.id == task.id))
    task_db.status = Task.STATUS_IN_PROGRESS
    task_db.resulting_change_id = change.id
    task_db.resulting_pull_request_id = pr.id
    db.commit()
    
    # Complete the task
    task_service.complete_task(task.id, user.id)
    
    # Verify session is revoked
    session_db = db.scalar(select(AgentSession).where(AgentSession.id == session.id))
    assert session_db.status == "revoked"
    assert session_db.revoked_at is not None
