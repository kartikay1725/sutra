from datetime import datetime, timezone, timedelta
from typing import List

from fastapi import APIRouter, Depends, Query, HTTPException
from pydantic import BaseModel

from app.api.dependencies import get_current_user
from app.models.user import User

router = APIRouter(prefix="/v1/repositories", tags=["releases"])

class ReleaseResponse(BaseModel):
    id: str
    tag_name: str
    name: str
    body: str
    is_prerelease: bool
    author_id: str
    created_at: datetime
    published_at: datetime

def _mock_releases(repo_name: str) -> List[ReleaseResponse]:
    now = datetime.now(timezone.utc)
    return [
        ReleaseResponse(
            id="rel-1",
            tag_name="v1.2.0",
            name="Performance Update",
            body="* Improved memory usage in the agent orchestrator.\n* Added new Knowledge Graph visualization features.\n* Fixed several race conditions during concurrent PR reviews.",
            is_prerelease=False,
            author_id="human-dev-1",
            created_at=now - timedelta(days=10),
            published_at=now - timedelta(days=10)
        ),
        ReleaseResponse(
            id="rel-2",
            tag_name="v1.3.0-rc.1",
            name="Release Candidate: SUTRA Intelligence",
            body="First release candidate for the new Intelligence dashboard.",
            is_prerelease=True,
            author_id="sutra-bot",
            created_at=now - timedelta(days=1),
            published_at=now - timedelta(days=1)
        )
    ]

@router.get("/{owner}/{repo}/releases", response_model=List[ReleaseResponse])
def get_releases(
    owner: str,
    repo: str,
    current_user: User = Depends(get_current_user),
):
    """
    Fetch releases and tags for this repository.
    """
    return _mock_releases(repo)
