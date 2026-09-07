from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.agent_dependencies import get_current_agent_session
from app.core.config import settings
from app.db.session import get_db

from app.models.agent import Agent
from app.models.agent_session import AgentSession
from app.models.issue import Issue
from app.models.repository import Repository
from app.models.task import Task

from app.providers.github.auth import GitHubAppAuthService
from app.providers.github.repository import GitHubRepositoryProvider

from app.services.agent_issue_service import AgentIssueService


router = APIRouter(
    prefix="/v1/agent/tasks",
    tags=["agent-issues"],
)


class AgentIssueCreateRequest(BaseModel):
    title: str = Field(
        min_length=1,
        max_length=200,
    )
    body: str = Field(
        min_length=1,
        max_length=10000,
    )


class AgentIssueResponse(BaseModel):
    id: str
    repository_id: str

    github_issue_id: str | None
    github_issue_number: int | None
    github_html_url: str | None

    source_type: str

    author_id: str | None
    agent_id: str | None
    agent_session_id: str | None
    task_id: str | None

    title: str
    body: str
    status: str

    github_author_login: str | None

    created_at: str
    updated_at: str
    closed_at: str | None


def _github_provider() -> GitHubRepositoryProvider:
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


def _response(issue: Issue) -> AgentIssueResponse:
    return AgentIssueResponse(
        id=issue.id,
        repository_id=issue.repository_id,
        github_issue_id=issue.github_issue_id,
        github_issue_number=issue.github_issue_number,
        github_html_url=issue.github_html_url,
        source_type=issue.source_type,
        author_id=issue.author_id,
        agent_id=issue.agent_id,
        agent_session_id=issue.agent_session_id,
        task_id=issue.task_id,
        title=issue.title,
        body=issue.body,
        status=issue.status,
        github_author_login=issue.github_author_login,
        created_at=issue.created_at.isoformat(),
        updated_at=issue.updated_at.isoformat(),
        closed_at=(
            issue.closed_at.isoformat()
            if issue.closed_at
            else None
        ),
    )


@router.post(
    "/{task_id}/issues",
    response_model=AgentIssueResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_agent_issue(
    task_id: str,
    payload: AgentIssueCreateRequest,
    session: AgentSession = Depends(
        get_current_agent_session
    ),
    db: Session = Depends(get_db),
):
    """
    Create a GitHub Issue on behalf of the authenticated
    SUTRA agent for the task it currently owns.

    Identity is derived from AgentSession.
    The agent cannot choose another agent/session/task.
    """

    # ---------------------------------------------------------
    # Resolve task
    # ---------------------------------------------------------

    task = db.scalar(
        select(Task).where(
            Task.id == task_id,
        )
    )

    if task is None:
        raise HTTPException(
            status_code=404,
            detail="Task not found",
        )

    # ---------------------------------------------------------
    # Explicit authorization boundary
    # ---------------------------------------------------------

    if task.assigned_agent_id != session.agent_id:
        raise HTTPException(
            status_code=403,
            detail="Agent is not assigned to this task",
        )

    if task.claimed_by_session_id != session.id:
        raise HTTPException(
            status_code=403,
            detail="Agent session does not hold this task lease",
        )

    # ---------------------------------------------------------
    # Load agent
    # ---------------------------------------------------------

    agent = db.scalar(
        select(Agent).where(
            Agent.id == session.agent_id,
            Agent.is_active.is_(True),
            Agent.status == "active",
        )
    )

    if agent is None:
        raise HTTPException(
            status_code=401,
            detail="Agent is inactive or revoked",
        )

    # ---------------------------------------------------------
    # Load repository
    # ---------------------------------------------------------

    repository = db.scalar(
        select(Repository).where(
            Repository.id == task.repository_id,
        )
    )

    if repository is None:
        raise HTTPException(
            status_code=404,
            detail="Task repository not found",
        )

    # ---------------------------------------------------------
    # Create GitHub-backed Agent Issue
    # ---------------------------------------------------------

    try:
        issue = AgentIssueService(
            db=db,
            provider=_github_provider(),
        ).create_issue(
            session=session,
            task=task,
            title=payload.title,
            body=payload.body,
        )

        db.commit()
        db.refresh(issue)

        return _response(issue)

    except PermissionError as exc:
        db.rollback()

        raise HTTPException(
            status_code=403,
            detail=str(exc),
        ) from exc

    except ValueError as exc:
        db.rollback()

        raise HTTPException(
            status_code=409,
            detail=str(exc),
        ) from exc

    except HTTPException:
        db.rollback()
        raise

    except Exception as exc:
        db.rollback()

        raise HTTPException(
            status_code=502,
            detail=f"Agent issue creation failed: {exc}",
        ) from exc