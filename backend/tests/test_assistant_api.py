import pytest
from fastapi import status
from uuid import uuid4

from app.models.user import User
from app.models.repository import Repository
from app.services.repository_service import RepositoryService


def setup_assistant_fixtures(db):
    from tests.conftest import ensure_test_actor
    user_a = User(
        id=str(uuid4()),
        username=f"assistant_user_{uuid4().hex[:8]}",
        email=f"assistant_{uuid4().hex[:8]}@example.com",
        password_hash="hash",
    )
    db.add(user_a)
    db.flush()
    ensure_test_actor(db, user_a)

    repo = RepositoryService(db).create(
        owner_id=user_a.id,
        name=f"assistant_repo_{uuid4().hex[:8]}",
        description="Assistant Repo",
        visibility="private",
    )
    db.commit()

    return user_a, repo


def test_assistant_api_lifecycle(client, db):
    user_a, repo = setup_assistant_fixtures(db)

    from app.api.dependencies import get_current_user
    from app.main import app

    app.dependency_overrides[get_current_user] = lambda: user_a

    # 1. Create a thread
    thread_data = {"title": "Help with tests"}
    resp = client.post(
        f"/v1/repositories/{user_a.username}/{repo.name}/assistant/threads",
        json=thread_data,
    )
    assert resp.status_code == status.HTTP_201_CREATED
    thread_id = resp.json()["id"]
    assert resp.json()["title"] == "Help with tests"

    # 2. List threads
    resp = client.get(f"/v1/repositories/{user_a.username}/{repo.name}/assistant/threads")
    assert resp.status_code == status.HTTP_200_OK
    assert len(resp.json()) == 1
    assert resp.json()[0]["id"] == thread_id

    # 3. Create a message
    msg_data = {"content": "Can you explain the repository structure?"}
    resp = client.post(f"/v1/assistant/threads/{thread_id}/messages", json=msg_data)
    assert resp.status_code == status.HTTP_201_CREATED
    messages = resp.json()
    assert len(messages) == 2  # 1 User msg, 1 AI msg
    assert messages[0]["role"] == "user"
    assert messages[0]["content"] == "Can you explain the repository structure?"
    assert messages[1]["role"] == "assistant"
    # Content can be a real AI response or an error string from the Ollama connection
    assert isinstance(messages[1]["content"], str)
    assert len(messages[1]["content"]) > 0

    # 4. List messages
    resp = client.get(f"/v1/assistant/threads/{thread_id}/messages")
    assert resp.status_code == status.HTTP_200_OK
    fetched_messages = resp.json()
    assert len(fetched_messages) == 2
    assert fetched_messages[0]["role"] == "user"
    assert fetched_messages[1]["role"] == "assistant"

    app.dependency_overrides.clear()
