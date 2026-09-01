from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from app.core.security import hash_password
from app.models.agent import Agent
from app.models.user import User


def make_user(db, user_id="subagent-user"):
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


def make_agent(db, owner_id, agent_id="subagent-parent"):
    raw_token = "sutra_agent_parent_secret"
    agent = Agent(
        id=agent_id,
        owner_id=owner_id,
        name="Parent Agent",
        token_hash=hash_password(raw_token),
        token_prefix=raw_token[:16],
        status="active",
        is_active=True,
    )
    db.add(agent)
    db.commit()
    db.refresh(agent)
    return agent, raw_token


def test_agent_can_spawn_subagent(client, db):
    user = make_user(db)
    agent, raw_token = make_agent(db, user.id)
    
    # Authenticate parent agent to get session token
    session_resp = client.post(
        "/v1/agents/session",
        json={"token": raw_token}
    )
    assert session_resp.status_code == 201
    session_token = session_resp.json()["token"]
    
    # Spawn subagent
    spawn_resp = client.post(
        "/v1/agents/spawn",
        json={"name": "Worker Thread 1"},
        headers={"Authorization": f"Bearer {session_token}"}
    )
    
    assert spawn_resp.status_code == 201
    data = spawn_resp.json()
    assert data["name"] == "Worker Thread 1"
    sub_token = data["token"]
    assert sub_token.startswith("sutra_subagent_")
    
    # Verify subagent can authenticate
    sub_session_resp = client.post(
        "/v1/agents/session",
        json={"token": sub_token}
    )
    assert sub_session_resp.status_code == 201
    
    # We can also check DB to verify parent_agent_id
    from sqlalchemy import select
    sub = db.scalar(select(Agent).where(Agent.id == data["id"]))
    assert sub.parent_agent_id == agent.id
    assert sub.owner_id == user.id
