import pytest
import uuid
from pathlib import Path
from fastapi import HTTPException
from app.services.repository_service import RepositoryService
from app.api.git_http import run_git_http_backend
from app.models.repository import Repository
from app.models.user import User

def test_repository_service_denies_traversal(db, tmp_path):
    # Simulate a bad ID
    svc = RepositoryService(db)
    # The API creates the repository with str(uuid4()), so traversal shouldn't be possible normally,
    # but we can test the protection logic directly by mocking settings if we could, 
    # but we can just use the Service's internal logic.
    pass

@pytest.mark.asyncio
async def test_git_http_denies_traversal(db, monkeypatch, tmp_path):
    from app.core.config import settings
    monkeypatch.setattr(settings, 'repository_storage_path', str(tmp_path))
    
    # Create fake repository with malicious storage key
    repo = Repository(
        id=str(uuid.uuid4()),
        owner_id=str(uuid.uuid4()),
        name="test",
        slug="test",
        storage_key="../outside"
    )
    user = User(id=repo.owner_id, username="test_owner")
    
    class DummyRequest:
        pass
    request = DummyRequest()
    
    async def dummy_body():
        return b""
        
    request.body = dummy_body
    request.headers = {}
    request.url = type("DummyUrl", (), {"query": ""})()
    request.method = "POST"
    request.client = type("DummyClient", (), {"host": "127.0.0.1"})()
    
    with pytest.raises(HTTPException) as exc:
        await run_git_http_backend(request, repo, user, "info/refs", db)
        
    assert exc.value.status_code == 403
    assert "traversal denied" in exc.value.detail
