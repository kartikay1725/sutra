import pytest
from sqlalchemy.orm import Session
from app.models.user import User
from app.core.security import hash_password
import uuid

@pytest.fixture()
def test_user(db: Session):
    from tests.conftest import ensure_test_actor
    user_id = str(uuid.uuid4())
    user = User(
        id=user_id,
        username="testuser",
        email="testuser@example.com",
        password_hash=hash_password("password123"),
        email_verified=True,
    )
    db.add(user)
    db.flush()
    ensure_test_actor(db, user)
    db.commit()
    return user

def test_login_valid_credentials(client, test_user):
    response = client.post("/v1/auth/login", json={"login": "testuser", "password": "password123"})
    assert response.status_code == 200
    assert "access_token" in response.json()

def test_login_invalid_credentials(client, test_user):
    response = client.post("/v1/auth/login", json={"login": "testuser", "password": "wrongpassword"})
    assert response.status_code == 401

def test_logout_and_session_revocation(client, test_user):
    # Login
    response = client.post("/v1/auth/login", json={"login": "testuser", "password": "password123"})
    token = response.json()["access_token"]
    
    # Verify we can access /me
    me_resp = client.get("/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me_resp.status_code == 200
    
    # Logout
    logout_resp = client.post("/v1/auth/logout", headers={"Authorization": f"Bearer {token}"})
    assert logout_resp.status_code == 204
    
    # Verify session is revoked
    me_resp2 = client.get("/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me_resp2.status_code == 401
    assert me_resp2.json()["detail"] == "Session is revoked"

def test_controlled_replay(client, test_user):
    """
    Test whether a copied session credential alone can authenticate a second simulated client,
    AFTER the first client logs out. Also ensures standard JWT replay without DB session check fails.
    """
    # 1. Authenticate normally
    response = client.post("/v1/auth/login", json={"login": "testuser", "password": "password123"})
    token = response.json()["access_token"]
    
    # 2. Logout (representing the original client invalidating it, or it being revoked)
    client.post("/v1/auth/logout", headers={"Authorization": f"Bearer {token}"})
    
    # 3. Simulate second client trying to replay the stolen token
    # It must fail because the session is revoked in the database, even though JWT signature is valid
    replay_resp = client.get("/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert replay_resp.status_code == 401
    assert replay_resp.json()["detail"] == "Session is revoked"

def test_brute_force_protection(client, test_user):
    # Test rate limiting on login endpoint
    # slowapi default rate limit might apply, we configured 5/minute
    for _ in range(5):
        client.post("/v1/auth/login", json={"login": "testuser", "password": "password123"})
        
    response = client.post("/v1/auth/login", json={"login": "testuser", "password": "password123"})
    # Status code could be 429 Too Many Requests
    assert response.status_code == 429
