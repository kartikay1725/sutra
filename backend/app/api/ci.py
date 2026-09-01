from datetime import datetime
import re

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.services.ci_service import CIService


router = APIRouter(
    tags=["ci"],
)

UUID_PATTERN = r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"


class CIJobResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    pull_request_id: str
    repository_id: str
    change_id: str
    commit_sha: str
    target_branch: str
    status: str
    trigger: str
    runner_type: str
    exit_code: int | None
    failure_reason: str | None
    worker_id: str | None
    started_at: datetime | None
    completed_at: datetime | None
    cancelled_at: datetime | None
    created_at: datetime
    updated_at: datetime


class CILogResponse(BaseModel):
    job_id: str
    status: str
    output_log: str | None


@router.post(
    "/v1/pull-requests/{pull_request_id}/ci",
    response_model=CIJobResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_ci_job(
    pull_request_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not re.match(UUID_PATTERN, pull_request_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="PullRequest not found",
        )

    svc = CIService(db)
    try:
        job = svc.create_job(
            pull_request_id=pull_request_id,
            actor_id=current_user.id,
        )
        # Execute run synchronously for API trigger
        executed_job = svc.run_execution(job.id, worker_id=f"api_worker_{current_user.id[:8]}")
        db.commit()
        return executed_job
    except PermissionError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="PullRequest not found",
        )
    except ValueError as e:
        msg = str(e)
        if "not found" in msg:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=msg,
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=msg,
        )


@router.get(
    "/v1/pull-requests/{pull_request_id}/ci",
    response_model=list[CIJobResponse],
)
def list_ci_jobs(
    pull_request_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not re.match(UUID_PATTERN, pull_request_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="PullRequest not found",
        )

    svc = CIService(db)
    try:
        jobs = svc.list_jobs_for_pr(pull_request_id, current_user.id)
        return jobs
    except PermissionError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="PullRequest not found",
        )
    except ValueError as e:
        msg = str(e)
        if "not found" in msg:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=msg,
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=msg,
        )


@router.get(
    "/v1/pull-requests/{pull_request_id}/ci/{job_id}",
    response_model=CIJobResponse,
)
def get_ci_job(
    pull_request_id: str,
    job_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not re.match(UUID_PATTERN, pull_request_id) or not re.match(UUID_PATTERN, job_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="PullRequest or CI Job not found",
        )

    svc = CIService(db)
    try:
        job = svc.get_job(job_id, current_user.id)
        if job.pull_request_id != pull_request_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="CI Job not found for target PullRequest",
            )
        return job
    except PermissionError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="PullRequest or CI Job not found",
        )
    except ValueError as e:
        msg = str(e)
        if "not found" in msg:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=msg,
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=msg,
        )


@router.post(
    "/v1/pull-requests/{pull_request_id}/ci/{job_id}/cancel",
    response_model=CIJobResponse,
)
def cancel_ci_job(
    pull_request_id: str,
    job_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not re.match(UUID_PATTERN, pull_request_id) or not re.match(UUID_PATTERN, job_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="PullRequest or CI Job not found",
        )

    svc = CIService(db)
    try:
        job = svc.cancel_job(job_id, current_user.id)
        db.commit()
        return job
    except PermissionError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="PullRequest or CI Job not found",
        )
    except ValueError as e:
        msg = str(e)
        if "not found" in msg:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=msg,
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=msg,
        )


@router.get(
    "/v1/pull-requests/{pull_request_id}/ci/{job_id}/logs",
    response_model=CILogResponse,
)
def get_ci_job_logs(
    pull_request_id: str,
    job_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not re.match(UUID_PATTERN, pull_request_id) or not re.match(UUID_PATTERN, job_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="PullRequest or CI Job not found",
        )

    svc = CIService(db)
    try:
        job = svc.get_job(job_id, current_user.id)
        if job.pull_request_id != pull_request_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="CI Job not found for target PullRequest",
            )
        return CILogResponse(
            job_id=job.id,
            status=job.status,
            output_log=job.output_log,
        )
    except PermissionError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="PullRequest or CI Job not found",
        )
    except ValueError as e:
        msg = str(e)
        if "not found" in msg:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=msg,
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=msg,
        )
