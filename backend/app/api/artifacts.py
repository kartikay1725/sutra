from datetime import datetime
import re
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.db.session import get_db
from app.models.artifact import Artifact
from app.models.ci_job import CIJob
from app.models.repository import Repository
from app.models.user import User


router = APIRouter(
    tags=["artifacts"],
)

UUID_PATTERN = r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"


class ArtifactResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    ci_job_id: str
    repository_id: str
    name: str
    storage_key: str
    size_bytes: int
    mime_type: str | None
    created_at: datetime


class ArtifactCreate(BaseModel):
    name: str
    storage_key: str
    size_bytes: int
    mime_type: str | None = None


@router.get(
    "/v1/ci-jobs/{job_id}/artifacts",
    response_model=List[ArtifactResponse],
)
def list_artifacts(
    job_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not re.match(UUID_PATTERN, job_id):
        raise HTTPException(status_code=404, detail="CI Job not found")

    job = db.scalar(select(CIJob).where(CIJob.id == job_id))
    if not job:
        raise HTTPException(status_code=404, detail="CI Job not found")

    artifacts = db.scalars(
        select(Artifact).where(Artifact.ci_job_id == job.id).order_by(Artifact.created_at.desc())
    ).all()
    return artifacts


@router.post(
    "/v1/ci-jobs/{job_id}/artifacts",
    response_model=ArtifactResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_artifact(
    job_id: str,
    data: ArtifactCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not re.match(UUID_PATTERN, job_id):
        raise HTTPException(status_code=404, detail="CI Job not found")

    job = db.scalar(select(CIJob).where(CIJob.id == job_id))
    if not job:
        raise HTTPException(status_code=404, detail="CI Job not found")

    # In a full app, we would verify the current_user is the CI runner or has push access to repo
    artifact = Artifact(
        ci_job_id=job.id,
        repository_id=job.repository_id,
        name=data.name,
        storage_key=data.storage_key,
        size_bytes=data.size_bytes,
        mime_type=data.mime_type,
    )
    db.add(artifact)
    db.commit()
    db.refresh(artifact)

    return artifact
