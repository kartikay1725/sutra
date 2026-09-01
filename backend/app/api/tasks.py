from datetime import datetime

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    status,
)
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.db.session import get_db
from app.models.repository import Repository
from app.models.task import Task
from app.models.user import User
from app.services.task_service import TaskService


router = APIRouter(
    prefix="/v1",
    tags=["tasks"],
)


class CreateTaskRequest(BaseModel):
    title: str = Field(
        min_length=1,
        max_length=255,
    )

    description: str | None = Field(
        default=None,
        max_length=10000,
    )

    priority: str = Field(
        default=Task.PRIORITY_MEDIUM,
    )

    task_type: str = Field(
        default=Task.TYPE_FEATURE,
    )


class AssignTaskRequest(BaseModel):
    assigned_user_id: str | None = None
    assigned_agent_id: str | None = None


class TaskResponse(BaseModel):
    id: str
    repository_id: str
    created_by: str

    assigned_agent_id: str | None
    assigned_user_id: str | None

    claimed_by_session_id: str | None
    lease_expires_at: datetime | None

    resulting_change_id: str | None
    resulting_pull_request_id: str | None

    title: str
    description: str | None

    status: str
    priority: str
    task_type: str
    source: str

    created_at: datetime
    updated_at: datetime

    started_at: datetime | None
    completed_at: datetime | None
    cancelled_at: datetime | None


def _to_response(task: Task) -> TaskResponse:
    return TaskResponse(
        id=task.id,
        repository_id=task.repository_id,
        created_by=task.created_by,

        assigned_agent_id=task.assigned_agent_id,
        assigned_user_id=task.assigned_user_id,

        claimed_by_session_id=task.claimed_by_session_id,
        lease_expires_at=task.lease_expires_at,

        resulting_change_id=task.resulting_change_id,
        resulting_pull_request_id=task.resulting_pull_request_id,

        title=task.title,
        description=task.description,

        status=task.status,
        priority=task.priority,
        task_type=task.task_type,
        source=task.source,

        created_at=task.created_at,
        updated_at=task.updated_at,

        started_at=task.started_at,
        completed_at=task.completed_at,
        cancelled_at=task.cancelled_at,
    )


def _repository_for_owner(
    repo_owner: str,
    repo_name: str,
    db: Session,
) -> Repository:
    repository = db.scalar(
        select(Repository)
        .join(
            User,
            User.id == Repository.owner_id,
        )
        .where(
            User.username == repo_owner,
            Repository.slug == repo_name.lower(),
            Repository.deleted_at.is_(None),
        )
    )

    if repository is None:
        raise HTTPException(
            status_code=404,
            detail="Repository not found",
        )

    return repository


def _service_error(exc: Exception) -> HTTPException:
    if isinstance(exc, PermissionError):
        return HTTPException(
            status_code=403,
            detail=str(exc),
        )

    if isinstance(exc, ValueError):
        message = str(exc)

        if message == "Task not found":
            return HTTPException(
                status_code=404,
                detail=message,
            )

        return HTTPException(
            status_code=400,
            detail=message,
        )

    return HTTPException(
        status_code=500,
        detail="Task operation failed",
    )


@router.post(
    "/repositories/{owner}/{repo}/tasks",
    response_model=TaskResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_task(
    owner: str,
    repo: str,
    payload: CreateTaskRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    repository = _repository_for_owner(
        owner,
        repo,
        db,
    )

    if repository.owner_id != current_user.id:
        raise HTTPException(
            status_code=403,
            detail="You do not own this repository",
        )

    try:
        task = TaskService(db).create_task(
            repository_id=repository.id,
            created_by_id=current_user.id,
            title=payload.title,
            description=payload.description,
            priority=payload.priority,
            task_type=payload.task_type,
        )

        db.commit()
        db.refresh(task)

        return _to_response(task)

    except Exception as exc:
        db.rollback()
        raise _service_error(exc) from exc


@router.get(
    "/repositories/{owner}/{repo}/tasks",
    response_model=list[TaskResponse],
)
def list_tasks(
    owner: str,
    repo: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    repository = _repository_for_owner(
        owner,
        repo,
        db,
    )

    try:
        tasks = TaskService(db).list_tasks_for_repository(
            repository.id,
            current_user.id,
        )

        return [
            _to_response(task)
            for task in tasks
        ]

    except Exception as exc:
        raise _service_error(exc) from exc


@router.get(
    "/tasks/{task_id}",
    response_model=TaskResponse,
)
def get_task(
    task_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        task = TaskService(db).get_task(
            task_id,
            current_user.id,
        )

        return _to_response(task)

    except Exception as exc:
        raise _service_error(exc) from exc

@router.delete(
    "/tasks/{task_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_task(
    task_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        # In a real app, you might want a soft delete or proper authorization checks here
        # For now, we allow the creator or assignee to delete it.
        task = db.scalar(select(Task).where(Task.id == task_id))
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")
            
        if task.created_by != current_user.id and task.assigned_user_id != current_user.id:
            raise HTTPException(status_code=403, detail="Not authorized to delete this task")
            
        db.delete(task)
        db.commit()
    except Exception as exc:
        db.rollback()
        if isinstance(exc, HTTPException):
            raise exc
        raise _service_error(exc) from exc


@router.post(
    "/tasks/{task_id}/assign",
    response_model=TaskResponse,
)
def assign_task(
    task_id: str,
    payload: AssignTaskRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        task = TaskService(db).assign_task(
            task_id=task_id,
            actor_id=current_user.id,
            assigned_user_id=payload.assigned_user_id,
            assigned_agent_id=payload.assigned_agent_id,
        )

        db.commit()
        db.refresh(task)

        return _to_response(task)

    except Exception as exc:
        db.rollback()
        raise _service_error(exc) from exc


@router.post(
    "/tasks/{task_id}/start",
    response_model=TaskResponse,
)
def start_task(
    task_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        task = TaskService(db).start_task(
            task_id,
            current_user.id,
        )

        db.commit()
        db.refresh(task)

        return _to_response(task)

    except Exception as exc:
        db.rollback()
        raise _service_error(exc) from exc


@router.post(
    "/tasks/{task_id}/complete",
    response_model=TaskResponse,
)
def complete_task(
    task_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        task = TaskService(db).complete_task(
            task_id,
            current_user.id,
        )

        db.commit()
        db.refresh(task)

        return _to_response(task)

    except Exception as exc:
        db.rollback()
        raise _service_error(exc) from exc


@router.post(
    "/tasks/{task_id}/cancel",
    response_model=TaskResponse,
)
def cancel_task(
    task_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        task = TaskService(db).cancel_task(
            task_id,
            current_user.id,
        )

        db.commit()
        db.refresh(task)

        return _to_response(task)

    except Exception as exc:
        db.rollback()
        raise _service_error(exc) from exc

@router.post(
    "/agents/{agent_id}/tasks/next",
    response_model=TaskResponse,
)
def pick_next_task(
    agent_id: str,
    db: Session = Depends(get_db),
):
    # Agents can call this to auto-assign themselves the top priority unassigned task
    task = db.scalar(
        select(Task)
        .where(Task.status == Task.STATUS_OPEN)
        .where(Task.assigned_user_id.is_(None))
        .where(Task.assigned_agent_id.is_(None))
        .order_by(Task.priority_index.asc(), Task.created_at.asc())
    )

    if not task:
        raise HTTPException(
            status_code=404,
            detail="No tasks available",
        )

    task.assigned_agent_id = agent_id
    task.status = Task.STATUS_ASSIGNED
    db.commit()
    db.refresh(task)

    return _to_response(task)