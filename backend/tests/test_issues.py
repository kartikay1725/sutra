import pytest
from uuid import uuid4
from app.models.actor import Actor
from app.models.agent import Agent
from app.models.repository import Repository
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
    
    actor = Actor(
        id=user.id,
        type="user",
        name=user.username,
    )
    db.add(actor)
    db.commit()
    return user


def make_repo(db, owner_id, repo_name="issue-repo"):
    repo = Repository(
        owner_id=owner_id,
        name=repo_name,
        slug=repo_name,
        description="test repo",
        storage_key="test-storage-key",
    )
    db.add(repo)
    db.commit()
    db.refresh(repo)
    return repo


def make_agent(db, owner_id):
    agent_id = str(uuid4())
    agent = Agent(
        id=agent_id,
        owner_id=owner_id,
        name="Test Agent",
        description="Test Agent Desc",
        token_hash="fake_hash",
        token_prefix="fake_",
    )
    db.add(agent)
    
    actor = Actor(
        id=agent.id,
        type="agent",
        name=agent.name,
    )
    db.add(actor)
    db.commit()
    return agent


def test_issues_api(client, db):
    user = make_user(db)
    repo = make_repo(db, user.id)
    agent = make_agent(db, user.id)
    
    login_resp = client.post(
        "/v1/auth/login",
        json={"login": user.email, "password": "password"},
    )
    user_token = login_resp.json()["access_token"]
    auth_headers = {"Authorization": f"Bearer {user_token}"}
    
    # 1. Create issue as user
    resp = client.post(
        f"/v1/repositories/{user.username}/{repo.name}/issues",
        headers=auth_headers,
        json={
            "title": "Bug in API",
            "body": "It crashes.",
        }
    )
    assert resp.status_code == 201
    issue = resp.json()
    assert issue["title"] == "Bug in API"
    assert issue["author_id"] == user.id
    
    # 2. Create issue as agent
    resp_agent = client.post(
        f"/v1/repositories/{user.username}/{repo.name}/issues",
        headers=auth_headers,
        json={
            "title": "Refactor requested",
            "body": "Please refactor.",
            "author_id": agent.id,
        }
    )
    assert resp_agent.status_code == 201
    issue_agent = resp_agent.json()
    assert issue_agent["author_id"] == agent.id

    # 3. List issues
    list_resp = client.get(
        f"/v1/repositories/{user.username}/{repo.name}/issues",
        headers=auth_headers,
    )
    assert list_resp.status_code == 200
    assert len(list_resp.json()) == 2
    
    # 4. Add comment to issue
    comment_resp = client.post(
        f"/v1/repositories/{user.username}/{repo.name}/issues/{issue['id']}/comments",
        headers=auth_headers,
        json={
            "body": "I will fix it.",
        }
    )
    assert comment_resp.status_code == 201
    comment = comment_resp.json()
    assert comment["body"] == "I will fix it."
