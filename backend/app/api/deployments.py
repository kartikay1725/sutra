from datetime import datetime
import re
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.db.session import get_db
from app.models.deployment import Deployment
from app.models.environment import Environment
from app.models.user import User


router = APIRouter(
    tags=["deployments"],
)

UUID_PATTERN = r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"


class DeploymentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    environment_id: str
    repository_id: str
    commit_sha: str
    change_id: str | None
    actor_id: str
    status: str
    log_output: str | None
    created_at: datetime
    updated_at: datetime


class DeploymentCreate(BaseModel):
    commit_sha: str
    change_id: str | None = None


class DeploymentStatusUpdate(BaseModel):
    status: str
    log_output: str | None = None


@router.get(
    "/v1/environments/{environment_id}/deployments",
    response_model=List[DeploymentResponse],
)
def list_deployments(
    environment_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not re.match(UUID_PATTERN, environment_id):
        raise HTTPException(status_code=404, detail="Environment not found")

    env = db.scalar(select(Environment).where(Environment.id == environment_id))
    if not env:
        raise HTTPException(status_code=404, detail="Environment not found")

    deployments = db.scalars(
        select(Deployment).where(Deployment.environment_id == env.id).order_by(Deployment.created_at.desc())
    ).all()
    return deployments


@router.post(
    "/v1/environments/{environment_id}/deployments",
    response_model=DeploymentResponse,
    status_code=status.HTTP_201_CREATED,
)
def trigger_deployment(
    environment_id: str,
    data: DeploymentCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not re.match(UUID_PATTERN, environment_id):
        raise HTTPException(status_code=404, detail="Environment not found")

    env = db.scalar(select(Environment).where(Environment.id == environment_id))
    if not env:
        raise HTTPException(status_code=404, detail="Environment not found")

    deployment = Deployment(
        environment_id=env.id,
        repository_id=env.repository_id,
        commit_sha=data.commit_sha,
        change_id=data.change_id,
        actor_id=current_user.id,
        status=Deployment.STATUS_QUEUED,
    )
    db.add(deployment)
    db.commit()
    db.refresh(deployment)

    return deployment


@router.post(
    "/v1/deployments/{deployment_id}/status",
    response_model=DeploymentResponse,
)
def update_deployment_status(
    deployment_id: str,
    data: DeploymentStatusUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not re.match(UUID_PATTERN, deployment_id):
        raise HTTPException(status_code=404, detail="Deployment not found")

    deployment = db.scalar(select(Deployment).where(Deployment.id == deployment_id).with_for_update())
    if not deployment:
        raise HTTPException(status_code=404, detail="Deployment not found")

    if data.status not in [Deployment.STATUS_QUEUED, Deployment.STATUS_DEPLOYING, Deployment.STATUS_SUCCESS, Deployment.STATUS_FAILED, Deployment.STATUS_ROLLED_BACK]:
        raise HTTPException(status_code=400, detail="Invalid status")

    deployment.status = data.status
    if data.log_output is not None:
        deployment.log_output = data.log_output

    db.commit()
    db.refresh(deployment)

    return deployment
