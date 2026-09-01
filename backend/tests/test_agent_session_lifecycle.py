from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.api.agent_dependencies import (
    SESSION_IDLE_TIMEOUT_SECONDS,
)
from app.core.security import hash_password
from app.models.agent import Agent
from app.models.agent_session import AgentSession
from app.models.user import User
from app.services.agent_session_service import (
    cleanup_agent_sessions,
)


def make_user(db, user_id):
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


def make_agent(db, owner_id, agent_id):
    raw_token = f"sutra_agent_{agent_id}_secret"

    agent = Agent(
        id=agent_id,
        owner_id=owner_id,
        name=f"Agent {agent_id}",
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


def test_cleanup_does_not_delete_active_session(db):
    user = make_user(db, "cleanup-user")
    agent, _ = make_agent(
        db,
        user.id,
        "cleanup-agent",
    )

    now = datetime.now(timezone.utc)

    session = AgentSession(
        agent_id=agent.id,
        token_hash=hash_password("session-token"),
        token_prefix="sutra_session_cleanup",
        status="active",
        created_at=now - timedelta(days=30),
        expires_at=now + timedelta(minutes=10),
        last_seen_at=now,
    )

    db.add(session)
    db.commit()

    deleted = cleanup_agent_sessions(db)

    assert deleted == 0

    assert db.scalar(
        select(AgentSession).where(
            AgentSession.id == session.id
        )
    ) is not None


def test_cleanup_removes_old_expired_session(db):
    user = make_user(db, "cleanup-expired-user")
    agent, _ = make_agent(
        db,
        user.id,
        "cleanup-expired-agent",
    )

    now = datetime.now(timezone.utc)

    session = AgentSession(
        agent_id=agent.id,
        token_hash=hash_password("expired-session"),
        token_prefix="sutra_session_expired",
        status="expired",
        created_at=now - timedelta(days=30),
        expires_at=now - timedelta(days=29),
        last_seen_at=now - timedelta(days=29),
    )

    db.add(session)
    db.commit()

    deleted = cleanup_agent_sessions(db)

    assert deleted == 1

    assert db.scalar(
        select(AgentSession).where(
            AgentSession.id == session.id
        )
    ) is None


def test_cleanup_removes_old_revoked_session(db):
    user = make_user(db, "cleanup-revoked-user")
    agent, _ = make_agent(
        db,
        user.id,
        "cleanup-revoked-agent",
    )

    now = datetime.now(timezone.utc)

    session = AgentSession(
        agent_id=agent.id,
        token_hash=hash_password("revoked-session"),
        token_prefix="sutra_session_revoked",
        status="revoked",
        created_at=now - timedelta(days=30),
        expires_at=now + timedelta(minutes=10),
        last_seen_at=now - timedelta(days=30),
        revoked_at=now - timedelta(days=29),
    )

    db.add(session)
    db.commit()

    deleted = cleanup_agent_sessions(db)

    assert deleted == 1
