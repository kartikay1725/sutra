from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from app.core.security import hash_password
from app.models.agent_registration import AgentRegistrationRequest
from app.models.user import User


def make_user(db, user_id="reg-user"):
    from tests.conftest import ensure_test_actor
    user = User(
        id=user_id,
        username=f"user-{user_id}",
        email=f"{user_id}@example.com",
        password_hash=hash_password("password"),
        email_verified=True,
    )
    db.add(user)
    db.flush()
    ensure_test_actor(db, user)
    db.commit()
    db.refresh(user)
    return user


def test_agent_registration_device_flow(client, db):
    user = make_user(db)
    
    # 1. 3rd party creates registration request
    resp = client.post(
        "/v1/agents/register",
        json={
            "agent_name": "Claude Code",
            "owner_username": user.username,
            "provider": "Anthropic",
            "requested_capabilities": ["repository.read", "repository.write"],
        }
    )
    
    assert resp.status_code == 201
    data = resp.json()
    reg_id = data["id"]
    polling_token = data["polling_token"]
    
    # 2. 3rd party polls status (pending)
    poll_resp = client.get(
        f"/v1/agents/register/{reg_id}/status",
        params={"polling_token": polling_token}
    )
    assert poll_resp.status_code == 200
    assert poll_resp.json()["status"] == "pending"
    assert poll_resp.json()["permanent_token"] is None
    
    # User authenticates
    login_resp = client.post(
        "/v1/auth/login",
        json={
            "login": user.email,
            "password": "password",
        },
    )
    user_token = login_resp.json()["access_token"]
    auth_headers = {"Authorization": f"Bearer {user_token}"}
    
    # 3. User lists pending
    list_resp = client.get(
        "/v1/agents/registrations/pending",
        headers=auth_headers
    )
    assert list_resp.status_code == 200
    assert len(list_resp.json()) == 1
    assert list_resp.json()[0]["id"] == reg_id
    
    # 4. User approves
    approve_resp = client.post(
        f"/v1/agents/registrations/{reg_id}/approve",
        headers=auth_headers
    )
    assert approve_resp.status_code == 200
    
    # 5. 3rd party polls again (approved)
    poll_resp2 = client.get(
        f"/v1/agents/register/{reg_id}/status",
        params={"polling_token": polling_token}
    )
    assert poll_resp2.status_code == 200
    assert poll_resp2.json()["status"] == "approved"
    assert poll_resp2.json()["permanent_token"].startswith("sutra_agent_")
    
    
def test_agent_registration_reject(client, db):
    user = make_user(db, "reject-user")
    
    resp = client.post(
        "/v1/agents/register",
        json={"agent_name": "Bad Agent", "owner_username": user.username}
    )
    reg_id = resp.json()["id"]
    polling_token = resp.json()["polling_token"]
    
    login_resp = client.post(
        "/v1/auth/login",
        json={"login": user.email, "password": "password"},
    )
    user_token = login_resp.json()["access_token"]
    auth_headers = {"Authorization": f"Bearer {user_token}"}
    
    reject_resp = client.post(
        f"/v1/agents/registrations/{reg_id}/reject",
        headers=auth_headers
    )
    assert reject_resp.status_code == 200
    
    poll_resp = client.get(
        f"/v1/agents/register/{reg_id}/status",
        params={"polling_token": polling_token}
    )
    assert poll_resp.status_code == 200
    assert poll_resp.json()["status"] == "rejected"
    assert poll_resp.json()["permanent_token"] is None


def test_agent_registration_cannot_be_approved_by_different_user(client, db):
    owner = make_user(db, "owner-user")
    other = make_user(db, "other-user")

    resp = client.post(
        "/v1/agents/register",
        json={
            "agent_name": "Owner Agent",
            "owner_username": owner.username,
        },
    )
    assert resp.status_code == 201
    reg_id = resp.json()["id"]

    login_resp = client.post(
        "/v1/auth/login",
        json={"login": other.email, "password": "password"},
    )
    other_token = login_resp.json()["access_token"]
    other_headers = {"Authorization": f"Bearer {other_token}"}

    list_resp = client.get(
        "/v1/agents/registrations/pending",
        headers=other_headers,
    )
    assert list_resp.status_code == 200
    assert all(item["id"] != reg_id for item in list_resp.json())

    approve_resp = client.post(
        f"/v1/agents/registrations/{reg_id}/approve",
        headers=other_headers,
    )
    assert approve_resp.status_code == 404
