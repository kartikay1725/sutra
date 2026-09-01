from datetime import datetime

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
)
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.agent_dependencies import get_current_agent_session
from app.db.session import get_db
from app.models.agent_session import AgentSession
from app.models.task import Task
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
        claimed_by_session_id=task.claimed_by_session_id,
        lease_expires_at=task.lease_expires_at,
        resulting_change_id=task.resulting_change_id,
        resulting_pull_request_id=task.resulting_pull_request_id,
        started_at=task.started_at,
        completed_at=task.completed_at,
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