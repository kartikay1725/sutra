from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.db.session import get_db
from app.models.actor import Actor
from app.models.change import Change
from app.models.change_event import ChangeEvent
from app.models.deployment import Deployment
from app.models.discussion import Discussion
from app.models.git_push_event import GitPushEvent
from app.models.organization import Organization, OrganizationMember
from app.models.pull_request import PullRequest
from app.models.repository import Repository
from app.models.task import Task
from app.models.task_event import TaskEvent
from app.models.user import User

router = APIRouter(prefix="/v1/organizations", tags=["audit"])
activity_router = APIRouter(prefix="/v1", tags=["activity"])


class AuditLogEntry(BaseModel):
    id: str
    timestamp: datetime
    actor_id: str | None
    actor_name: str
    action: str
    resource_type: str
    resource_name: str
    ip_address: str | None = None
    metadata_json: dict

    model_config = ConfigDict(from_attributes=True)


def _require_org_auditor(org_id: str, current_user: User, db: Session) -> Organization:
    org = db.query(Organization).filter(Organization.id == org_id).first()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    membership = (
        db.query(OrganizationMember)
        .filter(
            OrganizationMember.organization_id == org.id,
            OrganizationMember.user_id == current_user.id,
        )
        .first()
    )
    if not membership or membership.role not in {"owner", "admin"}:
        raise HTTPException(status_code=403, detail="Organization audit access denied")
    return org


def _org_repository_ids(db: Session, org: Organization) -> list[str]:
    return [row[0] for row in db.query(Repository.id).filter(Repository.owner_id == org.id).all()]


def _parse_metadata(raw: str | None) -> dict:
    if not raw:
        return {}
    try:
        value = json.loads(raw)
        return value if isinstance(value, dict) else {}
    except (TypeError, ValueError):
        return {}


def _actor_names(db: Session, actor_ids: set[str]) -> dict[str, str]:
    if not actor_ids:
        return {}
    rows = db.query(Actor.id, Actor.name).filter(Actor.id.in_(actor_ids)).all()
    return {row[0]: row[1] for row in rows}


def _build_entries_for_repo_ids(db: Session, repo_ids: list[str], limit: int) -> list[AuditLogEntry]:
    if not repo_ids:
        return []

    entries: list[AuditLogEntry] = []
    actor_ids: set[str] = set()

    # 1. Change Events
    for event, change, repo in (
        db.query(ChangeEvent, Change, Repository)
        .join(Change, ChangeEvent.change_id == Change.id)
        .join(Repository, Change.repository_id == Repository.id)
        .filter(Repository.id.in_(repo_ids))
        .order_by(ChangeEvent.created_at.desc())
        .limit(limit).all()
    ):
        if event.actor_id:
            actor_ids.add(event.actor_id)
        entries.append(AuditLogEntry(
            id=f"change-event:{event.id}",
            timestamp=event.created_at,
            actor_id=event.actor_id,
            actor_name="Unknown actor",
            action=event.event_type,
            resource_type="change",
            resource_name=f"{repo.name}:{change.id[:8]}",
            metadata_json={
                "from_status": event.from_status,
                "to_status": event.to_status,
                "reason": event.reason,
                **_parse_metadata(event.metadata_json),
            },
        ))

    # 2. Task Events
    for event, task, repo in (
        db.query(TaskEvent, Task, Repository)
        .join(Task, TaskEvent.task_id == Task.id)
        .join(Repository, Task.repository_id == Repository.id)
        .filter(Repository.id.in_(repo_ids))
        .order_by(TaskEvent.created_at.desc())
        .limit(limit).all()
    ):
        if event.actor_id:
            actor_ids.add(event.actor_id)
        entries.append(AuditLogEntry(
            id=f"task-event:{event.id}",
            timestamp=event.created_at,
            actor_id=event.actor_id,
            actor_name="Unknown actor",
            action=event.event_type,
            resource_type="task",
            resource_name=f"{repo.name}:{task.title[:30]}",
            metadata_json={
                "task_id": task.id,
                "from_status": event.from_status,
                "to_status": event.to_status,
                "reason": event.reason,
                **_parse_metadata(event.metadata_json),
            },
        ))

    # 3. Discussions
    for d, repo in (
        db.query(Discussion, Repository)
        .join(Repository, Discussion.repository_id == Repository.id)
        .filter(Repository.id.in_(repo_ids))
        .order_by(Discussion.created_at.desc())
        .limit(limit).all()
    ):
        actor_ids.add(d.author_id)
        entries.append(AuditLogEntry(
            id=f"discussion:{d.id}",
            timestamp=d.created_at,
            actor_id=d.author_id,
            actor_name="Unknown actor",
            action="discussion.created",
            resource_type="discussion",
            resource_name=f"{repo.name}:{d.title[:30]}",
            metadata_json={"discussion_id": d.id, "category": d.category},
        ))

    # 4. Git Push Events
    for event, repo in (
        db.query(GitPushEvent, Repository)
        .join(Repository, GitPushEvent.repository_id == Repository.id)
        .filter(Repository.id.in_(repo_ids))
        .order_by(GitPushEvent.created_at.desc())
        .limit(limit).all()
    ):
        actor_ids.add(event.actor_id)
        entries.append(AuditLogEntry(
            id=f"git-push:{event.id}",
            timestamp=event.created_at,
            actor_id=event.actor_id,
            actor_name="Unknown actor",
            action="git.push",
            resource_type="repository",
            resource_name=repo.name,
            metadata_json={"status": event.status, "attempts": event.attempts},
        ))

    # 5. Pull Requests
    for pr, repo in (
        db.query(PullRequest, Repository)
        .join(Repository, PullRequest.repository_id == Repository.id)
        .filter(Repository.id.in_(repo_ids))
        .order_by(PullRequest.updated_at.desc())
        .limit(limit).all()
    ):
        actor_ids.add(pr.author_id)
        entries.append(AuditLogEntry(
            id=f"pull-request:{pr.id}",
            timestamp=pr.updated_at,
            actor_id=pr.author_id,
            actor_name="Unknown actor",
            action=f"pull_request.{pr.status}",
            resource_type="pull_request",
            resource_name=f"{repo.name}:{pr.title or pr.id[:8]}",
            metadata_json={
                "pull_request_id": pr.id,
                "source_change_id": pr.source_change_id,
                "target_branch": pr.target_branch,
            },
        ))

    names = _actor_names(db, actor_ids)
    for entry in entries:
        entry.actor_name = names.get(entry.actor_id or "", "Unknown actor")

    def _ts(dt: datetime) -> datetime:
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt

    entries.sort(key=lambda entry: _ts(entry.timestamp), reverse=True)
    return entries[:limit]


def _build_entries(db: Session, org: Organization, limit: int) -> list[AuditLogEntry]:
    repo_ids = _org_repository_ids(db, org)
    return _build_entries_for_repo_ids(db, repo_ids, limit)


@router.get("/{org_id}/audit-logs", response_model=List[AuditLogEntry])
def get_audit_logs(
    org_id: str,
    limit: int = Query(50, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    org = _require_org_auditor(org_id, current_user, db)
    return _build_entries(db, org, limit)


@activity_router.get("/activity", response_model=List[AuditLogEntry])
@activity_router.get("/audit-logs", response_model=List[AuditLogEntry])
def get_user_activity(
    limit: int = Query(50, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    repo_ids = [
        r[0]
        for r in db.query(Repository.id)
        .filter((Repository.owner_id == current_user.id) | (Repository.visibility == "public"))
        .all()
    ]
    return _build_entries_for_repo_ids(db, repo_ids, limit)


@activity_router.get("/repositories/{owner_name}/{repo_name}/activity", response_model=List[AuditLogEntry])
def get_repository_activity(
    owner_name: str,
    repo_name: str,
    limit: int = Query(50, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    repo = db.scalar(
        select(Repository)
        .join(Actor, Actor.id == Repository.owner_id)
        .where(
            Actor.name == owner_name,
            (Repository.name == repo_name) | (Repository.slug == repo_name.lower()),
            Repository.deleted_at.is_(None),
        )
    )
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")
    if repo.visibility == "private" and repo.owner_id != current_user.id:
        raise HTTPException(status_code=404, detail="Repository not found")

    return _build_entries_for_repo_ids(db, [repo.id], limit)

