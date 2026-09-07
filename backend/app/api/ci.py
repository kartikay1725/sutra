from datetime import datetime, timezone
import re

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
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


class NormalizedCheckItem(BaseModel):
    id: str
    name: str
    head_sha: str
    status: str
    conclusion: str | None = None
    sutra_state: str
    html_url: str | None = None
    details_url: str | None = None
    started_at: str | None = None
    completed_at: str | None = None
    source: str = "github"
    app_name: str | None = None
    required: bool = True


class PRChecksSummaryItem(BaseModel):
    total: int
    passed: int
    failed: int
    running: int
    pending: int


class PRChecksResponse(BaseModel):
    pull_request_id: str
    repository_id: str
    head_sha: str
    overall_status: str
    governance_verdict: str
    ready_for_governance: bool
    summary: PRChecksSummaryItem
    checks: list[NormalizedCheckItem]


class CreateCheckRunRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    head_sha: str | None = None
    status: str = "completed"
    conclusion: str | None = "success"
    details_url: str | None = None
    summary: str | None = None


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


@router.get(
    "/v1/pull-requests/{pull_request_id}/checks",
    response_model=PRChecksResponse,
)
def get_pull_request_checks(
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
        data = svc.get_pr_checks(pull_request_id, current_user.id)
        return data
    except PermissionError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="PullRequest not found",
        )
    except ValueError as e:
        msg = str(e)
        if "not found" in msg.lower():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=msg,
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=msg,
        )


@router.post(
    "/v1/pull-requests/{pull_request_id}/checks",
    response_model=NormalizedCheckItem,
    status_code=status.HTTP_201_CREATED,
)
def create_pull_request_check_run(
    pull_request_id: str,
    payload: CreateCheckRunRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not re.match(UUID_PATTERN, pull_request_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="PullRequest not found",
        )

    from app.models.pull_request import PullRequest
    from app.models.repository import Repository
    from app.models.change import Change
    from app.models.ci_job import CIJob
    from uuid import uuid4
    from sqlalchemy import select

    pr = db.scalar(select(PullRequest).where(PullRequest.id == pull_request_id))
    if not pr:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="PullRequest not found")

    repo = db.scalar(select(Repository).where(Repository.id == pr.repository_id, Repository.deleted_at.is_(None)))
    if not repo:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Repository not found")

    svc = CIService(db)
    try:
        svc._authorize_user(current_user.id, repo)
    except PermissionError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="PullRequest not found")

    head_sha = payload.head_sha or pr.source_commit
    if not head_sha:
        change = db.scalar(select(Change).where(Change.id == pr.source_change_id))
        head_sha = change.resulting_commit if change else None
    if not head_sha:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No commit SHA available for check run")

    gh_check = None
    if repo.provider_type == "github":
        provider = svc._get_provider(repo)
        if provider:
            try:
                owner = repo.provider_owner or "kartikay1725"
                gh_check = provider.create_check_run(
                    owner=owner,
                    name=repo.name,
                    check_name=payload.name,
                    head_sha=head_sha,
                    status=payload.status,
                    conclusion=payload.conclusion,
                    summary=payload.summary,
                    details_url=payload.details_url,
                )
            except Exception:
                pass

    conc = (payload.conclusion or "").lower()
    st = (payload.status or "").lower()
    if conc == "success":
        j_status = CIJob.STATUS_PASSED
    elif conc in ("failure", "timed_out", "action_required"):
        j_status = CIJob.STATUS_FAILED
    elif conc in ("cancelled", "skipped", "neutral"):
        j_status = CIJob.STATUS_CANCELLED if conc == "cancelled" else CIJob.STATUS_PASSED
    elif st in ("in_progress", "running"):
        j_status = CIJob.STATUS_RUNNING
    else:
        j_status = CIJob.STATUS_QUEUED

    trigger_name = f"github_check_{gh_check['id']}" if (gh_check and "id" in gh_check) else payload.name
    now_utc = datetime.now(timezone.utc)

    job = CIJob(
        id=str(uuid4()),
        pull_request_id=pr.id,
        repository_id=repo.id,
        change_id=pr.source_change_id,
        commit_sha=head_sha,
        target_branch=pr.target_branch,
        status=j_status,
        trigger=trigger_name,
        runner_type="github_actions" if repo.provider_type == "github" else "sutra",
        output_log=(gh_check.get("html_url") if gh_check else None) or payload.details_url,
        failure_reason=conc if j_status == CIJob.STATUS_FAILED else None,
        started_at=now_utc,
        completed_at=now_utc if st == "completed" else None,
    )
    db.add(job)
    db.commit()

    return NormalizedCheckItem(
        id=job.id,
        name=payload.name,
        head_sha=head_sha,
        status=payload.status,
        conclusion=payload.conclusion,
        sutra_state="passed" if j_status == CIJob.STATUS_PASSED else ("failed" if j_status == CIJob.STATUS_FAILED else j_status),
        html_url=(gh_check.get("html_url") if gh_check else None) or payload.details_url,
        details_url=payload.details_url,
        started_at=job.started_at.isoformat() if job.started_at else None,
        completed_at=job.completed_at.isoformat() if job.completed_at else None,
        source="github" if repo.provider_type == "github" else "sutra",
        app_name="GitHub Actions" if repo.provider_type == "github" else "SUTRA CI",
        required=True,
    )
