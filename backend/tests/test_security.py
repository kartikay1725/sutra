import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from app.models.repository import Repository
from app.models.user import User

def test_unauthenticated_repository_read_private(
    client: TestClient,
    db: Session,
):
    test_user = User(
        username="testuser",
        email="test@example.com",
        password_hash="dummy",
    )
    db.add(test_user)
    db.commit()

    repository = Repository(
        owner_id=test_user.id,
        name="private-repo",
        slug="private-repo",
        visibility="private",
        storage_key="dummy",
    )
    db.add(repository)
    db.commit()

    response = client.get(f"/v1/repositories/{test_user.username}/private-repo")
    assert response.status_code == 404
    assert response.json()["detail"] == "Repository not found"

def test_git_path_traversal(
    client: TestClient,
    db: Session,
):
    test_user = User(
        username="testuser2",
        email="test2@example.com",
        password_hash="dummy",
    )
    db.add(test_user)
    db.commit()

    # The route matches /{owner}/{repo}.git/{git_path:path}
    # We can send an invalid git path
    response = client.get(f"/{test_user.username}/repo.git/../info/refs")
    # FastAPI might normalize this to /username/info/refs which is a 404
    # If we urlencode:
    response = client.get(f"/{test_user.username}/repo.git/..%2finfo%2frefs")
    assert response.status_code in (400, 404)
    if response.status_code == 400:
        assert response.json()["detail"] == "Invalid Git endpoint"

def test_git_http_error_leakage(
    client: TestClient,
    db: Session,
):
    test_user = User(
        username="testuser3",
        email="test3@example.com",
        password_hash="dummy",
    )
    db.add(test_user)
    db.commit()

    # Send an invalid git-upload-pack request that causes git to fail
    response = client.post(
        f"/{test_user.username}/repo.git/git-upload-pack",
        content=b"0000",
        headers={"Content-Type": "application/x-git-upload-pack-request"}
    )
    if response.status_code == 500:
        assert "Internal Server Error" in response.text
        assert "git" not in response.text.lower() or "internal server error during git operation" in response.text.lower()
