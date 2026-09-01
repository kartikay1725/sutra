from datetime import datetime
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.db.session import get_db
from app.models.environment import Environment
from app.models.repository import Repository
from app.models.user import User


router = APIRouter(
    tags=["environments"],
)

class EnvironmentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    repository_id: str
    name: str
    description: str | None
    type: str
    created_at: datetime
    updated_at: datetime


class EnvironmentCreate(BaseModel):
    name: str
    description: str | None = None
    type: str = "development"


@router.get(
    "/v1/repositories/{owner}/{repo_name}/environments",
    response_model=List[EnvironmentResponse],
)
def list_environments(
    owner: str,
    repo_name: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from app.models.actor import Actor
    actor = db.scalar(select(Actor).where(Actor.name == owner))
    if not actor:
        raise HTTPException(status_code=404, detail="Repository not found")

    repo = db.scalar(
        select(Repository).where(
            Repository.owner_id == actor.id,
            Repository.name == repo_name,
            Repository.deleted_at.is_(None)
        )
    )
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")

    environments = db.scalars(
        select(Environment).where(Environment.repository_id == repo.id).order_by(Environment.created_at.desc())
    ).all()
    return environments


@router.post(
    "/v1/repositories/{owner}/{repo_name}/environments",
    response_model=EnvironmentResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_environment(
    owner: str,
    repo_name: str,
    data: EnvironmentCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from app.models.actor import Actor
    actor = db.scalar(select(Actor).where(Actor.name == owner))
    if not actor:
        raise HTTPException(status_code=404, detail="Repository not found")

    repo = db.scalar(
        select(Repository).where(
            Repository.owner_id == actor.id,
            Repository.name == repo_name,
            Repository.deleted_at.is_(None)
        )
    )
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")

    # Ensure no duplicates
    existing = db.scalar(select(Environment).where(Environment.repository_id == repo.id, Environment.name == data.name))
    if existing:
        raise HTTPException(status_code=400, detail="Environment already exists")

    env = Environment(
        repository_id=repo.id,
        name=data.name,
        description=data.description,
        type=data.type,
    )
    db.add(env)
    db.commit()
    db.refresh(env)

    return env
