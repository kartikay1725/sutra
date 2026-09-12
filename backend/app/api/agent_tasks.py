from datetime import datetime

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    status,
)
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.agent_dependencies import get_current_agent_session
from app.api.changes import ChangeResponse, _to_change_response
from app.api.pull_requests import PullRequestResponse, _to_response
from app.core.config import settings
from app.db.session import get_db
from app.models.agent_session import AgentSession
from app.models.repository import Repository
from app.models.task import Task
from app.providers.github.auth import GitHubAppAuthService
from app.providers.github.repository import GitHubRepositoryProvider
from app.services.agent_change_service import AgentChangeService
from app.services.task_service import TaskService


router = APIRouter(
    prefix="/v1/agent/tasks",
    tags=["agent-tasks"],
)


class AgentTaskResponse(BaseModel):
    id: str
    repository_id: str
    assigned_agent_id: str | None

    title: str
    description: str | None

    status: str
    priority: str
    task_type: str

    claimed_by_session_id: str | None
    lease_expires_at: datetime | None

    resulting_change_id: str | None
    resulting_pull_request_id: str | None

    started_at: datetime | None
    completed_at: datetime | None

    source: str | None = None
    execution_summary: str | None = None
    validation_summary: str | None = None


def _response(task: Task) -> AgentTaskResponse:
    return AgentTaskResponse(
        id=task.id,
        repository_id=task.repository_id,
        assigned_agent_id=task.assigned_agent_id,
        title=task.title,
        description=task.description,
        status=task.status,
        priority=task.priority,
        task_type=task.task_type,
        source=task.source,
        claimed_by_session_id=task.claimed_by_session_id,
        lease_expires_at=task.lease_expires_at,
        resulting_change_id=task.resulting_change_id,
        resulting_pull_request_id=task.resulting_pull_request_id,
        started_at=task.started_at,
        completed_at=task.completed_at,
        execution_summary=task.execution_summary,
        validation_summary=task.validation_summary,
    )


def _handle_error(exc: Exception) -> HTTPException:
    if isinstance(exc, PermissionError):
        return HTTPException(
            status_code=403,
            detail=str(exc),
        )

    if isinstance(exc, ValueError):
        return HTTPException(
            status_code=409,
            detail=str(exc),
        )

    return HTTPException(
        status_code=500,
        detail="Agent task operation failed",
    )


@router.post(
    "/{task_id}/claim",
    response_model=AgentTaskResponse,
)
def claim_task(
    task_id: str,
    session: AgentSession = Depends(
        get_current_agent_session
    ),
    db: Session = Depends(get_db),
):
    try:
        task = TaskService(db).claim_agent_task(
            task_id,
            session,
        )

        db.commit()
        db.refresh(task)

        return _response(task)

    except Exception as exc:
        db.rollback()
        raise _handle_error(exc) from exc


@router.post(
    "/{task_id}/heartbeat",
    response_model=AgentTaskResponse,
)
def heartbeat_task(
    task_id: str,
    session: AgentSession = Depends(
        get_current_agent_session
    ),
    db: Session = Depends(get_db),
):
    try:
        task = TaskService(db).heartbeat_agent_task(
            task_id,
            session,
        )

        db.commit()
        db.refresh(task)

        return _response(task)

    except Exception as exc:
        if isinstance(exc, ValueError) and str(exc) == "Task lease expired":
            db.commit()
        else:
            db.rollback()

        raise _handle_error(exc) from exc


@router.post(
    "/{task_id}/release",
    response_model=AgentTaskResponse,
)
def release_task(
    task_id: str,
    session: AgentSession = Depends(
        get_current_agent_session
    ),
    db: Session = Depends(get_db),
):
    try:
        task = TaskService(db).release_agent_task(
            task_id,
            session,
        )

        db.commit()
        db.refresh(task)

        return _response(task)

    except Exception as exc:
        db.rollback()
        raise _handle_error(exc) from exc


@router.post(
    "/{task_id}/execute",
    response_model=AgentTaskResponse,
)
def execute_task(
    task_id: str,
    session: AgentSession = Depends(
        get_current_agent_session
    ),
    db: Session = Depends(get_db),
):
    try:
        task = TaskService(db).execute_agent_task(
            task_id=task_id,
            actor_id=session.agent_id,
            session=session,
        )

        db.commit()
        db.refresh(task)

        return _response(task)

    except Exception as exc:
        if isinstance(exc, ValueError) and str(exc) == "Task lease expired":
            db.commit()
        else:
            db.rollback()
        raise _handle_error(exc) from exc


class AgentTaskChangeCreateRequest(BaseModel):
    intent: str = Field(default="", max_length=5000)
    title: str | None = None
    description: str | None = None
    branch: str | None = None
    base_branch: str | None = None
    base_commit: str | None = None
    risk_level: str = "unknown"

    @model_validator(mode="before")
    @classmethod
    def resolve_intent(cls, data):
        if isinstance(data, dict):
            if not data.get("intent"):
                data["intent"] = data.get("title") or data.get("description") or "Agent change"
        return data


class AgentTaskChangeCommitRequest(BaseModel):
    resulting_commit: str = Field(
        default="",
        max_length=64,
    )
    commit_sha: str | None = None
    message: str | None = None
    author_name: str | None = None
    author_email: str | None = None

    @model_validator(mode="before")
    @classmethod
    def resolve_commit(cls, data):
        if isinstance(data, dict):
            if not data.get("resulting_commit") and data.get("commit_sha"):
                data["resulting_commit"] = data["commit_sha"]
        return data


def _get_provider_for_repository(repository: Repository):
    if repository.provider_type == "github":
        if settings.github_app_id and settings.github_private_key_pem:
            auth_service = GitHubAppAuthService(
                app_id=settings.github_app_id,
                private_key_pem=settings.github_private_key_pem,
                base_url=settings.github_api_base_url,
            )
            return GitHubRepositoryProvider(
                auth_service=auth_service,
                base_url=settings.github_api_base_url,
            )
    return None


@router.post(
    "/{task_id}/changes",
    response_model=ChangeResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create Change for Claimed Agent Task",
    description="Agent declares intent to create a Change for its claimed task. Enforces AgentSession task lease ownership.",
)
def create_agent_task_change(
    task_id: str,
    payload: AgentTaskChangeCreateRequest,
    session: AgentSession = Depends(get_current_agent_session),
    db: Session = Depends(get_db),
):
    task = db.scalar(select(Task).where(Task.id == task_id))
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    repository = db.scalar(select(Repository).where(Repository.id == task.repository_id))
    if not repository:
        raise HTTPException(status_code=404, detail="Task repository not found")

    provider = _get_provider_for_repository(repository)
    svc = AgentChangeService(db=db, provider=provider)

    try:
        change = svc.create_change(
            session=session,
            task=task,
            intent=payload.intent,
            branch=payload.branch,
            base_branch=payload.base_branch,
            base_commit=payload.base_commit,
            risk_level=payload.risk_level,
        )
        db.commit()
        db.refresh(change)
        return _to_change_response(change, None, db)
    except PermissionError as exc:
        db.rollback()
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except HTTPException:
        db.rollback()
        raise
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to create agent change: {exc}") from exc


@router.post(
    "/{task_id}/commit",
    response_model=ChangeResponse,
    summary="Record Resulting Commit for Claimed Agent Task",
    description="Agent attaches resulting commit for its claimed task change. Enforces AgentSession task lease ownership.",
)
def record_agent_task_commit(
    task_id: str,
    payload: AgentTaskChangeCommitRequest,
    session: AgentSession = Depends(get_current_agent_session),
    db: Session = Depends(get_db),
):
    task = db.scalar(select(Task).where(Task.id == task_id))
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    repository = db.scalar(select(Repository).where(Repository.id == task.repository_id))
    if not repository:
        raise HTTPException(status_code=404, detail="Task repository not found")

    provider = _get_provider_for_repository(repository)
    svc = AgentChangeService(db=db, provider=provider)

    try:
        change = svc.record_commit(
            session=session,
            task=task,
            resulting_commit=payload.resulting_commit,
        )
        db.commit()
        db.refresh(change)
        return _to_change_response(change, None, db)
    except PermissionError as exc:
        db.rollback()
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except HTTPException:
        db.rollback()
        raise
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to record agent commit: {exc}") from exc


class AgentTaskPRCreateRequest(BaseModel):
    title: str | None = None
    target_branch: str | None = None
    description: str | None = None
    is_draft: bool = False


@router.post(
    "/{task_id}/pull-requests",
    response_model=PullRequestResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create Pull Request for Claimed Agent Task",
    description="Agent creates a GitHub & SUTRA Pull Request for its recorded Change. Enforces AgentSession lease ownership and recorded commit.",
)
def create_agent_task_pull_request(
    task_id: str,
    payload: AgentTaskPRCreateRequest,
    session: AgentSession = Depends(get_current_agent_session),
    db: Session = Depends(get_db),
):
    task = db.scalar(select(Task).where(Task.id == task_id))
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    repository = db.scalar(select(Repository).where(Repository.id == task.repository_id))
    if not repository:
        raise HTTPException(status_code=404, detail="Task repository not found")

    provider = _get_provider_for_repository(repository)
    svc = AgentChangeService(db=db, provider=provider)

    try:
        pr = svc.create_pull_request(
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
    except PermissionError as exc:
        db.rollback()
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except HTTPException:
        db.rollback()
        raise
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to create agent pull request: {exc}") from exc