import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from sqlalchemy import text
from uuid import uuid4

from app.models.user import User
from app.models.actor import Actor
from app.models.repository import Repository
from app.models.social import RepositoryStar

@pytest.fixture
def test_data(db: Session):
    db.execute(text("DELETE FROM repository_stars"))
    db.execute(text("DELETE FROM repositories WHERE name='explore-repo'"))
    db.execute(text("DELETE FROM users WHERE username='explorer'"))
    db.execute(text("DELETE FROM actors WHERE name='explorer'"))
    db.commit()
    
    user_id = str(uuid4())
    actor = Actor(id=user_id, type="user", name="explorer", capabilities="[]")
    db.add(actor)
    
    user = User(
        id=user_id,
        username="explorer",
        email="explorer@example.com",
        password_hash="fake",
    )
    db.add(user)
    
    repo_id = str(uuid4())
    repo = Repository(
        id=repo_id,
        owner_id=user_id,
        name="explore-repo",
        slug="explore-repo",
        visibility="public",
        storage_key="test-explore"
    )
    db.add(repo)
    
    star = RepositoryStar(actor_id=user_id, repository_id=repo_id)
    db.add(star)
    
    db.commit()
    return user_id, repo_id

def test_get_profile(client: TestClient, test_data):
    user_id, repo_id = test_data
    response = client.get("/v1/profiles/explorer")
    assert response.status_code == 200
    data = response.json()
    assert data["username"] == "explorer"

def test_get_contributions(client: TestClient, test_data):
    response = client.get("/v1/profiles/explorer/contributions")
    assert response.status_code == 200
    data = response.json()
    assert "total_contributions" in data
    assert "days" in data

def test_explore_trending(client: TestClient, test_data):
    response = client.get("/v1/explore/trending/repositories")
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 1
    assert any(r["name"] == "explore-repo" for r in data)

def test_search(client: TestClient, test_data):
    response = client.get("/v1/search?q=explore")
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 1
