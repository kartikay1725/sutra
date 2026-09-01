import json
from datetime import datetime, timedelta, timezone
from typing import Any, List, Optional
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

import re
import subprocess

from app.models.actor import Actor
from app.models.agent import Agent
from app.models.change import Change
from app.models.task_event import TaskEvent
from app.models.pull_request import PullRequest
from app.models.repository import Repository
from app.models.agent_session import AgentSession
from app.models.task import Task
from app.models.user import User
from app.services.authorization_service import AuthorizationService
from app.services.ci_sandbox import CISandbox
from app.services.pull_request_service import PullRequestService
from app.services.notification_service import NotificationService

AGENT_TASK_LEASE_SECONDS = 120

class TaskService:
    AGENT_TASK_LEASE_SECONDS = 120

    def __init__(self, db: Session):
        self.db = db

    def _record_task_event(
        self,
        task: Task,
        event_type: str,
        *,
        actor_id: str | None = None,
        session_id: str | None = None,
        from_status: str | None = None,
        to_status: str | None = None,
        reason: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> TaskEvent:
        event = TaskEvent(
            id=str(uuid4()),
            task_id=task.id,
            actor_id=actor_id,
            session_id=session_id,
            event_type=event_type,
            from_status=from_status,
            to_status=to_status,
            reason=reason,
            metadata_json=json.dumps(
                metadata or {},
                separators=(",", ":"),
                sort_keys=True,
            ),
        )

        self.db.add(event)
        return event

    def _authorize_actor_access(self, actor_id: str, repository: Repository) -> None:
        if repository.visibility == "private" and repository.owner_id != actor_id:
            agent = self.db.scalar(select(Agent).where(Agent.id == actor_id))
            if agent and agent.owner_id == repository.owner_id:
                return

            user = self.db.scalar(select(User).where(User.id == actor_id))
            if user:
                actor = self.db.scalar(select(Actor).where(Actor.id == actor_id, Actor.type == "user"))
                if not actor:
                    actor = Actor(
                        id=actor_id,
                        owner_id=actor_id,
                        type="user",
                        name=user.username,
                        capabilities='["repository.read", "repository.write"]',
                    )
                    self.db.add(actor)
                    self.db.flush()
            else:
                actor = self.db.scalar(select(Actor).where(Actor.id == actor_id))

            if not actor:
                raise PermissionError("Actor not found")

            auth_res = AuthorizationService.check(actor, repository, AuthorizationService.READ, db=self.db)
            if not auth_res.allowed:
                raise PermissionError("Actor does not have access to this private repository")

    def create_task(
        self,
        repository_id: str,
        created_by_id: str,
        title: str,
        description: Optional[str] = None,
        priority: str = Task.PRIORITY_MEDIUM,
        task_type: str = Task.TYPE_FEATURE,
    ) -> Task:
        repo = self.db.scalar(select(Repository).where(Repository.id == repository_id, Repository.deleted_at.is_(None)))
        if not repo:
            raise ValueError("Repository not found or deleted")

        self._authorize_actor_access(created_by_id, repo)

        if not title or len(title.strip()) == 0:
            raise ValueError("Task title cannot be empty")
        if len(title) > 255:
            raise ValueError("Task title exceeds maximum length of 255 characters")

        if priority not in {Task.PRIORITY_LOW, Task.PRIORITY_MEDIUM, Task.PRIORITY_HIGH, Task.PRIORITY_CRITICAL}:
            raise ValueError("Invalid task priority")

        if task_type not in {Task.TYPE_FEATURE, Task.TYPE_BUGFIX, Task.TYPE_REFACTOR, Task.TYPE_SECURITY, Task.TYPE_DOCUMENTATION}:
            raise ValueError("Invalid task type")

        task = Task(
            id=str(uuid4()),
            repository_id=repo.id,
            created_by=created_by_id,
            title=title,
            description=description,
            status=Task.STATUS_OPEN,
            priority=priority,
            task_type=task_type,
            source="user",
        )
        self.db.add(task)

        self._record_task_event(
            task,
            TaskEvent.EVENT_CREATED,
            actor_id=created_by_id,
            to_status=Task.STATUS_OPEN,
            metadata={
                "task_id": task.id,
                "repository_id": repo.id,
                "title": title[:50],
            },
        )
        self.db.flush()

        return task

    def get_task(self, task_id: str, actor_id: str) -> Task:
        task = self.db.scalar(select(Task).where(Task.id == task_id))
        if not task:
            raise ValueError("Task not found")

        repo = self.db.scalar(select(Repository).where(Repository.id == task.repository_id))
        if repo:
            self._authorize_actor_access(actor_id, repo)

        return task

    def list_tasks_for_repository(self, repository_id: str, actor_id: str) -> List[Task]:
        repo = self.db.scalar(select(Repository).where(Repository.id == repository_id))
        if not repo:
            raise ValueError("Repository not found")

        self._authorize_actor_access(actor_id, repo)

        return self.db.scalars(
            select(Task)
            .where(Task.repository_id == repository_id)
            .order_by(Task.created_at.desc())
        ).all()

    def assign_task(
        self,
        task_id: str,
        actor_id: str,
        assigned_user_id: Optional[str] = None,
        assigned_agent_id: Optional[str] = None,
    ) -> Task:
        task = self.db.scalar(select(Task).where(Task.id == task_id).with_for_update())
        if not task:
            raise ValueError("Task not found")

        repo = self.db.scalar(select(Repository).where(Repository.id == task.repository_id))
        if repo:
            self._authorize_actor_access(actor_id, repo)

        if task.status in {Task.STATUS_COMPLETED, Task.STATUS_CANCELLED}:
            raise ValueError(f"Cannot assign task in terminal status '{task.status}'")

        if assigned_user_id and assigned_agent_id:
            raise ValueError("Cannot assign task to both user and agent simultaneously")

        if not assigned_user_id and not assigned_agent_id:
            raise ValueError("Must assign task to either a user or an agent")

        if assigned_user_id:
            user = self.db.scalar(select(User).where(User.id == assigned_user_id))
            if not user:
                raise ValueError("Assigned user not found")
            task.assigned_user_id = assigned_user_id
            task.assigned_agent_id = None

        if assigned_agent_id:
            agent = self.db.scalar(select(Agent).where(Agent.id == assigned_agent_id))
            if not agent:
                raise ValueError("Assigned agent not found")
            if not agent.is_active or agent.status != "active":
                raise ValueError("Assigned agent is inactive or revoked")
            if agent.owner_id != repo.owner_id:
                raise PermissionError("Agent does not belong to repository owner scope")

            task.assigned_agent_id = assigned_agent_id
            task.assigned_user_id = None

        previous_status = task.status

        task.status = Task.STATUS_ASSIGNED
        task.updated_at = datetime.now(timezone.utc)

        self._record_task_event(
            task,
            TaskEvent.EVENT_ASSIGNED,
            actor_id=actor_id,
            from_status=previous_status,
            to_status=Task.STATUS_ASSIGNED,
            metadata={
                "task_id": task.id,
                "assigned_agent_id": assigned_agent_id,
                "assigned_user_id": assigned_user_id,
            },
        )
        self.db.flush()

        if assigned_user_id:
            NotificationService.create_notification(
                db=self.db,
                user_id=assigned_user_id,
                title=f"You've been assigned: {task.title}",
                message=f"Task '{task.title[:50]}' was assigned to you.",
                type="task",
                link=f"/repositories/{repo.slug}/tasks/{task.id}"
            )

        return task

    def start_task(self, task_id: str, actor_id: str) -> Task:
        task = self.db.scalar(select(Task).where(Task.id == task_id).with_for_update())
        if not task:
            raise ValueError("Task not found")

        repo = self.db.scalar(select(Repository).where(Repository.id == task.repository_id))
        if repo:
            self._authorize_actor_access(actor_id, repo)

        if task.status not in {Task.STATUS_OPEN, Task.STATUS_ASSIGNED, Task.STATUS_BLOCKED}:
            raise ValueError(f"Cannot start task in status '{task.status}'")

        previous_status = task.status

        task.status = Task.STATUS_IN_PROGRESS
        now = datetime.now(timezone.utc)
        if not task.started_at:
            task.started_at = now
        task.updated_at = now

        self._record_task_event(
    task,
    TaskEvent.EVENT_STARTED,
    actor_id=actor_id,
    from_status=previous_status,
    to_status=Task.STATUS_IN_PROGRESS,
    metadata={
        "task_id": task.id,
    },
)
        self.db.flush()

        return task
    
    @staticmethod
    def _normalize_datetime(value: datetime | None) -> datetime | None:
        if value is None:
            return None

        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)

        return value.astimezone(timezone.utc)

    def _get_task_for_update(self, task_id: str) -> Task:
        task = self.db.scalar(
            select(Task)
            .where(Task.id == task_id)
            .with_for_update()
        )

        if not task:
            raise ValueError("Task not found")

        return task

    def _validate_agent_session_for_task(
        self,
        task: Task,
        session: AgentSession,
    ) -> None:
        if task.assigned_agent_id != session.agent_id:
            raise PermissionError(
                "Task is not assigned to this agent"
            )

        if session.status != "active":
            raise PermissionError(
                "Agent session is not active"
            )

        now = datetime.now(timezone.utc)

        expires_at = self._normalize_datetime(
            session.expires_at
        )

        last_seen_at = self._normalize_datetime(
            session.last_seen_at
        )

        if expires_at is None or expires_at <= now:
            raise PermissionError(
                "Agent session expired"
            )

        if (
            last_seen_at is not None
            and (
                now - last_seen_at
            ).total_seconds()
            > 120
        ):
            raise PermissionError(
                "Agent session expired due to inactivity"
            )

        agent = self.db.scalar(
            select(Agent).where(
                Agent.id == session.agent_id,
                Agent.is_active.is_(True),
                Agent.status == "active",
            )
        )

        if agent is None:
            raise PermissionError(
                "Agent is inactive or revoked"
            )

    def _lease_is_active(self, task: Task) -> bool:
        if not task.claimed_by_session_id:
            return False

        expires_at = self._normalize_datetime(
            task.lease_expires_at
        )

        if expires_at is None:
            return False

        return expires_at > datetime.now(timezone.utc)

    def claim_agent_task(
        self,
        task_id: str,
        session: AgentSession,
    ) -> Task:
        task = self._get_task_for_update(task_id)

        self._validate_agent_session_for_task(
            task,
            session,
        )

        now = datetime.now(timezone.utc)
        previous_status = task.status
        # Existing active lease.
        if self._lease_is_active(task):
            if (
                task.claimed_by_session_id
                == session.id
            ):
                return task

            raise PermissionError(
                "Task is already claimed by another session"
            )

        # Reclaim expired lease.
        task.claimed_by_session_id = session.id
        task.lease_expires_at = (
            now
            + timedelta(
                seconds=self.AGENT_TASK_LEASE_SECONDS
            )
        )

        task.status = Task.STATUS_IN_PROGRESS
        self._record_task_event(
    task,
    TaskEvent.EVENT_CLAIMED,
    actor_id=session.agent_id,
    session_id=session.id,
    from_status=previous_status,
    to_status=Task.STATUS_IN_PROGRESS,
    metadata={
        "task_id": task.id,
        "session_id": session.id,
        "lease_expires_at": task.lease_expires_at.isoformat(),
    },
)
        if task.started_at is None:
            task.started_at = now

        task.updated_at = now

        self.db.flush()

        return task

    def heartbeat_agent_task(
    self,
        task_id: str,
        session: AgentSession,
    ) -> Task:
        task = self._get_task_for_update(task_id)

        self._validate_agent_session_for_task(
            task,
            session,
        )

        if (
            task.claimed_by_session_id
            != session.id
        ):
            raise PermissionError(
                "Task is not claimed by this session"
            )

        now = datetime.now(timezone.utc)

        if not self._lease_is_active(task):
            task.claimed_by_session_id = None
            task.lease_expires_at = None

            if task.status == Task.STATUS_IN_PROGRESS:
                task.status = Task.STATUS_ASSIGNED

            task.updated_at = now

            self.db.flush()

            raise ValueError(
                "Task lease expired"
            )

        task.lease_expires_at = (
            now
            + timedelta(
                seconds=self.AGENT_TASK_LEASE_SECONDS
            )
        )

        task.updated_at = now
        self._record_task_event(
            task,
            TaskEvent.EVENT_HEARTBEAT,
            actor_id=session.agent_id,
            session_id=session.id,
            metadata={
                "task_id": task.id,
                "session_id": session.id,
                "lease_expires_at": task.lease_expires_at.isoformat(),
            },
        )

        self.db.flush()

        return task
    
    def release_agent_task(
        self,
        task_id: str,
        session: AgentSession,
    ) -> Task:
        task = self._get_task_for_update(task_id)

        self._validate_agent_session_for_task(
            task,
            session,
        )

        if (
            task.claimed_by_session_id
            != session.id
        ):
            raise PermissionError(
                "Task is not claimed by this session"
            )

        task.claimed_by_session_id = None
        task.lease_expires_at = None
        previous_status = task.status

        if task.status == Task.STATUS_IN_PROGRESS:
            task.status = Task.STATUS_ASSIGNED

        task.updated_at = datetime.now(timezone.utc)
        self._record_task_event(
    task,
    TaskEvent.EVENT_RELEASED,
    actor_id=session.agent_id,
    session_id=session.id,
    from_status=previous_status,
    to_status=task.status,
    reason="Agent released the task",
    metadata={
        "task_id": task.id,
        "session_id": session.id,
    },
)

        self.db.flush()

        return task

    def _validate_agent_task_lease(
    self,
    task: Task,
    session: AgentSession,
) -> None:
        self._validate_agent_session_for_task(
        task,
        session,
        )

        if task.claimed_by_session_id != session.id:
            raise PermissionError(
                "Task is not claimed by this session"
            )

        if self._lease_is_active(task):
            return

        previous_status = task.status

        task.claimed_by_session_id = None
        task.lease_expires_at = None

        if task.status == Task.STATUS_IN_PROGRESS:
            task.status = Task.STATUS_ASSIGNED

        task.updated_at = datetime.now(timezone.utc)

        self._record_task_event(
        task,
        TaskEvent.EVENT_LEASE_EXPIRED,
        actor_id=session.agent_id,
        session_id=session.id,
        from_status=previous_status,
        to_status=task.status,
        reason="Task lease expired",
        metadata={
            "task_id": task.id,
            "session_id": session.id,
        },
    )

        self.db.flush()

        raise ValueError(
            "Task lease expired"
        )

    def execute_agent_task(
        self,
        task_id: str,
        actor_id: str,
        session: AgentSession | None = None,
    ) -> Task:
        task = self._get_task_for_update(task_id)

        # Agent task execution is lease-protected. Keep the existing
        # validation semantics so expired/stale sessions return the
        # expected 403/409 responses.
        if session is not None:
            self._validate_agent_task_lease(
                task,
                session,
            )

        repo = self.db.scalar(
            select(Repository).where(
                Repository.id == task.repository_id
            )
        )

        if not repo:
            raise ValueError("Repository not found")

        self._authorize_actor_access(
            actor_id,
            repo,
        )

        if not task.assigned_agent_id:
            raise ValueError(
                "Task is not assigned to an agent"
            )

        agent = self.db.scalar(
            select(Agent).where(
                Agent.id == task.assigned_agent_id
            )
        )

        if (
            not agent
            or not agent.is_active
            or agent.status != "active"
        ):
            raise ValueError(
                "Assigned agent is inactive or revoked"
            )

        if task.status not in {
            Task.STATUS_ASSIGNED,
            Task.STATUS_IN_PROGRESS,
            Task.STATUS_OPEN,
        }:
            raise ValueError(
                f"Cannot execute agent task in status "
                f"'{task.status}'"
            )

        previous_status = task.status
        now = datetime.now(timezone.utc)

        # Task execution is intentionally separate from CI/container
        # execution. A valid agent lease must not fail merely because
        # the local CI/Docker runtime is unavailable.
        task.status = Task.STATUS_IN_PROGRESS

        if not task.started_at:
            task.started_at = now

        # Capture the real repository HEAD when storage is available.
        # Never fabricate Git SHAs.
        base_commit = None

        try:
            repository_path = (
                self._repository_storage_path(repo)
                if hasattr(self, "_repository_storage_path")
                else None
            )

            if repository_path:
                result = subprocess.run(
                    [
                        "git",
                        "--git-dir",
                        str(repository_path),
                        "rev-parse",
                        "--verify",
                        f"{repo.default_branch}^{{commit}}",
                    ],
                    capture_output=True,
                    text=True,
                    check=False,
                )

                if result.returncode == 0:
                    candidate = result.stdout.strip()

                    if re.fullmatch(
                        r"[0-9a-fA-F]{40}",
                        candidate,
                    ):
                        base_commit = candidate
        except Exception:
            # Repository storage availability should not turn a valid
            # task execution into a 500.
            base_commit = None

        # Create exactly one resulting Change. The resulting commit stays
        # NULL until the agent performs a real Git commit.
        if not task.resulting_change_id:
            agent_actor = self.db.scalar(
                select(Actor).where(
                    Actor.id == agent.id
                )
            )

            if not agent_actor:
                agent_actor = Actor(
                    id=agent.id,
                    owner_id=agent.owner_id,
                    type="agent",
                    name=agent.name,
                    capabilities=(
                        '["repository.read",'
                        '"repository.write",'
                        '"change.create"]'
                    ),
                )
                self.db.add(agent_actor)
                self.db.flush()

            change = Change(
                id=str(uuid4()),
                repository_id=repo.id,
                actor_id=agent_actor.id,
                intent=(
                    f"Resulting Change for Task: "
                    f"{task.title}"
                ),
                risk_level="low",
                base_commit=base_commit,
                resulting_commit=None,
                operation_key=(uuid4().hex * 2)[:64],
                status="proposed",
            )

            self.db.add(change)
            self.db.flush()

            task.resulting_change_id = change.id

        self._record_task_event(
            task,
            TaskEvent.EVENT_STARTED,
            actor_id=actor_id,
            session_id=(
                session.id
                if session is not None
                else None
            ),
            from_status=previous_status,
            to_status=Task.STATUS_IN_PROGRESS,
            metadata={
                "task_id": task.id,
                "change_id": task.resulting_change_id,
                "base_commit": base_commit,
                "execution": "started",
            },
        )

        self._record_task_event(
            task,
            TaskEvent.EVENT_CHANGE_CREATED,
            actor_id=actor_id,
            session_id=(
                session.id
                if session is not None
                else None
            ),
            metadata={
                "task_id": task.id,
                "change_id": task.resulting_change_id,
            },
        )

        task.updated_at = now
        self.db.flush()

        return task

    def create_pull_request_for_task(self, task_id: str, actor_id: str, title: str, target_branch: str = "main") -> Task:
        task = self.db.scalar(select(Task).where(Task.id == task_id).with_for_update())
        if not task:
            raise ValueError("Task not found")

        repo = self.db.scalar(select(Repository).where(Repository.id == task.repository_id))
        if repo:
            self._authorize_actor_access(actor_id, repo)

        if not task.resulting_change_id:
            raise ValueError("Task does not have a resulting Change yet")

        if task.resulting_pull_request_id:
            return task

        pr_svc = PullRequestService(self.db)
        pr = pr_svc.create_pull_request(
            repository_id=repo.id,
            author_id=actor_id,
            source_change_id=task.resulting_change_id,
            title=title,
            target_branch=target_branch,
        )

        task.resulting_pull_request_id = pr.id
        task.updated_at = datetime.now(timezone.utc)

        self._record_task_event(
            task,
            TaskEvent.EVENT_PULL_REQUEST_CREATED,
            actor_id=actor_id,
            metadata={
                "task_id": task.id,
                "pull_request_id": pr.id,
                "change_id": task.resulting_change_id,
            },
        )
        self.db.flush()

        return task

    def _complete_locked_task(
        self,
        task: Task,
        actor_id: str,
    ) -> Task:
        if task.status == Task.STATUS_COMPLETED:
            return task

        if task.status == Task.STATUS_CANCELLED:
            raise ValueError(
                f"Cannot complete task in status '{task.status}'"
            )

        if not task.resulting_change_id or not task.resulting_pull_request_id:
            raise ValueError(
                "Task requires both a resulting Change and PullRequest to be completed"
            )

        previous_status = task.status
        now = datetime.now(timezone.utc)

        task.status = Task.STATUS_COMPLETED
        task.completed_at = now
        task.updated_at = now

        if task.claimed_by_session_id:
            session = self.db.scalar(
                select(AgentSession).where(AgentSession.id == task.claimed_by_session_id)
            )
            if session and session.status == "active":
                session.status = "revoked"
                session.revoked_at = now

        self._record_task_event(
            task,
            TaskEvent.EVENT_COMPLETED,
            actor_id=actor_id,
            from_status=previous_status,
            to_status=Task.STATUS_COMPLETED,
            metadata={
                "task_id": task.id,
                "status": Task.STATUS_COMPLETED,
            },
        )

        self.db.flush()

        return task

    def complete_task(self, task_id: str, actor_id: str) -> Task:
        task = self.db.scalar(
            select(Task)
            .where(Task.id == task_id)
            .with_for_update()
        )

        if not task:
            raise ValueError("Task not found")

        repo = self.db.scalar(
            select(Repository).where(
                Repository.id == task.repository_id
            )
        )

        if repo:
            self._authorize_actor_access(actor_id, repo)

        return self._complete_locked_task(
            task,
            actor_id,
        )

    def cancel_task(self, task_id: str, actor_id: str) -> Task:
        task = self.db.scalar(select(Task).where(Task.id == task_id).with_for_update())
        if not task:
            raise ValueError("Task not found")

        repo = self.db.scalar(select(Repository).where(Repository.id == task.repository_id))
        if repo:
            self._authorize_actor_access(actor_id, repo)

        if task.status in {Task.STATUS_COMPLETED, Task.STATUS_CANCELLED}:
            return task

        previous_status = task.status
        task.status = Task.STATUS_CANCELLED
        now = datetime.now(timezone.utc)
        task.cancelled_at = now
        task.updated_at = now

        self._record_task_event(
            task,
            TaskEvent.EVENT_CANCELLED,
            actor_id=actor_id,
            from_status=previous_status,
            to_status=Task.STATUS_CANCELLED,
            metadata={
                "task_id": task.id,
                "status": Task.STATUS_CANCELLED,
            },
        )
        self.db.flush()

        return task