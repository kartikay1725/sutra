from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import password_hash
from app.models.agent import Agent
from app.models.agent_session import AgentSession
from app.models.user import User


def _user(db: Session, username: str) -> User:
    user = User(
        username=username,
        email=f"{username}@example.com",
        password_hash=password_hash.hash("TestPassword123!"),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _agent(db: Session, owner: User, name: str) -> Agent:
    agent = Agent(
        owner_id=owner.id,
        name=name,
        token_hash=password_hash.hash("sutra-agent-test-token"),
        token_prefix="sutra_agent_t",
        status="active",
        is_active=True,
    )
    db.add(agent)
    db.commit()
    db.refresh(agent)
    return agent


def _override_user(client: TestClient, user: User):
    from app.main import app
    from app.api.dependencies import get_current_user

    app.dependency_overrides[get_current_user] = lambda: user


def test_agent_session_list_is_owner_scoped(client: TestClient, db: Session):
    owner = _user(db, "agent-session-owner")
    other = _user(db, "agent-session-other")
    agent = _agent(db, owner, "Session Agent")

    now = datetime.now(timezone.utc)
    db.add(
        AgentSession(
            agent_id=agent.id,
            token_hash=password_hash.hash("session-token"),
            token_prefix="sutra_sess_t",
            status="active",
            created_at=now,
            expires_at=now + timedelta(hours=1),
            last_seen_at=now,
        )
    )
    db.commit()

    _override_user(client, owner)
    response = client.get(f"/v1/agents/{agent.id}/sessions")
    assert response.status_code == 200, response.text
    assert len(response.json()) == 1

    _override_user(client, other)
    denied = client.get(f"/v1/agents/{agent.id}/sessions")
    assert denied.status_code == 404
