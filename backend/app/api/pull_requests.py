from datetime import datetime
import json
import re

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.api.agent_dependencies import get_current_agent
from app.api.dependencies import get_current_user
from app.db.session import get_db
from app.models.agent import Agent
from app.models.user import User
from app.services.agent_review_service import AgentReviewService
from app.services.inline_review_service import InlineReviewService
from app.services.pull_request_service import PullRequestService


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


def _to_response(pr) -> PullRequestResponse:
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
        return _to_response(pr)
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
    current_agent: Agent = Depends(get_current_agent),
    db: Session = Depends(get_db),
):
    svc = PullRequestService(db)
    
    # We must look up the actor for the agent
    from sqlalchemy import select
    from app.models.actor import Actor
    actor = db.scalar(
        select(Actor).where(
            Actor.id == current_agent.id,
            Actor.type == "agent",
            Actor.owner_id == current_agent.owner_id,
        )
    )
    if not actor:
        from app.api.agent_errors import raise_agent_inactive
        raise_agent_inactive()
        
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
        return _to_response(pr)
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
            return [_to_response(pr) for pr in prs]
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
    return [_to_response(pr) for pr in prs]


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
    return _to_response(pr)


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
        return [_to_response(pr) for pr in prs]
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
    pr = svc.get_pull_request(pull_request_id, current_user.id)
    if pr is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="PullRequest not found",
        )

    reason = payload.reason if payload else None
    try:
        approved_pr = svc.approve_pull_request(pr, current_user.id, reason=reason)
        db.commit()
        return _to_response(approved_pr)
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

    svc = PullRequestService(db)
    try:
        result = svc.merge_pull_request(pull_request_id, current_user.id)
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
        return _to_response(closed_pr)
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
