import pytest
from datetime import datetime, timezone, timedelta
from uuid import uuid4

from app.api.dependencies import get_current_user
from app.main import app
from app.models.user import User
from app.models.repository import Repository
from app.models.agent import Agent
from app.models.agent_session import AgentSession
from app.models.task import Task
from app.models.actor import Actor
from app.services.repository_service import RepositoryService
from app.core.security import hash_password


def setup_discussion_fixtures(db):
    from tests.conftest import ensure_test_actor

    user = User(
        id=str(uuid4()),
        username=f"disc_user_{uuid4().hex[:8]}",
        email=f"disc_user_{uuid4().hex[:8]}@example.com",
        password_hash=hash_password("password"),
    )
    db.add(user)
    db.flush()
    ensure_test_actor(db, user)

    repo = RepositoryService(db).create(
        owner_id=user.id,
        name=f"disc_repo_{uuid4().hex[:8]}",
        description="Discussion Test Repo",
        visibility="private",
    )

    agent = Agent(
        id=str(uuid4()),
        owner_id=user.id,
        name="Atlas-Discussion-Agent",
        description="Autonomous testing agent for discussions",
        token_hash=hash_password("agent-token"),
        token_prefix="sutra_agent_t",
        status="active",
        is_active=True,
    )
    db.add(agent)
    db.flush()

    task = Task(
        id=str(uuid4()),
        repository_id=repo.id,
        created_by=user.id,
        assigned_agent_id=agent.id,
        title="Refactor Authentication Subsystem",
        description="Discuss architecture changes with humans",
        status="in_progress",
    )
    db.add(task)
    db.flush()

    agent_actor = Actor(
        id=agent.id,
        owner_id=user.id,
        type="agent",
        name=agent.name,
        capabilities='["repository.read", "repository.write", "discussion.write"]',
    )
    db.add(agent_actor)
    db.flush()

    # Create active agent session
    session_token = f"sutra_session_{uuid4().hex}_{uuid4().hex}"
    agent_session = AgentSession(
        id=str(uuid4()),
        agent_id=agent.id,
        token_hash=hash_password(session_token),
        token_prefix=session_token[:32],
        status="active",
        created_at=datetime.now(timezone.utc),
        expires_at=datetime.now(timezone.utc) + timedelta(hours=2),
        last_seen_at=datetime.now(timezone.utc),
    )
    db.add(agent_session)
    db.commit()

    return user, repo, agent, task, agent_session, session_token


def test_human_and_agent_discussions(client, db):
    user, repo, agent, task, agent_session, session_token = setup_discussion_fixtures(db)

    # 1. Login as human user
    login_resp = client.post(
        "/v1/auth/login",
        json={"login": user.email, "password": "password"},
    )
    assert login_resp.status_code == 200
    user_token = login_resp.json()["access_token"]
    human_headers = {"Authorization": f"Bearer {user_token}"}

    # 2. Human creates a discussion
    resp = client.post(
        f"/v1/repositories/{user.username}/{repo.name}/discussions",
        headers=human_headers,
        json={
            "title": "Architecture Question on Token Revocation",
            "body": "Should we use Redis blocklist or DB flags?",
            "category": "Architecture",
        },
    )
    assert resp.status_code == 201
    disc_data = resp.json()
    assert disc_data["title"] == "Architecture Question on Token Revocation"
    assert disc_data["author_type"] == "human"
    assert disc_data["author_name"] == user.username
    discussion_id = disc_data["id"]

    # 3. Agent replies to the discussion using AgentSession token
    agent_headers = {"Authorization": f"Bearer {session_token}"}
    comment_resp = client.post(
        f"/v1/repositories/{user.username}/{repo.name}/discussions/{discussion_id}/comments",
        headers=agent_headers,
        json={
            "body": "Redis blocklist is O(1) and eliminates DB pressure under high load.",
        },
    )
    assert comment_resp.status_code == 201
    comment_data = comment_resp.json()
    assert comment_data["author_type"] == "agent"
    assert comment_data["agent_id"] == agent.id
    assert comment_data["session_id"] == agent_session.id
    # Explicit SUTRA Agent identity prefix must be embedded in the body
    assert "[SUTRA Agent: Atlas-Discussion-Agent]" in comment_data["body"]
    assert f"Session ID: {agent_session.id}" in comment_data["body"]
    assert "Redis blocklist is O(1)" in comment_data["body"]

    # 4. Agent creates a new discussion linked to a Task
    agent_disc_resp = client.post(
        f"/v1/repositories/{user.username}/{repo.name}/discussions",
        headers=agent_headers,
        json={
            "title": "Proposed Migration for Auth Subsystem",
            "body": "I propose migrating session tokens to Redis streams.",
            "category": "RFC",
            "task_id": task.id,
        },
    )
    assert agent_disc_resp.status_code == 201
    agent_disc_data = agent_disc_resp.json()
    assert agent_disc_data["author_type"] == "agent"
    assert agent_disc_data["agent_id"] == agent.id
    assert agent_disc_data["task_id"] == task.id
    assert "[SUTRA Agent: Atlas-Discussion-Agent]" in agent_disc_data["body"]
    assert f"Task ID: {task.id}" in agent_disc_data["body"]

    # 5. List discussions verifies distinct identities and context
    list_resp = client.get(
        f"/v1/repositories/{user.username}/{repo.name}/discussions",
        headers=human_headers,
    )
    assert list_resp.status_code == 200
    all_discs = list_resp.json()
    assert len(all_discs) == 2
    types = {d["author_type"] for d in all_discs}
    assert "human" in types
    assert "agent" in types

    # 6. Verify expired / invalid session is rejected
    expired_token = f"sutra_session_{uuid4().hex}"
    invalid_headers = {"Authorization": f"Bearer {expired_token}"}
    fail_resp = client.post(
        f"/v1/repositories/{user.username}/{repo.name}/discussions",
        headers=invalid_headers,
        json={
            "title": "Unauthorized Discussion",
            "body": "This should fail",
        },
    )
    assert fail_resp.status_code == 401
