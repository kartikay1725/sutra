import pytest
from uuid import uuid4
from app.models.agent import Agent
from app.models.user import User
from app.core.security import hash_password


def make_user(db):
    user_id = str(uuid4())
    user = User(
        id=user_id,
        username=f"user-{user_id[:8]}",
        email=f"{user_id[:8]}@example.com",
        password_hash=hash_password("password"),
    )
    db.add(user)
    db.commit()
    return user


def make_agent(db, owner_id):
    agent_id = str(uuid4())
    agent = Agent(
        id=agent_id,
        owner_id=owner_id,
        name=f"Agent {agent_id[:8]}",
        description="Test",
        token_hash="fake_hash",
        token_prefix="fake_",
    )
    db.add(agent)
    db.commit()
    return agent


def test_agent_messages_api(client, db):
    user = make_user(db)
    agent_a = make_agent(db, user.id)
    agent_b = make_agent(db, user.id)
    
    login_resp = client.post(
        "/v1/auth/login",
        json={"login": user.email, "password": "password"},
    )
    user_token = login_resp.json()["access_token"]
    auth_headers = {"Authorization": f"Bearer {user_token}"}
    
    # 1. Agent A sends to Agent B
    resp = client.post(
        "/v1/agent-messages",
        headers=auth_headers,
        json={
            "sender_agent_id": agent_a.id,
            "receiver_agent_id": agent_b.id,
            "topic_id": "PR-123",
            "content": "Can you review this?"
        }
    )
    assert resp.status_code == 201
    msg = resp.json()
    assert msg["sender_agent_id"] == agent_a.id
    assert msg["receiver_agent_id"] == agent_b.id
    
    # 2. Agent B checks messages
    list_resp = client.get(
        f"/v1/agent-messages?agent_id={agent_b.id}",
        headers=auth_headers,
    )
    assert list_resp.status_code == 200
    msgs = list_resp.json()
    assert len(msgs) == 1
    assert msgs[0]["content"] == "Can you review this?"
    
    # 3. Test filtering by topic
    topic_resp = client.get(
        f"/v1/agent-messages?agent_id={agent_a.id}&topic_id=PR-123",
        headers=auth_headers,
    )
    assert topic_resp.status_code == 200
    assert len(topic_resp.json()) == 1
    
    empty_topic_resp = client.get(
        f"/v1/agent-messages?agent_id={agent_a.id}&topic_id=PR-999",
        headers=auth_headers,
    )
    assert empty_topic_resp.status_code == 200
    assert len(empty_topic_resp.json()) == 0
