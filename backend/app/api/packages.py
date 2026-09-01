from datetime import datetime, timezone, timedelta
from typing import List

from fastapi import APIRouter, Depends, Query, HTTPException
from pydantic import BaseModel

from app.api.dependencies import get_current_user
from app.models.user import User

router = APIRouter(prefix="/v1/repositories", tags=["packages"])

class PackageResponse(BaseModel):
    id: str
    name: str
    type: str # e.g., "npm", "docker", "pypi"
    latest_version: str
    downloads_last_30d: int
    published_at: datetime
    description: str

def _mock_packages(repo_name: str) -> List[PackageResponse]:
    now = datetime.now(timezone.utc)
    
    if "core" in repo_name.lower():
        return [
            PackageResponse(
                id="pkg-1",
                name="@sutra/core",
                type="npm",
                latest_version="1.2.4",
                downloads_last_30d=4520,
                published_at=now - timedelta(days=2),
                description="Core primitives and utilities for SUTRA architecture."
            ),
            PackageResponse(
                id="pkg-2",
                name="sutra/api-server",
                type="docker",
                latest_version="0.9.1-alpine",
                downloads_last_30d=1200,
                published_at=now - timedelta(days=1),
                description="Containerized SUTRA FastAPI backend."
            )
        ]
    return [
        PackageResponse(
            id="pkg-3",
            name=f"{repo_name}-utils",
            type="pypi",
            latest_version="0.1.0",
            downloads_last_30d=45,
            published_at=now - timedelta(days=14),
            description=f"Python utilities extracted from {repo_name}."
        )
    ]

@router.get("/{owner}/{repo}/packages", response_model=List[PackageResponse])
def get_packages(
    owner: str,
    repo: str,
    current_user: User = Depends(get_current_user),
):
    """
    Fetch packages and container images published by this repository.
    """
    return _mock_packages(repo)
