from datetime import datetime, timezone
import re
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.db.session import get_db
from app.models.actor import Actor
from app.models.issue import Issue, IssueComment
from app.models.repository import Repository
from app.models.user import User
from app.services.notification_service import NotificationService


router = APIRouter(
    prefix="/v1/repositories/{owner_name}/{repo_name}/issues",
    tags=["issues"],
)


UUID_PATTERN = (
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-"
    r"[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
    r"[0-9a-fA-F]{12}$"
)


class IssueCreateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    body: str = Field(min_length=1, max_length=10000)
    author_id: str | None = Field(
        default=None,
        pattern=UUID_PATTERN,
    )


class IssueCommentCreateRequest(BaseModel):
    body: str = Field(
        min_length=1,
        max_length=10000,
    )
    author_id: str | None = Field(
        default=None,
        pattern=UUID_PATTERN,
    )


class IssueResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    repository_id: str
    author_id: str
    title: str
    body: str
    status: str
    created_at: datetime
    updated_at: datetime
    closed_at: datetime | None


class IssueCommentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    issue_id: str
    author_id: str
    body: str
    created_at: datetime
    updated_at: datetime


def get_repository_for_user(
    owner_name: str,
    repo_name: str,
    db: Session,
    user: User,
) -> Repository:

    repo = db.scalar(
        select(Repository)
        .join(Actor, Actor.id == Repository.owner_id)
        .where(
            Actor.name == owner_name,
            Repository.name == repo_name,
        )
    )

    if not repo:
        raise HTTPException(
            status_code=404,
            detail="Repository not found",
        )

    if repo.owner_id != user.id:
        raise HTTPException(
            status_code=403,
            detail="Forbidden",
        )

    return repo


def _verify_actor(
    actor_id: str,
    current_user: User,
    db: Session,
) -> Actor:
    actor = db.get(
        Actor,
        actor_id,
    )

    if not actor:
        raise HTTPException(
            status_code=400,
            detail="Invalid author_id",
        )

    # Preserve the existing behavior for now:
    # users may act as themselves or their agents.
    return actor


def _create_issue_comment(
    *,
    issue: Issue,
    author_id: str,
    body: str,
    db: Session,
) -> IssueComment:
    comment = IssueComment(
        id=str(uuid4()),
        issue_id=issue.id,
        author_id=author_id,
        body=body,
    )

    db.add(comment)
    db.flush()

    return comment


@router.post(
    "",
    response_model=IssueResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_issue(
    owner_name: str,
    repo_name: str,
    payload: IssueCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    repo = get_repository_for_user(
        owner_name,
        repo_name,
        db,
        current_user,
    )

    author_id = (
        payload.author_id
        or current_user.id
    )

    _verify_actor(
        author_id,
        current_user,
        db,
    )

    issue = Issue(
        repository_id=repo.id,
        author_id=author_id,
        title=payload.title,
        body=payload.body,
    )

    db.add(issue)
    db.commit()
    db.refresh(issue)

    NotificationService.create_notification(
        db=db,
        user_id=repo.owner_id,
        title=f"New issue: {issue.title}",
        message=(
            f"Issue #{issue.id[:8]} "
            f"was created in {repo_name}."
        ),
        type="issue",
        link=(
            f"/repositories/"
            f"{repo_name}/issues/{issue.id}"
        ),
    )

    return issue


@router.get(
    "",
    response_model=list[IssueResponse],
)
def list_issues(
    owner_name: str,
    repo_name: str,
    state: str = Query(
        "all",
        pattern="^(open|closed|all)$",
    ),
    limit: int = Query(
        50,
        ge=1,
        le=100,
    ),
    offset: int = Query(
        0,
        ge=0,
    ),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    repo = get_repository_for_user(
        owner_name,
        repo_name,
        db,
        current_user,
    )

    stmt = select(Issue).where(
        Issue.repository_id == repo.id
    )

    if state != "all":
        stmt = stmt.where(
            Issue.status == state
        )

    stmt = (
        stmt
        .order_by(Issue.created_at.desc())
        .limit(limit)
        .offset(offset)
    )

    issues = db.scalars(stmt).all()

    return list(issues)


@router.get(
    "/{issue_id}",
    response_model=IssueResponse,
)
def get_issue(
    owner_name: str,
    repo_name: str,
    issue_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    repo = get_repository_for_user(
        owner_name,
        repo_name,
        db,
        current_user,
    )

    issue = db.scalar(
        select(Issue).where(
            Issue.id == issue_id,
            Issue.repository_id == repo.id,
        )
    )

    if not issue:
        raise HTTPException(
            status_code=404,
            detail="Issue not found",
        )

    return issue


@router.post(
    "/{issue_id}/comments",
    response_model=IssueCommentResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_issue_comment(
    owner_name: str,
    repo_name: str,
    issue_id: str,
    payload: IssueCommentCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    repo = get_repository_for_user(
        owner_name,
        repo_name,
        db,
        current_user,
    )

    issue = db.scalar(
        select(Issue).where(
            Issue.id == issue_id,
            Issue.repository_id == repo.id,
        )
    )

    if not issue:
        raise HTTPException(
            status_code=404,
            detail="Issue not found",
        )

    author_id = (
        payload.author_id
        or current_user.id
    )

    _verify_actor(
        author_id,
        current_user,
        db,
    )

    comment = _create_issue_comment(
        issue=issue,
        author_id=author_id,
        body=payload.body,
        db=db,
    )

    db.commit()
    db.refresh(comment)

    return comment


@router.get(
    "/{issue_id}/comments",
    response_model=list[IssueCommentResponse],
)
def get_issue_comments(
    owner_name: str,
    repo_name: str,
    issue_id: str,
    limit: int = Query(
        50,
        ge=1,
        le=100,
    ),
    offset: int = Query(
        0,
        ge=0,
    ),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    repo = get_repository_for_user(
        owner_name,
        repo_name,
        db,
        current_user,
    )

    issue = db.scalar(
        select(Issue).where(
            Issue.id == issue_id,
            Issue.repository_id == repo.id,
        )
    )

    if not issue:
        raise HTTPException(
            status_code=404,
            detail="Issue not found",
        )

    stmt = (
        select(IssueComment)
        .where(
            IssueComment.issue_id == issue.id
        )
        .order_by(
            IssueComment.created_at.asc()
        )
        .limit(limit)
        .offset(offset)
    )

    comments = db.scalars(stmt).all()

    return list(comments)


class IssueStatusRequest(BaseModel):
    status: str = Field(
        pattern="^(open|closed)$"
    )

    resolution: str | None = Field(
        default=None,
        pattern="^(completed|not_planned|duplicate)$",
    )

    comment: str | None = Field(
        default=None,
        max_length=10000,
    )


@router.patch(
    "/{issue_id}/status",
)
def update_issue_status(
    owner_name: str,
    repo_name: str,
    issue_id: str,
    payload: IssueStatusRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    repo = get_repository_for_user(
        owner_name,
        repo_name,
        db,
        current_user,
    )

    issue = db.scalar(
        select(Issue).where(
            Issue.id == issue_id,
            Issue.repository_id == repo.id,
        )
    )

    if not issue:
        raise HTTPException(
            status_code=404,
            detail="Issue not found",
        )

    now = datetime.now(timezone.utc)

    # ---------------------------------------------------------
    # CLOSE
    # ---------------------------------------------------------
    if payload.status == "closed":

        if not payload.resolution:
            raise HTTPException(
                status_code=400,
                detail=(
                    "A resolution is required when "
                    "closing an issue."
                ),
            )

        if not payload.comment or not payload.comment.strip():
            raise HTTPException(
                status_code=400,
                detail=(
                    "A closing comment is required "
                    "when closing an issue."
                ),
            )

        resolution_labels = {
            "completed": "completed",
            "not_planned": "not planned",
            "duplicate": "duplicate",
        }

        resolution_label = resolution_labels[
            payload.resolution
        ]

        audit_body = (
            f"Closed as {resolution_label}.\n\n"
            f"{payload.comment.strip()}"
        )

        _create_issue_comment(
            issue=issue,
            author_id=current_user.id,
            body=audit_body,
            db=db,
        )

        issue.status = "closed"
        issue.closed_at = now
        issue.updated_at = now

        db.commit()
        db.refresh(issue)

        NotificationService.create_notification(
            db=db,
            user_id=repo.owner_id,
            title=f"Issue resolved: {issue.title}",
            message=(
                f"Issue #{issue.id[:8]} was "
                f"closed as {resolution_label}."
            ),
            type="issue",
            link=(
                f"/repositories/"
                f"{repo_name}/issues/{issue.id}"
            ),
        )

        return {
            "status": "ok",
            "issue_status": "closed",
            "resolution": payload.resolution,
        }

    # ---------------------------------------------------------
    # REOPEN
    # ---------------------------------------------------------
    issue.status = "open"
    issue.closed_at = None
    issue.updated_at = now

    if payload.comment and payload.comment.strip():
        _create_issue_comment(
            issue=issue,
            author_id=current_user.id,
            body=(
                "Reopened.\n\n"
                f"{payload.comment.strip()}"
            ),
            db=db,
        )

    db.commit()
    db.refresh(issue)

    NotificationService.create_notification(
        db=db,
        user_id=repo.owner_id,
        title=f"Issue reopened: {issue.title}",
        message=(
            f"Issue #{issue.id[:8]} was reopened "
            f"in {repo_name}."
        ),
        type="issue",
        link=(
            f"/repositories/"
            f"{repo_name}/issues/{issue.id}"
        ),
    )

    return {
        "status": "ok",
        "issue_status": "open",
        "resolution": None,
    }


@router.delete(
    "/{issue_id}",
)
def delete_issue(
    owner_name: str,
    repo_name: str,
    issue_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    repo = get_repository_for_user(
        owner_name,
        repo_name,
        db,
        current_user,
    )

    issue = db.scalar(
        select(Issue).where(
            Issue.id == issue_id,
            Issue.repository_id == repo.id,
        )
    )

    if not issue:
        raise HTTPException(
            status_code=404,
            detail="Issue not found",
        )

    db.delete(issue)
    db.commit()

    return {
        "status": "deleted"
    }