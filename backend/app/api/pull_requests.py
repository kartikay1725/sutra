from datetime import datetime
import json
import re

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.agent_dependencies import get_current_agent, get_current_agent_session
from app.api.dependencies import get_current_user
from app.db.session import get_db
from app.models.actor import Actor
from app.models.agent import Agent
from app.models.agent_session import AgentSession
from app.models.change import Change
from app.models.change_review import ChangeReview
from app.models.ci_job import CIJob
from app.models.pull_request import PullRequest
from app.models.repository import Repository
from app.models.task import Task
from app.models.user import User
from app.services.agent_review_service import AgentReviewService
from app.services.inline_review_service import InlineReviewService
from app.services.pull_request_service import PullRequestService
from app.services.ci_service import CIService
from app.services.governance_service import GovernanceService, GovernanceVerdict


router = APIRouter(
    tags=["pull-requests"],
)

UUID_PATTERN = r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
BRANCH_PATTERN = r"^[A-Za-z0-9_][A-Za-z0-9._/\-]*$"


class PullRequestCreateRequest(BaseModel):
    repository_id: str = Field(pattern=UUID_PATTERN)
    source_change_id: str = Field(pattern=UUID_PATTERN)
    title: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=5000)
    target_branch: str = Field(min_length=1, max_length=255, pattern=BRANCH_PATTERN)
    is_draft: bool = False


class PullRequestActionRequest(BaseModel):
    reason: str | None = Field(default=None, max_length=5000)


class PullRequestResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    repository_id: str
    author_id: str
    source_change_id: str
    title: str
    description: str | None
    target_branch: str
    source_commit: str | None
    target_commit: str | None
    status: str
    created_at: datetime
    updated_at: datetime
    merged_at: datetime | None
    closed_at: datetime | None

    # Enriched SUTRA & Substrate Context
    repository_name: str | None = None
    head_branch: str | None = None
    base_branch: str | None = None
    github_pr_number: int | None = None
    github_html_url: str | None = None
    task_id: str | None = None
    task_title: str | None = None
    agent_id: str | None = None
    agent_name: str | None = None
    agent_session_id: str | None = None
    actor_name: str | None = None
    actor_type: str | None = None
    checks_summary: dict | None = None
    checks_verdict: str | None = None
    governance_verdict: str | None = None
    ready_for_approval: bool | None = None
    ready_for_merge: bool | None = None
    eligible_for_merge: bool | None = None
    approved: bool | None = None
    reviewer: dict | None = None
    required_approvals: int | None = None
    actual_valid_approvals: int | None = None


class GovernanceEvaluationResponse(BaseModel):
    pull_request_id: str
    repository_id: str
    verdict: str
    ready_for_approval: bool
    head_sha: str
    evaluated_at: str
    passed: list[str]
    failed: list[str]
    warnings: list[str]
    checks: dict
    provenance: dict
    policy: dict
    review: dict


from sqlalchemy import select
from app.models.change_file import ChangeFile


class PRChangeFileResponse(BaseModel):
    path: str
    operation: str
    additions: int = 0
    deletions: int = 0


class PRChangeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    repository_id: str
    actor_id: str
    intent: str
    base_commit: str | None
    resulting_commit: str | None
    status: str
    risk_level: str
    additions: int = 0
    deletions: int = 0
    files_changed: int = 0
    files: list[PRChangeFileResponse] = []
    created_at: datetime
    updated_at: datetime


class PRReviewResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    change_id: str
    requested_by: str
    reviewer_id: str | None
    status: str
    reason: str | None
    created_at: datetime
    reviewed_at: datetime | None


class PRConflictResponse(BaseModel):
    level: str
    reason: str
    paths: list[str]
    related_change_ids: list[str]


class PRMergeResponse(BaseModel):
    status: str
    pull_request_id: str
    detail: str
    merge_commit_sha: str | None = None
    merged_at: datetime | None = None


class PREventResponse(BaseModel):
    id: str
    pull_request_id: str
    change_id: str
    actor_id: str | None
    event_type: str
    from_status: str | None
    to_status: str | None
    reason: str | None
    metadata: dict
    created_at: datetime


class InlineCommentCreateRequest(BaseModel):
    body: str = Field(min_length=1, max_length=10000)
    path: str | None = Field(default=None, max_length=1000)
    diff_side: str | None = Field(default=None, pattern=r"^(LEFT|RIGHT)$")
    line_number: int | None = Field(default=None, gt=0)
    line_range_start: int | None = Field(default=None, gt=0)
    line_range_end: int | None = Field(default=None, gt=0)
    commit_sha: str | None = Field(default=None, max_length=64)
    parent_id: str | None = Field(default=None, pattern=UUID_PATTERN)


class InlineCommentReplyRequest(BaseModel):
    body: str = Field(min_length=1, max_length=10000)


class InlineCommentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    pull_request_id: str
    repository_id: str
    author_id: str
    parent_id: str | None
    path: str | None
    diff_side: str | None
    line_number: int | None
    line_range_start: int | None
    line_range_end: int | None
    commit_sha: str | None
    body: str
    status: str
    created_at: datetime
    updated_at: datetime
    resolved_at: datetime | None
    resolved_by: str | None


class AgentCommentCreateRequest(BaseModel):
    body: str = Field(min_length=1, max_length=10000)
    path: str | None = Field(default=None, max_length=1000)
    diff_side: str | None = Field(default=None, pattern=r"^(LEFT|RIGHT)$")
    line_number: int | None = Field(default=None, gt=0)
    commit_sha: str | None = Field(default=None, max_length=64)
    parent_id: str | None = Field(default=None, pattern=UUID_PATTERN)


class AgentFindingCreateRequest(BaseModel):
    severity: str = Field(pattern=r"^(low|medium|high|critical)$")
    category: str = Field(pattern=r"^(bug|security|correctness|performance|style|maintainability|test|dependency)$")
    message: str = Field(min_length=1, max_length=10000)
    path: str | None = Field(default=None, max_length=1000)
    line_number: int | None = Field(default=None, gt=0)
    diff_side: str | None = Field(default=None, pattern=r"^(LEFT|RIGHT)$")
    suggested_fix: str | None = Field(default=None, max_length=10000)


class AgentReviewSummaryResponse(BaseModel):
    pull_request_id: str
    repository_id: str
    total_findings: int
    severity_distribution: dict
    participating_agents_count: int
    participating_agent_ids: list[str]
    findings: list[dict]


def _to_response(pr, db: Session | None = None) -> PullRequestResponse:
    repo_name = None
    head_branch = None
    github_pr_number = None
    github_html_url = None
    task_id = None
    task_title = None
    agent_id = None
    agent_name = None
    agent_session_id = None
    actor_name = None
    actor_type = None

    if db is not None:
        try:
            repo = db.scalar(select(Repository).where(Repository.id == pr.repository_id))
            if repo:
                repo_name = repo.name

            actor = db.scalar(select(Actor).where(Actor.id == pr.author_id))
            if actor:
                actor_name = actor.name
                actor_type = actor.type

            change = db.scalar(select(Change).where(Change.id == pr.source_change_id))
            if change:
                try:
                    meta = json.loads(change.metadata_json or "{}")
                except Exception:
                    meta = {}
                head_branch = meta.get("branch") or meta.get("head_branch")
                github_pr_number = meta.get("github_pr_number")
                github_html_url = meta.get("github_pr_url")
                task_id = meta.get("task_id")
                task_title = meta.get("task_title")
                agent_id = meta.get("agent_id")
                agent_name = meta.get("agent_name")
                agent_session_id = meta.get("agent_session_id")

                if not task_id:
                    task = db.scalar(select(Task).where(Task.resulting_change_id == change.id))
                    if task:
                        task_id = task.id
                        task_title = task.title
                        if not agent_id:
                            agent_id = task.assigned_agent_id
                        if not agent_session_id:
                            agent_session_id = task.claimed_by_session_id

                if agent_id and not agent_name:
                    ag = db.scalar(select(Agent).where(Agent.id == agent_id))
                    if ag:
                        agent_name = ag.name
        except Exception:
            pass

    checks_summary = None
    checks_verdict = None
    if db is not None and pr.source_commit:
        try:
            head_jobs = db.scalars(
                select(CIJob).where(
                    CIJob.pull_request_id == pr.id,
                    CIJob.commit_sha == pr.source_commit,
                )
            ).all()
            if head_jobs:
                total_c = len(head_jobs)
                passed_c = sum(1 for j in head_jobs if j.status == CIJob.STATUS_PASSED)
                failed_c = sum(1 for j in head_jobs if j.status == CIJob.STATUS_FAILED)
                running_c = sum(1 for j in head_jobs if j.status == CIJob.STATUS_RUNNING)
                pending_c = sum(1 for j in head_jobs if j.status in (CIJob.STATUS_QUEUED, "pending"))
                checks_summary = {
                    "total": total_c,
                    "passed": passed_c,
                    "failed": failed_c,
                    "running": running_c,
                    "pending": pending_c,
                }
                if failed_c > 0:
                    checks_verdict = "BLOCKED BY CI"
                elif running_c > 0 or pending_c > 0:
                    checks_verdict = "CHECKS IN PROGRESS"
                else:
                    checks_verdict = "READY FOR GOVERNANCE"
        except Exception:
            pass

    governance_verdict = None
    ready_for_approval = None
    ready_for_merge = None
    eligible_for_merge = None
    approved = (pr.status == "approved")
    reviewer = None
    required_approvals = None
    actual_valid_approvals = None

    if db is not None:
        try:
            gov_svc = GovernanceService(db)
            gov_eval = gov_svc.evaluate_pull_request(pr.id, record_audit=False)
            governance_verdict = gov_eval["verdict"]
            ready_for_approval = gov_eval["ready_for_approval"]
            ready_for_merge = gov_eval.get("ready_for_merge", False)
            eligible_for_merge = gov_eval.get("eligible_for_merge", False)
            if "review" in gov_eval:
                required_approvals = gov_eval["review"].get("required_approvals", 1)
                actual_valid_approvals = gov_eval["review"].get("actual_approvals", 0)

            # Find latest valid human reviewer
            reviews = db.scalars(
                select(ChangeReview)
                .where(
                    ChangeReview.change_id == pr.source_change_id,
                    ChangeReview.status == "approved",
                )
                .order_by(ChangeReview.reviewed_at.desc())
            ).all()
            for r in reviews:
                if r.reviewer_id and r.reviewer_id != pr.author_id:
                    rev_user = db.scalar(select(User).where(User.id == r.reviewer_id))
                    reviewer = {
                        "id": r.reviewer_id,
                        "username": rev_user.username if rev_user else r.reviewer_id,
                        "name": rev_user.username if rev_user else "Human Reviewer",
                        "reviewed_at": r.reviewed_at.isoformat() if r.reviewed_at else None,
                    }
                    break
        except Exception:
            pass

    return PullRequestResponse(
        id=pr.id,
        repository_id=pr.repository_id,
        author_id=pr.author_id,
        source_change_id=pr.source_change_id,
        title=pr.title,
        description=pr.description,
        target_branch=pr.target_branch,
        source_commit=pr.source_commit,
        target_commit=pr.target_commit,
        status=pr.status,
        created_at=pr.created_at,
        updated_at=pr.updated_at,
        merged_at=pr.merged_at,
        closed_at=pr.closed_at,
        repository_name=repo_name,
        head_branch=head_branch,
        base_branch=pr.target_branch,
        github_pr_number=github_pr_number,
        github_html_url=github_html_url,
        task_id=task_id,
        task_title=task_title,
        agent_id=agent_id,
        agent_name=agent_name,
        agent_session_id=agent_session_id,
        actor_name=actor_name,
        actor_type=actor_type,
        checks_summary=checks_summary,
        checks_verdict=checks_verdict,
        governance_verdict=governance_verdict,
        ready_for_approval=ready_for_approval,
        ready_for_merge=ready_for_merge,
        eligible_for_merge=eligible_for_merge,
        approved=approved,
        reviewer=reviewer,
        required_approvals=required_approvals,
        actual_valid_approvals=actual_valid_approvals,
    )


@router.get(
    "/v1/pull-requests/{id}/checks",
    status_code=status.HTTP_200_OK,
)
def get_pr_checks_alias(
    id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not re.match(UUID_PATTERN, id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="PullRequest not found",
        )

    svc = CIService(db)
    try:
        return svc.get_pr_checks(id, current_user.id)
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


@router.get(
    "/v1/pull-requests/{id}/governance",
    response_model=GovernanceEvaluationResponse,
    status_code=status.HTTP_200_OK,
)
def get_pr_governance(
    id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not re.match(UUID_PATTERN, id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="PullRequest not found",
        )

    svc = GovernanceService(db)
    try:
        return svc.evaluate_pull_request(id, current_user.id, record_audit=False)
    except PermissionError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e),
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
    "/v1/pull-requests/{id}/governance/evaluate",
    response_model=GovernanceEvaluationResponse,
    status_code=status.HTTP_200_OK,
)
def evaluate_pr_governance_post(
    id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not re.match(UUID_PATTERN, id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="PullRequest not found",
        )

    svc = GovernanceService(db)
    try:
        res = svc.evaluate_pull_request(id, current_user.id, record_audit=True)
        db.commit()
        return res
    except PermissionError as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e),
        )
    except ValueError as e:
        db.rollback()
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


# ---------------------------------------------------------
# ENDPOINTS
# ---------------------------------------------------------

@router.post(
    "/v1/pull-requests",
    response_model=PullRequestResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_pull_request(
    payload: PullRequestCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    svc = PullRequestService(db)
    try:
        pr = svc.create_pull_request(
            repository_id=payload.repository_id,
            author_id=current_user.id,
            source_change_id=payload.source_change_id,
            title=payload.title,
            target_branch=payload.target_branch,
            description=payload.description,
            is_draft=payload.is_draft,
        )
        db.commit()
        return _to_response(pr, db)
    except PermissionError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e),
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
    "/v1/pull-requests/agent",
    response_model=PullRequestResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create Pull Request (Agent)",
    description="Agent creates a PR from a Change. Requires AgentSession. The Change must have a `resulting_commit` recorded.",
)
def create_agent_pull_request(
    payload: PullRequestCreateRequest,
    session: AgentSession = Depends(get_current_agent_session),
    db: Session = Depends(get_db),
):
    change = db.scalar(select(Change).where(Change.id == payload.source_change_id))
    if not change:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Source Change not found")

    # If Change belongs to a task, enforce task lease ownership and delegate to AgentChangeService
    task = db.scalar(select(Task).where(Task.resulting_change_id == payload.source_change_id))
    if task is None:
        try:
            meta = json.loads(change.metadata_json or "{}")
            t_id = meta.get("task_id")
            if t_id:
                task = db.scalar(select(Task).where(Task.id == t_id))
        except Exception:
            pass

    if task is not None:
        if task.assigned_agent_id != session.agent_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Agent is not assigned to this task")
        if task.claimed_by_session_id != session.id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Agent session does not hold the task lease")

        repository = db.scalar(select(Repository).where(Repository.id == task.repository_id))
        from app.api.agent_tasks import _get_provider_for_repository
        from app.services.agent_change_service import AgentChangeService
        provider = _get_provider_for_repository(repository) if repository else None
        agent_svc = AgentChangeService(db=db, provider=provider)
        try:
            pr = agent_svc.create_pull_request(
                session=session,
                task=task,
                title=payload.title,
                target_branch=payload.target_branch,
                description=payload.description,
                is_draft=payload.is_draft,
            )
            db.commit()
            db.refresh(pr)
            return _to_response(pr, db)
        except PermissionError as e:
            from app.api.agent_errors import raise_capability_required
            raise_capability_required(
                capability="repository.write",
                repository_slug=payload.repository_id,
            )
        except ValueError as e:
            msg = str(e)
            if "not found" in msg:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=msg)
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=msg)

    # Standalone change without task: check agent actor and capability
    actor = db.scalar(
        select(Actor).where(
            Actor.id == session.agent_id,
            Actor.type == "agent",
        )
    )
    if not actor:
        from app.api.agent_errors import raise_agent_inactive
        raise_agent_inactive()

    svc = PullRequestService(db)
    try:
        pr = svc.create_pull_request(
            repository_id=payload.repository_id,
            author_id=actor.id,
            source_change_id=payload.source_change_id,
            title=payload.title,
            target_branch=payload.target_branch,
            description=payload.description,
            is_draft=payload.is_draft,
        )
        db.commit()
        return _to_response(pr, db)
    except PermissionError as e:
        from app.api.agent_errors import raise_capability_required
        raise_capability_required(
            capability="repository.write",
            repository_slug=payload.repository_id,
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
    "/v1/pull-requests",
    response_model=list[PullRequestResponse],
)
def list_all_pull_requests(
    repository_id: str | None = Query(None),
    status_filter: str | None = Query(None, alias="status"),
    target_branch: str | None = Query(None),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    svc = PullRequestService(db)
    if repository_id:
        if not re.match(UUID_PATTERN, repository_id):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Repository not found",
            )
        try:
            prs = svc.list_pull_requests(
                repository_id=repository_id,
                user_id=current_user.id,
                status=status_filter,
                target_branch=target_branch,
                limit=limit,
                offset=offset,
            )
            return [_to_response(pr, db) for pr in prs]
        except PermissionError as e:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=str(e),
            )
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=str(e),
            )

    prs = svc.list_all_pull_requests(
        user_id=current_user.id,
        status=status_filter,
        target_branch=target_branch,
        limit=limit,
        offset=offset,
    )
    return [_to_response(pr, db) for pr in prs]


@router.get(
    "/v1/pull-requests/{pull_request_id}",
    response_model=PullRequestResponse,
)
def get_pull_request(
    pull_request_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not re.match(UUID_PATTERN, pull_request_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="PullRequest not found",
        )

    svc = PullRequestService(db)
    pr = svc.get_pull_request(pull_request_id, current_user.id)
    if pr is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="PullRequest not found",
        )
    return _to_response(pr, db)


@router.get(
    "/v1/pull-requests/{pull_request_id}/changes",
    response_model=PRChangeResponse,
)
def get_pull_request_change(
    pull_request_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not re.match(UUID_PATTERN, pull_request_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="PullRequest not found",
        )

    svc = PullRequestService(db)
    result = svc.get_pull_request_change(pull_request_id, current_user.id)
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="PullRequest not found",
        )

    pr, change = result
    change_files = list(
        db.scalars(
            select(ChangeFile).where(ChangeFile.change_id == change.id)
        ).all()
    )
    additions = sum(f.additions for f in change_files)
    deletions = sum(f.deletions for f in change_files)
    files_list = [
        PRChangeFileResponse(
            path=f.path,
            operation=f.operation,
            additions=f.additions,
            deletions=f.deletions,
        )
        for f in change_files
    ]
    return PRChangeResponse(
        id=change.id,
        repository_id=change.repository_id,
        actor_id=change.actor_id,
        intent=change.intent,
        base_commit=change.base_commit,
        resulting_commit=change.resulting_commit,
        status=change.status,
        risk_level=change.risk_level,
        additions=additions,
        deletions=deletions,
        files_changed=len(change_files),
        files=files_list,
        created_at=change.created_at,
        updated_at=change.updated_at,
    )


@router.get(
    "/v1/pull-requests/{pull_request_id}/reviews",
    response_model=list[PRReviewResponse],
)
def get_pull_request_reviews(
    pull_request_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not re.match(UUID_PATTERN, pull_request_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="PullRequest not found",
        )

    svc = PullRequestService(db)
    result = svc.get_pull_request_reviews(pull_request_id, current_user.id)
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="PullRequest not found",
        )

    pr, reviews = result
    return [
        PRReviewResponse(
            id=r.id,
            change_id=r.change_id,
            requested_by=r.requested_by,
            reviewer_id=r.reviewer_id,
            status=r.status,
            reason=r.reason,
            created_at=r.created_at,
            reviewed_at=r.reviewed_at,
        )
        for r in reviews
    ]


@router.post(
    "/v1/pull-requests/{pull_request_id}/reviews",
    response_model=PRReviewResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_pull_request_review(
    pull_request_id: str,
    payload: PullRequestActionRequest | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not re.match(UUID_PATTERN, pull_request_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="PullRequest not found",
        )

    svc = PullRequestService(db)
    pr = svc.get_pull_request(pull_request_id, current_user.id)
    if pr is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="PullRequest not found",
        )

    reason = payload.reason if payload else None
    try:
        review = svc.create_pull_request_review_request(pr, current_user.id, reason=reason)
        db.commit()
        return PRReviewResponse(
            id=review.id,
            change_id=review.change_id,
            requested_by=review.requested_by,
            reviewer_id=review.reviewer_id,
            status=review.status,
            reason=review.reason,
            created_at=review.created_at,
            reviewed_at=review.reviewed_at,
        )
    except PermissionError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e),
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e),
        )


@router.get(
    "/v1/pull-requests/{pull_request_id}/conflicts",
    response_model=PRConflictResponse,
)
def get_pull_request_conflicts(
    pull_request_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not re.match(UUID_PATTERN, pull_request_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="PullRequest not found",
        )

    svc = PullRequestService(db)
    result = svc.get_pull_request_conflicts(pull_request_id, current_user.id)
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="PullRequest not found",
        )

    pr, conflict_result = result
    return PRConflictResponse(
        level=conflict_result.level,
        reason=conflict_result.reason,
        paths=conflict_result.paths,
        related_change_ids=conflict_result.related_change_ids,
    )


@router.get(
    "/v1/repositories/{repository_id}/pull-requests",
    response_model=list[PullRequestResponse],
)
def list_pull_requests(
    repository_id: str,
    status_filter: str | None = Query(None, alias="status"),
    target_branch: str | None = Query(None),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not re.match(UUID_PATTERN, repository_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Repository not found",
        )

    svc = PullRequestService(db)
    try:
        prs = svc.list_pull_requests(
            repository_id=repository_id,
            user_id=current_user.id,
            status=status_filter,
            target_branch=target_branch,
            limit=limit,
            offset=offset,
        )
        return [_to_response(pr, db) for pr in prs]
    except PermissionError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e),
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )


@router.post(
    "/v1/pull-requests/{pull_request_id}/approve",
    response_model=PullRequestResponse,
)
def approve_pull_request(
    pull_request_id: str,
    payload: PullRequestActionRequest | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not re.match(UUID_PATTERN, pull_request_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="PullRequest not found",
        )

    svc = PullRequestService(db)
    pr = db.scalar(select(PullRequest).where(PullRequest.id == pull_request_id))
    if pr is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="PullRequest not found",
        )
    repo = db.scalar(
        select(Repository).where(
            Repository.id == pr.repository_id,
            Repository.deleted_at.is_(None),
        )
    )
    if repo is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="PullRequest not found",
        )

    # Private repository IDOR protection: user must own repo, author PR, or have an existing ChangeReview on it
    if getattr(repo, "visibility", "private") != "public" and repo.owner_id != current_user.id and pr.author_id != current_user.id:
        existing_review = db.scalar(
            select(ChangeReview).where(
                ChangeReview.change_id == pr.source_change_id,
                (
                    (ChangeReview.reviewer_id == current_user.id)
                    | (ChangeReview.reviewer_id.is_(None) & (ChangeReview.status == "pending"))
                    | (ChangeReview.requested_by == current_user.id)
                ),
            )
        )
        if existing_review is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="PullRequest not found",
            )

    reason = payload.reason if payload else None

    # If no review exists for source change, auto-create review request so human approval can proceed seamlessly
    existing_review = db.scalar(
        select(ChangeReview).where(ChangeReview.change_id == pr.source_change_id)
    )
    if existing_review is None:
        from uuid import uuid4
        requester = pr.author_id
        is_user = db.scalar(select(User).where(User.id == pr.author_id)) is not None
        if not is_user:
            repo = db.scalar(select(Repository).where(Repository.id == pr.repository_id))
            requester = repo.owner_id if repo else current_user.id

        new_review = ChangeReview(
            id=str(uuid4()),
            change_id=pr.source_change_id,
            requested_by=requester,
            reviewer_id=current_user.id,
            status="pending",
            reason=reason or "Requested review for PR approval",
        )
        db.add(new_review)
        db.flush()

    try:
        approved_pr = svc.approve_pull_request(pr, current_user.id, reason=reason)
        db.commit()
        return _to_response(approved_pr, db)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e),
        )
    except PermissionError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e),
        )


@router.post(
    "/v1/pull-requests/{pull_request_id}/merge",
    response_model=PRMergeResponse,
)
def merge_pull_request(
    pull_request_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not re.match(UUID_PATTERN, pull_request_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="PullRequest not found",
        )

    pr = db.scalar(select(PullRequest).where(PullRequest.id == pull_request_id))
    if pr is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="PullRequest not found",
        )

    repo = db.scalar(select(Repository).where(Repository.id == pr.repository_id, Repository.deleted_at.is_(None)))
    provider = None
    if repo:
        from app.api.agent_tasks import _get_provider_for_repository
        provider = _get_provider_for_repository(repo)

    svc = PullRequestService(db, provider=provider)
    try:
        result = svc.merge_pull_request(pr, current_user.id)
        if result is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="PullRequest not found",
            )
        db.commit()
        return PRMergeResponse(
            status=result.status,
            pull_request_id=result.pull_request.id,
            detail=result.detail,
            merge_commit_sha=result.merge_commit_sha,
            merged_at=result.merged_at,
        )
    except PermissionError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e),
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e),
        )


@router.post(
    "/v1/pull-requests/{pull_request_id}/close",
    response_model=PullRequestResponse,
)
def close_pull_request(
    pull_request_id: str,
    payload: PullRequestActionRequest | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not re.match(UUID_PATTERN, pull_request_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="PullRequest not found",
        )

    svc = PullRequestService(db)
    pr = svc.get_pull_request(pull_request_id, current_user.id)
    if pr is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="PullRequest not found",
        )

    reason = payload.reason if payload else None
    try:
        closed_pr = svc.close_pull_request(pr, current_user.id, reason=reason)
        db.commit()
        return _to_response(closed_pr, db)
    except PermissionError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e),
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e),
        )


@router.post(
    "/v1/pull-requests/{pull_request_id}/reject",
    response_model=PullRequestResponse,
)
def reject_pull_request(
    pull_request_id: str,
    payload: PullRequestActionRequest | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not re.match(UUID_PATTERN, pull_request_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="PullRequest not found",
        )

    svc = PullRequestService(db)
    pr = svc.get_pull_request(pull_request_id, current_user.id)
    if pr is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="PullRequest not found",
        )

    reason = payload.reason if payload else None
    try:
        rejected_pr = svc.reject_pull_request(pr, current_user.id, reason=reason)
        db.commit()
        return _to_response(rejected_pr)
    except PermissionError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e),
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e),
        )


@router.get(
    "/v1/pull-requests/{pull_request_id}/events",
    response_model=list[PREventResponse],
)
def get_pull_request_events(
    pull_request_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not re.match(UUID_PATTERN, pull_request_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="PullRequest not found",
        )

    svc = PullRequestService(db)
    result = svc.get_pull_request_events(pull_request_id, current_user.id)
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="PullRequest not found",
        )

    pr, events = result
    response = []
    for ev in events:
        try:
            meta = json.loads(ev.metadata_json or "{}")
        except json.JSONDecodeError:
            meta = {}

        response.append(
            PREventResponse(
                id=ev.id,
                pull_request_id=pr.id,
                change_id=ev.change_id,
                actor_id=ev.actor_id,
                event_type=ev.event_type,
                from_status=ev.from_status,
                to_status=ev.to_status,
                reason=ev.reason,
                metadata=meta,
                created_at=ev.created_at,
            )
        )
    return response


@router.get(
    "/v1/pull-requests/{pull_request_id}/diff",
)
def get_pull_request_diff(
    pull_request_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not re.match(UUID_PATTERN, pull_request_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="PullRequest not found",
        )

    svc = PullRequestService(db)
    result = svc.get_pull_request_diff(pull_request_id, current_user.id)
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="PullRequest not found",
        )

    pr, diff_data = result
    return diff_data


@router.get(
    "/v1/pull-requests/{pull_request_id}/files",
)
def get_pull_request_files(
    pull_request_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not re.match(UUID_PATTERN, pull_request_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="PullRequest not found",
        )

    svc = PullRequestService(db)
    result = svc.get_pull_request_files(pull_request_id, current_user.id)
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="PullRequest not found",
        )

    pr, files_data = result
    return files_data


@router.get(
    "/v1/pull-requests/{pull_request_id}/comments",
    response_model=list[InlineCommentResponse],
)
def get_pull_request_comments(
    pull_request_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not re.match(UUID_PATTERN, pull_request_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="PullRequest not found",
        )

    svc = InlineReviewService(db)
    try:
        result = svc.get_comments_for_pull_request(pull_request_id, current_user.id)
    except PermissionError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="PullRequest not found",
        )

    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="PullRequest not found",
        )

    pr, comments = result
    return comments


@router.post(
    "/v1/pull-requests/{pull_request_id}/comments",
    response_model=InlineCommentResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_pull_request_comment(
    pull_request_id: str,
    payload: InlineCommentCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not re.match(UUID_PATTERN, pull_request_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="PullRequest not found",
        )

    svc = InlineReviewService(db)
    try:
        comment = svc.create_comment(
            pull_request_id=pull_request_id,
            author_id=current_user.id,
            body=payload.body,
            path=payload.path,
            diff_side=payload.diff_side,
            line_number=payload.line_number,
            line_range_start=payload.line_range_start,
            line_range_end=payload.line_range_end,
            commit_sha=payload.commit_sha,
            parent_id=payload.parent_id,
        )
        db.commit()
        return comment
    except PermissionError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e),
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
    "/v1/pull-requests/{pull_request_id}/comments/{comment_id}/reply",
    response_model=InlineCommentResponse,
    status_code=status.HTTP_201_CREATED,
)
def reply_pull_request_comment(
    pull_request_id: str,
    comment_id: str,
    payload: InlineCommentReplyRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not re.match(UUID_PATTERN, pull_request_id) or not re.match(UUID_PATTERN, comment_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="PullRequest or Comment not found",
        )

    svc = InlineReviewService(db)
    try:
        reply = svc.create_comment(
            pull_request_id=pull_request_id,
            author_id=current_user.id,
            body=payload.body,
            parent_id=comment_id,
        )
        db.commit()
        return reply
    except PermissionError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e),
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
    "/v1/pull-requests/{pull_request_id}/comments/{comment_id}/resolve",
    response_model=InlineCommentResponse,
)
def resolve_pull_request_thread(
    pull_request_id: str,
    comment_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not re.match(UUID_PATTERN, pull_request_id) or not re.match(UUID_PATTERN, comment_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="PullRequest or Comment not found",
        )

    svc = InlineReviewService(db)
    try:
        resolved = svc.resolve_thread(comment_id, current_user.id)
        db.commit()
        return resolved
    except PermissionError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e),
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
    "/v1/pull-requests/{pull_request_id}/comments/{comment_id}/reopen",
    response_model=InlineCommentResponse,
)
def reopen_pull_request_thread(
    pull_request_id: str,
    comment_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not re.match(UUID_PATTERN, pull_request_id) or not re.match(UUID_PATTERN, comment_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="PullRequest or Comment not found",
        )

    svc = InlineReviewService(db)
    try:
        reopened = svc.reopen_thread(comment_id, current_user.id)
        db.commit()
        return reopened
    except PermissionError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e),
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
    "/v1/pull-requests/{pull_request_id}/agent-reviews/comments",
    response_model=InlineCommentResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_agent_review_comment(
    pull_request_id: str,
    payload: AgentCommentCreateRequest,
    current_agent: Agent = Depends(get_current_agent),
    db: Session = Depends(get_db),
):
    if not re.match(UUID_PATTERN, pull_request_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="PullRequest not found",
        )

    svc = AgentReviewService(db)
    try:
        comment = svc.create_agent_comment(
            agent_id=current_agent.id,
            pull_request_id=pull_request_id,
            body=payload.body,
            path=payload.path,
            diff_side=payload.diff_side,
            line_number=payload.line_number,
            commit_sha=payload.commit_sha,
            parent_id=payload.parent_id,
        )
        db.commit()
        return comment
    except PermissionError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e),
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
    "/v1/pull-requests/{pull_request_id}/agent-reviews/findings",
    response_model=InlineCommentResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_agent_review_finding(
    pull_request_id: str,
    payload: AgentFindingCreateRequest,
    current_agent: Agent = Depends(get_current_agent),
    db: Session = Depends(get_db),
):
    if not re.match(UUID_PATTERN, pull_request_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="PullRequest not found",
        )

    svc = AgentReviewService(db)
    try:
        comment = svc.create_agent_finding(
            agent_id=current_agent.id,
            pull_request_id=pull_request_id,
            severity=payload.severity,
            category=payload.category,
            message=payload.message,
            path=payload.path,
            line_number=payload.line_number,
            diff_side=payload.diff_side,
            suggested_fix=payload.suggested_fix,
        )
        db.commit()
        return comment
    except PermissionError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e),
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
    "/v1/pull-requests/{pull_request_id}/agent-reviews",
    response_model=AgentReviewSummaryResponse,
)
def get_agent_review_summary(
    pull_request_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not re.match(UUID_PATTERN, pull_request_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="PullRequest not found",
        )

    svc = AgentReviewService(db)
    try:
        summary = svc.get_agent_review_summary(pull_request_id, current_user.id, is_agent=False)
        return summary
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
