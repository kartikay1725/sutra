import os
import pytest
from uuid import uuid4
from datetime import datetime, timezone, timedelta
from fastapi import status
from sqlalchemy import select

from app.models.user import User
from app.models.repository import Repository
from app.models.agent import Agent
from app.models.actor import Actor
from app.models.agent_session import AgentSession
from app.models.task import Task
from app.core.security import hash_password
from app.services.knowledge_graph_service import index_engineering_lifecycle


def test_live_surfaces_verification(client, db):
    """
    Live verification of the completed product surfaces on the live substrate:
    1. Knowledge Graph lifecycle indexing and queries.
    2. AI Assistant scoped engineering context.
    3. Discussions & Governed Agent Participation with explicit SUTRA identity.
    """
    # 1. Resolve or create live repository pointer for kartikay1725/dam-project
    repo = db.scalar(
        select(Repository).where(
            (Repository.name == "dam-project") | (Repository.slug == "dam-project")
        )
    )

    owner_user = db.scalar(select(User).where(User.username == "kartikay1725"))
    if not owner_user:
        owner_user = User(
            id=str(uuid4()),
            username="kartikay1725",
            email="kartikay1725@example.com",
            password_hash=hash_password("TestPassword123!"),
        )
        db.add(owner_user)
        db.flush()

    if not repo:
        repo = Repository(
            id=str(uuid4()),
            owner_id=owner_user.id,
            name="dam-project",
            slug="dam-project",
            storage_key="kartikay1725/dam-project",
            default_branch="main",
            visibility="public",
            provider_type="github",
        )
        db.add(repo)
        db.commit()
        db.refresh(repo)

    # 2. Authenticate Human User
    from tests.conftest import ensure_test_actor
    ensure_test_actor(db, owner_user)

    # Ensure user has a known password or override token
    login_resp = client.post(
        "/v1/auth/login",
        json={"login": owner_user.email, "password": "TestPassword123!"},
    )
    if login_resp.status_code == 200:
        user_token = login_resp.json()["access_token"]
    else:
        from app.core.security import create_access_token
        user_token = create_access_token(owner_user.id)

    human_headers = {"Authorization": f"Bearer {user_token}"}

    # 3. Setup Governed Agent & Active Session
    agent = db.scalar(select(Agent).where(Agent.name == "Atlas-Live-Verification"))
    if not agent:
        agent = Agent(
            id=str(uuid4()),
            owner_id=owner_user.id,
            name="Atlas-Live-Verification",
            description="Agent for live surface verification",
            token_hash=hash_password("agent-live-token"),
            token_prefix="sutra_agent_l",
            status="active",
            is_active=True,
        )
        db.add(agent)
        db.flush()

    agent_actor = db.scalar(select(Actor).where(Actor.id == agent.id))
    if not agent_actor:
        agent_actor = Actor(
            id=agent.id,
            owner_id=owner_user.id,
            type="agent",
            name=agent.name,
            capabilities='["repository.read", "repository.write", "discussion.write", "change.create"]',
        )
        db.add(agent_actor)
        db.flush()

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

    # Link an engineering task
    task = Task(
        id=str(uuid4()),
        repository_id=repo.id,
        created_by=owner_user.id,
        assigned_agent_id=agent.id,
        title="Live Surface Integration Task",
        description="Verify knowledge graph, assistant, and discussions against dam-project",
        status="in_progress",
    )
    db.add(task)
    db.commit()

    agent_headers = {"Authorization": f"Bearer {session_token}"}

    # =========================================================================
    # VERIFICATION 1: KNOWLEDGE GRAPH
    # =========================================================================
    # Run lifecycle indexing on live repo
    kg_counts = index_engineering_lifecycle(db, repo.id)
    assert isinstance(kg_counts, dict)
    assert kg_counts["nodes"] >= 1

    # Query Knowledge Graph API
    kg_resp = client.get(
        f"/v1/repositories/{owner_user.username}/{repo.name}/graph/data",
        headers=human_headers,
    )
    assert kg_resp.status_code == 200, f"KG API failed: {kg_resp.text}"
    kg_data = kg_resp.json()
    assert "nodes" in kg_data
    assert "edges" in kg_data
    node_names = [n["name"] for n in kg_data["nodes"]]
    assert any("Live Surface Integration Task" in name for name in node_names)

    # =========================================================================
    # VERIFICATION 2: AI ASSISTANT SCOPED CONTEXT
    # =========================================================================
    # Create thread scoped to task
    thread_resp = client.post(
        f"/v1/repositories/{owner_user.username}/{repo.name}/assistant/threads",
        headers=human_headers,
        json={
            "title": "Live Verification Thread",
            "task_id": task.id,
        },
    )
    assert thread_resp.status_code == 201, f"Thread creation failed: {thread_resp.text}"
    thread = thread_resp.json()
    thread_id = thread["id"]
    assert thread["task_id"] == task.id

    # Post question
    msg_resp = client.post(
        f"/v1/assistant/threads/{thread_id}/messages",
        headers=human_headers,
        json={"content": "What is the status of the current task?"},
    )
    assert msg_resp.status_code == 201, f"Message creation failed: {msg_resp.text}"
    messages = msg_resp.json()
    assert len(messages) == 2
    ai_content = messages[1]["content"]
    assert len(ai_content) > 0
    # Must be grounded in the repo/task context
    assert repo.name in ai_content or "Live Surface" in ai_content or "Task" in ai_content

    # =========================================================================
    # VERIFICATION 3: DISCUSSIONS & GOVERNED AGENT PARTICIPATION
    # =========================================================================
    # Human creates discussion
    disc_resp = client.post(
        f"/v1/repositories/{owner_user.username}/{repo.name}/discussions",
        headers=human_headers,
        json={
            "title": "Live Verification: Architectural Sync",
            "body": "Verifying governed discussions with agent participation.",
            "category": "General",
            "task_id": task.id,
        },
    )
    assert disc_resp.status_code == 201, f"Discussion creation failed: {disc_resp.text}"
    discussion_id = disc_resp.json()["id"]

    # Governed Agent participates with AgentSession
    comment_resp = client.post(
        f"/v1/repositories/{owner_user.username}/{repo.name}/discussions/{discussion_id}/comments",
        headers=agent_headers,
        json={
            "body": "Atlas agent reporting: All surfaces verified and active.",
        },
    )
    assert comment_resp.status_code == 201, f"Agent comment failed: {comment_resp.text}"
    comment_data = comment_resp.json()

    # Explicit SUTRA Agent identity verification
    assert comment_data["author_type"] == "agent"
    assert comment_data["agent_id"] == agent.id
    assert comment_data["session_id"] == agent_session.id
    assert f"[SUTRA Agent: {agent.name}]" in comment_data["body"]
    assert f"Session ID: {agent_session.id}" in comment_data["body"]
    assert "All surfaces verified and active" in comment_data["body"]
