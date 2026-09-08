from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.models.issue import Issue, IssueComment
from app.models.repository import Repository
from app.models.user import User

from app.providers.github.auth import GitHubAppAuthService
from app.providers.github.repository import GitHubRepositoryProvider
from app.core.config import settings

from app.services.notification_service import NotificationService


router = APIRouter(
    prefix="/v1/repositories/{owner_name}/{repo_name}/issues",
    tags=["issues"],
)


# ============================================================
# REQUEST / RESPONSE MODELS
# ============================================================


class IssueCreateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    body: str = Field(min_length=1, max_length=10000)

    # Reserved for the future agent issue pathway.
    agent_id: Optional[str] = None
    agent_session_id: Optional[str] = None
    task_id: Optional[str] = None


class IssueCommentCreateRequest(BaseModel):
    body: str = Field(
        min_length=1,
        max_length=10000,
    )


class IssueStatusRequest(BaseModel):
    status: str = Field(
        pattern="^(open|closed)$"
    )

    # Optional comment that will be posted to GitHub.
    comment: Optional[str] = Field(
        default=None,
        max_length=10000,
    )


class IssueResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    repository_id: str

    # GitHub identity.
    github_issue_id: Optional[str]
    github_issue_number: Optional[int]
    github_html_url: Optional[str]

    source_type: str

    agent_id: Optional[str]
    agent_session_id: Optional[str]
    task_id: Optional[str]

    title: str
    body: str
    status: str

    github_author_login: Optional[str]

    created_at: datetime
    updated_at: datetime
    closed_at: Optional[datetime]


class IssueCommentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    issue_id: str

    github_comment_id: Optional[str]
    github_html_url: Optional[str]

    author_id: Optional[str]
    github_author_login: Optional[str]

    body: str

    created_at: datetime
    updated_at: datetime


# ============================================================
# REPOSITORY / PROVIDER HELPERS
# ============================================================


def get_repository_for_user(
    owner_name: str,
    repo_name: str,
    db: Session,
    user: User,
) -> Repository:
    """
    Resolve the SUTRA repository.

    The GitHub repository itself is identified using
    Repository.provider_owner + Repository.name.
    """
    repo = db.scalar(
        select(Repository)
        .join(
            User,
            User.id == Repository.owner_id,
        )
        .where(
            User.username == owner_name,
            Repository.slug == repo_name.lower(),
            Repository.deleted_at.is_(None),
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


def _github_provider(
    repository: Repository,
) -> GitHubRepositoryProvider:
    if repository.provider_type != "github":
        raise HTTPException(
            status_code=400,
            detail=(
                "This Issues API currently supports "
                "GitHub repositories only."
            ),
        )

    if not repository.provider_owner:
        raise HTTPException(
            status_code=500,
            detail="GitHub repository owner metadata is missing",
        )

    if (
        not settings.github_app_id
        or not settings.github_private_key_pem
    ):
        raise HTTPException(
            status_code=503,
            detail="GitHub App is not configured",
        )

    auth_service = GitHubAppAuthService(
        app_id=settings.github_app_id,
        private_key_pem=settings.github_private_key_pem,
        base_url=settings.github_api_base_url,
    )

    return GitHubRepositoryProvider(
        auth_service=auth_service,
        base_url=settings.github_api_base_url,
    )


# ============================================================
# LOCAL LINKAGE HELPERS
# ============================================================


def _find_linked_issue(
    *,
    repository_id: str,
    github_issue_number: int,
    db: Session,
) -> Optional[Issue]:
    return db.scalar(
        select(Issue).where(
            Issue.repository_id == repository_id,
            Issue.github_issue_number == github_issue_number,
        )
    )


def _sync_issue_link(
    *,
    repository: Repository,
    github_issue,
    db: Session,
    source_type: str = "human",
    agent_id: Optional[str] = None,
    agent_session_id: Optional[str] = None,
    task_id: Optional[str] = None,
    author_id: Optional[str] = None,
) -> Issue:
    """
    Synchronize a GitHub issue into SUTRA's lightweight
    provenance/linkage record.

    GitHub remains authoritative.
    """

    issue = _find_linked_issue(
        repository_id=repository.id,
        github_issue_number=github_issue.number,
        db=db,
    )

    now = datetime.now(timezone.utc)

    if issue is None:
        issue = Issue(
            repository_id=repository.id,
            github_issue_id=str(github_issue.id),
            github_issue_number=github_issue.number,
            github_html_url=github_issue.html_url,
            source_type=source_type,
            agent_id=agent_id,
            agent_session_id=agent_session_id,
            task_id=task_id,
            author_id=author_id,
            title=github_issue.title,
            body=github_issue.body or "",
            status=github_issue.state,
            github_author_login=github_issue.author_login,
            created_at=github_issue.created_at,
            updated_at=github_issue.updated_at,
            closed_at=github_issue.closed_at,
        )

        db.add(issue)

    else:
        issue.github_issue_id = str(github_issue.id)
        issue.github_html_url = github_issue.html_url

        issue.title = github_issue.title
        issue.body = github_issue.body or ""
        issue.status = github_issue.state
        issue.github_author_login = (
            github_issue.author_login
        )

        issue.created_at = github_issue.created_at
        issue.updated_at = github_issue.updated_at
        issue.closed_at = github_issue.closed_at

        # Only populate provenance when explicitly supplied.
        if agent_id is not None:
            issue.agent_id = agent_id

        if agent_session_id is not None:
            issue.agent_session_id = agent_session_id

        if task_id is not None:
            issue.task_id = task_id

        if author_id is not None:
            issue.author_id = author_id

        issue.source_type = source_type

        issue.updated_at = now

    db.flush()

    return issue


def _sync_comment(
    *,
    issue: Issue,
    github_comment,
    db: Session,
) -> IssueComment:
    existing = db.scalar(
        select(IssueComment).where(
            IssueComment.github_comment_id
            == str(github_comment.id),
        )
    )

    if existing:
        existing.body = github_comment.body
        existing.github_html_url = github_comment.html_url
        existing.github_author_login = (
            github_comment.author_login
        )
        existing.updated_at = github_comment.updated_at
        db.flush()
        return existing

    comment = IssueComment(
        issue_id=issue.id,
        github_comment_id=str(github_comment.id),
        github_html_url=github_comment.html_url,
        author_id=None,
        github_author_login=github_comment.author_login,
        body=github_comment.body,
        created_at=github_comment.created_at,
        updated_at=github_comment.updated_at,
    )

    db.add(comment)
    db.flush()

    return comment


# ============================================================
# CREATE ISSUE
# ============================================================


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
    # SUTRA IS NOT A GITHUB REPLACEMENT.
    # Humans must create issues directly on GitHub. SUTRA is a read, observe, and governance control plane.
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Issues must be created directly on GitHub. SUTRA is an observation and governance control plane.",
    )

    repository = get_repository_for_user(
        owner_name,
        repo_name,
        db,
        current_user,
    )

    provider = _github_provider(repository)

    try:
        github_issue = provider.create_issue(
            owner=repository.provider_owner,
            name=repository.name,
            title=payload.title,
            body=payload.body,
        )

        # This is a normal human-created issue unless the
        # future agent pathway explicitly supplies agent identity.
        source_type = (
            "agent"
            if payload.agent_id
            else "human"
        )

        issue = _sync_issue_link(
            repository=repository,
            github_issue=github_issue,
            db=db,
            source_type=source_type,
            agent_id=payload.agent_id,
            agent_session_id=payload.agent_session_id,
            task_id=payload.task_id,
            author_id=current_user.id,
        )

        db.commit()
        db.refresh(issue)

        NotificationService.create_notification(
            db=db,
            user_id=current_user.id,
            title=f"New issue: {issue.title}",
            message=(
                f"GitHub issue #{issue.github_issue_number} "
                f"was created in {repo_name}."
            ),
            type="issue",
            link=(
                f"/repositories/"
                f"{repo_name}/issues/"
                f"{issue.github_issue_number}"
            ),
        )

        return issue

    except HTTPException:
        raise

    except Exception as exc:
        db.rollback()

        raise HTTPException(
            status_code=503,
            detail=f"GitHub issue creation failed: {exc}",
        ) from exc


# ============================================================
# LIST ISSUES
# ============================================================


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
    repository = get_repository_for_user(
        owner_name,
        repo_name,
        db,
        current_user,
    )

    provider = _github_provider(repository)

    try:
        github_issues = provider.list_issues(
            owner=repository.provider_owner,
            name=repository.name,
            state=state,
            limit=limit,
            offset=offset,
        )

        result: list[Issue] = []

        for github_issue in github_issues:
            issue = _sync_issue_link(
                repository=repository,
                github_issue=github_issue,
                db=db,
            )

            result.append(issue)

        db.commit()

        for issue in result:
            db.refresh(issue)

        return result

    except HTTPException:
        raise

    except Exception as exc:
        db.rollback()

        raise HTTPException(
            status_code=503,
            detail=f"GitHub issue listing failed: {exc}",
        ) from exc


# ============================================================
# GET ISSUE
# ============================================================


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
    repository = get_repository_for_user(
        owner_name,
        repo_name,
        db,
        current_user,
    )

    provider = _github_provider(repository)

    try:
        # Existing frontend may still pass the previous local UUID.
        #
        # Prefer the local linkage lookup first so existing routes
        # remain compatible.
        linked_issue = db.scalar(
            select(Issue).where(
                Issue.id == issue_id,
                Issue.repository_id == repository.id,
            )
        )

        github_issue_number: Optional[int] = None

        if linked_issue:
            github_issue_number = (
                linked_issue.github_issue_number
            )
        else:
            # New frontend may pass the GitHub issue number.
            try:
                github_issue_number = int(issue_id)
            except ValueError:
                raise HTTPException(
                    status_code=404,
                    detail="Issue not found",
                )

        github_issue = provider.get_issue(
            owner=repository.provider_owner,
            name=repository.name,
            issue_number=github_issue_number,
        )

        if github_issue is None:
            raise HTTPException(
                status_code=404,
                detail="Issue not found",
            )

        issue = _sync_issue_link(
            repository=repository,
            github_issue=github_issue,
            db=db,
            source_type=(
                linked_issue.source_type
                if linked_issue
                else "human"
            ),
            agent_id=(
                linked_issue.agent_id
                if linked_issue
                else None
            ),
            agent_session_id=(
                linked_issue.agent_session_id
                if linked_issue
                else None
            ),
            task_id=(
                linked_issue.task_id
                if linked_issue
                else None
            ),
            author_id=(
                linked_issue.author_id

                if linked_issue
                else None
            ),
        )

        db.commit()
        db.refresh(issue)

        return issue

    except HTTPException:
        raise

    except Exception as exc:
        db.rollback()

        raise HTTPException(
            status_code=503,
            detail=f"GitHub issue lookup failed: {exc}",
        ) from exc


# ============================================================
# CREATE COMMENT
# ============================================================


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
    repository = get_repository_for_user(
        owner_name,
        repo_name,
        db,
        current_user,
    )

    provider = _github_provider(repository)

    try:
        linked_issue = db.scalar(
            select(Issue).where(
                Issue.id == issue_id,
                Issue.repository_id == repository.id,
            )
        )

        if linked_issue:
            issue_number = linked_issue.github_issue_number
        else:
            try:
                issue_number = int(issue_id)
            except ValueError:
                raise HTTPException(
                    status_code=404,
                    detail="Issue not found",
                )

        if issue_number is None:
            raise HTTPException(
                status_code=404,
                detail="GitHub issue linkage is missing",
            )

        github_comment = provider.create_issue_comment(
            owner=repository.provider_owner,
            name=repository.name,
            issue_number=issue_number,
            body=payload.body,
        )

        # Ensure the issue linkage exists.
        github_issue = provider.get_issue(
            owner=repository.provider_owner,
            name=repository.name,
            issue_number=issue_number,
        )

        if github_issue is None:
            raise HTTPException(
                status_code=404,
                detail="Issue not found on GitHub",
            )

        issue = _sync_issue_link(
            repository=repository,
            github_issue=github_issue,
            db=db,
            source_type=(
                linked_issue.source_type
                if linked_issue
                else "human"
            ),
            agent_id=(
                linked_issue.agent_id
                if linked_issue
                else None
            ),
            agent_session_id=(
                linked_issue.agent_session_id
                if linked_issue
                else None
            ),
            task_id=(
                linked_issue.task_id
                if linked_issue
                else None
            ),
            author_id=(
                linked_issue.author_id

                if linked_issue
                else current_user.id
            ),
        )

        comment = _sync_comment(
            issue=issue,
            github_comment=github_comment,
            db=db,
        )

        db.commit()
        db.refresh(comment)

        return comment

    except HTTPException:
        raise

    except Exception as exc:
        db.rollback()

        raise HTTPException(
            status_code=503,
            detail=f"GitHub issue comment failed: {exc}",
        ) from exc


# ============================================================
# LIST COMMENTS
# ============================================================


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
    repository = get_repository_for_user(
        owner_name,
        repo_name,
        db,
        current_user,
    )

    provider = _github_provider(repository)

    try:
        linked_issue = db.scalar(
            select(Issue).where(
                Issue.id == issue_id,
                Issue.repository_id == repository.id,
            )
        )

        if linked_issue:
            issue_number = linked_issue.github_issue_number
        else:
            try:
                issue_number = int(issue_id)
            except ValueError:
                raise HTTPException(
                    status_code=404,
                    detail="Issue not found",
                )

        if issue_number is None:
            raise HTTPException(
                status_code=404,
                detail="GitHub issue linkage is missing",
            )

        github_issue = provider.get_issue(
            owner=repository.provider_owner,
            name=repository.name,
            issue_number=issue_number,
        )

        if github_issue is None:
            raise HTTPException(
                status_code=404,
                detail="Issue not found",
            )

        issue = _sync_issue_link(
            repository=repository,
            github_issue=github_issue,
            db=db,
            source_type=(
                linked_issue.source_type
                if linked_issue
                else "human"
            ),
            agent_id=(
                linked_issue.agent_id
                if linked_issue
                else None
            ),
            agent_session_id=(
                linked_issue.agent_session_id
                if linked_issue
                else None
            ),
            task_id=(
                linked_issue.task_id
                if linked_issue
                else None
            ),
            author_id=(
                linked_issue.author_id

                if linked_issue
                else current_user.id
            ),
        )

        github_comments = provider.list_issue_comments(
            owner=repository.provider_owner,
            name=repository.name,
            issue_number=issue_number,
            limit=limit,
            offset=offset,
        )

        comments = [
            _sync_comment(
                issue=issue,
                github_comment=comment,
                db=db,
            )
            for comment in github_comments
        ]

        db.commit()

        for comment in comments:
            db.refresh(comment)

        return comments

    except HTTPException:
        raise

    except Exception as exc:
        db.rollback()

        raise HTTPException(
            status_code=503,
            detail=f"GitHub issue comments failed: {exc}",
        ) from exc


# ============================================================
# OPEN / CLOSE
# ============================================================


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
    repository = get_repository_for_user(
        owner_name,
        repo_name,
        db,
        current_user,
    )

    provider = _github_provider(repository)

    try:
        linked_issue = db.scalar(
            select(Issue).where(
                Issue.id == issue_id,
                Issue.repository_id == repository.id,
            )
        )

        if linked_issue:
            issue_number = linked_issue.github_issue_number
        else:
            try:
                issue_number = int(issue_id)
            except ValueError:
                raise HTTPException(
                    status_code=404,
                    detail="Issue not found",
                )

        if issue_number is None:
            raise HTTPException(
                status_code=404,
                detail="GitHub issue linkage is missing",
            )

        # --------------------------------------------------------
        # CLOSE
        # --------------------------------------------------------

        if payload.status == "closed":
            github_issue = provider.close_issue(
                owner=repository.provider_owner,
                name=repository.name,
                issue_number=issue_number,
            )

            resolution_text = (
                "Closed via SUTRA."
            )

            if payload.comment and payload.comment.strip():
                resolution_text += (
                    "\n\n"
                    + payload.comment.strip()
                )

            provider.create_issue_comment(
                owner=repository.provider_owner,
                name=repository.name,
                issue_number=issue_number,
                body=resolution_text,
            )

        # --------------------------------------------------------
        # REOPEN
        # --------------------------------------------------------

        else:
            github_issue = provider.reopen_issue(
                owner=repository.provider_owner,
                name=repository.name,
                issue_number=issue_number,
            )

            if payload.comment and payload.comment.strip():
                provider.create_issue_comment(
                    owner=repository.provider_owner,
                    name=repository.name,
                    issue_number=issue_number,
                    body=payload.comment.strip(),
                )

        issue = _sync_issue_link(
            repository=repository,
            github_issue=github_issue,
            db=db,
            source_type=(
                linked_issue.source_type
                if linked_issue
                else "human"
            ),
            agent_id=(
                linked_issue.agent_id
                if linked_issue
                else None
            ),
            agent_session_id=(
                linked_issue.agent_session_id
                if linked_issue
                else None
            ),
            task_id=(
                linked_issue.task_id
                if linked_issue
                else None
            ),
            author_id=(
                linked_issue.author_id

                if linked_issue
                else current_user.id
            ),
        )

        db.commit()
        db.refresh(issue)

        return {
            "status": "ok",
            "issue_status": github_issue.state,
            "github_issue_number": github_issue.number,
            "resolution": None,
        }

    except HTTPException:
        raise

    except Exception as exc:
        db.rollback()

        raise HTTPException(
            status_code=503,
            detail=f"GitHub issue status update failed: {exc}",
        ) from exc


# ============================================================
# DELETE
# ============================================================


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
    """
    GitHub is authoritative.

    We intentionally do not expose a fake local delete operation.
    GitHub Issues do not provide the deletion semantics that the old
    SUTRA-local issue model provided.

    Use GitHub itself for issue deletion where applicable.
    """

    raise HTTPException(
        status_code=405,
        detail=(
            "Issue deletion is controlled by GitHub. "
            "SUTRA does not delete GitHub issues."
        ),
    )