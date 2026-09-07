import pytest
from uuid import uuid4
from datetime import datetime, timezone
from fastapi import status

from app.models.user import User
from app.models.repository import Repository
from app.models.task import Task
from app.models.change import Change
from app.models.pull_request import PullRequest
from app.models.agent import Agent
from app.models.actor import Actor
from app.core.security import hash_password
from app.services.repository_service import RepositoryService


def setup_assistant_comprehensive_fixtures(db):
    from tests.conftest import ensure_test_actor

    user_a = User(
        id=str(uuid4()),
        username=f"asst_usr_{uuid4().hex[:8]}",
        email=f"asst_usr_{uuid4().hex[:8]}@example.com",
        password_hash=hash_password("password"),
    )
    user_b = User(
        id=str(uuid4()),
        username=f"other_usr_{uuid4().hex[:8]}",
        email=f"other_usr_{uuid4().hex[:8]}@example.com",
        password_hash=hash_password("password"),
    )
    db.add_all([user_a, user_b])
    db.flush()
    ensure_test_actor(db, user_a)
    ensure_test_actor(db, user_b)

    repo = RepositoryService(db).create(
        owner_id=user_a.id,
        name=f"asst_repo_{uuid4().hex[:8]}",
        description="Engineering Assistant Test Repository",
        visibility="private",
    )

    agent = Agent(
        id=str(uuid4()),
        owner_id=user_a.id,
        name="Atlas-Code-Agent",
        description="Code generator",
        token_hash=hash_password("agent-token"),
        token_prefix="sutra_agent_t",
        status="active",
        is_active=True,
    )
    db.add(agent)
    db.flush()

    agent_actor = Actor(
        id=agent.id,
        owner_id=user_a.id,
        type="agent",
        name=agent.name,
        capabilities='["repository.read", "repository.write", "change.create"]',
    )
    db.add(agent_actor)
    db.flush()

    task = Task(
        id=str(uuid4()),
        repository_id=repo.id,
        created_by=user_a.id,
        assigned_agent_id=agent.id,
        title="Add OIDC Token Verification",
        description="Secure bearer tokens using RSA public keys",
        status="in_progress",
    )
    db.add(task)
    db.flush()

    change = Change(
        id=str(uuid4()),
        repository_id=repo.id,
        actor_id=agent.id,
        status="proposed",
        intent="Implement RSA-256 JWT validation",
    )
    db.add(change)
    db.flush()

    pr = PullRequest(
        id=str(uuid4()),
        repository_id=repo.id,
        source_change_id=change.id,
        author_id=agent.id,
        target_branch="main",
        status="open",
        title="feat: Implement RSA-256 JWT validation",
    )
    db.add(pr)
    db.flush()

    task.resulting_change_id = change.id
    task.resulting_pull_request_id = pr.id
    db.commit()

    return user_a, user_b, repo, task, change, pr, agent


def test_assistant_scoped_context_and_isolation(client, db):
    user_a, user_b, repo, task, change, pr, agent = setup_assistant_comprehensive_fixtures(db)

    # 1. Login user A and user B
    login_a = client.post("/v1/auth/login", json={"login": user_a.email, "password": "password"})
    token_a = login_a.json()["access_token"]
    headers_a = {"Authorization": f"Bearer {token_a}"}

    login_b = client.post("/v1/auth/login", json={"login": user_b.email, "password": "password"})
    token_b = login_b.json()["access_token"]
    headers_b = {"Authorization": f"Bearer {token_b}"}

    # 2. User A creates a scoped thread for a specific Task
    create_thread_resp = client.post(
        f"/v1/repositories/{user_a.username}/{repo.name}/assistant/threads",
        headers=headers_a,
        json={
            "title": "Reviewing OIDC Implementation",
            "task_id": task.id,
        },
    )
    assert create_thread_resp.status_code == 201
    thread = create_thread_resp.json()
    thread_id = thread["id"]
    assert thread["task_id"] == task.id
    assert "Reviewing OIDC Implementation" in thread["title"]

    # 3. Verify Thread Isolation: User B cannot access User A's thread
    user_b_access = client.get(
        f"/v1/assistant/threads/{thread_id}/messages",
        headers=headers_b,
    )
    assert user_b_access.status_code == 404

    # 4. User A asks "What changed in this task?"
    msg_resp = client.post(
        f"/v1/assistant/threads/{thread_id}/messages",
        headers=headers_a,
        json={"content": "What changed in this task?"},
    )
    assert msg_resp.status_code == 201
    messages = msg_resp.json()
    assert len(messages) == 2
    ai_reply = messages[1]["content"]

    # Should reference the scoped task and real change data
    assert "OIDC" in ai_reply
    assert "RSA" in ai_reply or "proposed" in ai_reply.lower()

    # 5. User A asks "What is the PR status?"
    msg_resp2 = client.post(
        f"/v1/assistant/threads/{thread_id}/messages",
        headers=headers_a,
        json={"content": "Why is this PR blocked?"},
    )
    assert msg_resp2.status_code == 201
    messages2 = msg_resp2.json()
    assert len(messages2) == 2
    ai_reply2 = messages2[1]["content"]
    assert len(ai_reply2) > 0

    # 6. Verify total messages in thread is 4
    list_msgs = client.get(
        f"/v1/assistant/threads/{thread_id}/messages",
        headers=headers_a,
    )
    assert list_msgs.status_code == 200
    assert len(list_msgs.json()) == 4
