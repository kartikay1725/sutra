import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.models.user import User


@pytest.fixture
def auth_headers(db: Session) -> dict:
    from app.models.actor import Actor
    from uuid import uuid4
    
    # Clean up first if needed
    db.execute(text("DELETE FROM users WHERE username='orgcreator'"))
    db.execute(text("DELETE FROM actors WHERE name='orgcreator'"))
    db.commit()
    
    user_id = str(uuid4())
    actor = Actor(id=user_id, type="user", name="orgcreator", capabilities="[]")
    db.add(actor)
    
    user = User(
        id=user_id,
        username="orgcreator",
        email="orgcreator@example.com",
        password_hash="fake",
    )
    db.add(user)
    db.commit()

    from app.core.security import create_access_token
    token = create_access_token(user_id)
    return {"Authorization": f"Bearer {token}"}


def test_create_organization(client: TestClient, auth_headers):
    response = client.post(
        "/v1/organizations",
        json={
            "name": "acme-corp",
            "display_name": "ACME Corporation",
            "description": "Building everything"
        },
        headers=auth_headers
    )
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "acme-corp"
    
    # Test fetch
    res = client.get("/v1/organizations/acme-corp")
    assert res.status_code == 200
    assert res.json()["display_name"] == "ACME Corporation"
    
    # Test members
    res_mem = client.get("/v1/organizations/acme-corp/members")
    assert res_mem.status_code == 200
    members = res_mem.json()
    assert len(members) == 1
    assert members[0]["role"] == "owner"
