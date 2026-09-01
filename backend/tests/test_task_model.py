from uuid import uuid4
import pytest
from sqlalchemy import select

from app.models.task import Task
from app.models.user import User
from app.services.repository_service import RepositoryService


def setup_task_model_fixtures(db):
    user = User(
        id=str(uuid4()),
        username=f"task_muser_{uuid4().hex[:8]}",
        email=f"taskmuser_{uuid4().hex[:8]}@example.com",
        password_hash="hash",
    )
    db.add(user)
    db.flush()

    repo = RepositoryService(db).create(
        owner_id=user.id,
        name=f"task_mrepo_{uuid4().hex[:8]}",
        description="Task Model Repo",
        visibility="private",
    )

    return user, repo


def test_create_task_model(db):
    user, repo = setup_task_model_fixtures(db)

    task = Task(
        repository_id=repo.id,
        created_by=user.id,
        title="Implement Task System",
        description="Build Task System orchestration layer",
        status=Task.STATUS_OPEN,
        priority=Task.PRIORITY_HIGH,
        task_type=Task.TYPE_FEATURE,
    )
    db.add(task)
    db.commit()

    saved = db.scalar(select(Task).where(Task.id == task.id))
    assert saved is not None
    assert saved.repository_id == repo.id
    assert saved.created_by == user.id
    assert saved.title == "Implement Task System"
    assert saved.status == Task.STATUS_OPEN
    assert saved.priority == Task.PRIORITY_HIGH
