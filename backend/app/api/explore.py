from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.actor import Actor
from app.models.agent import Agent
from app.models.discussion import Discussion
from app.models.repository import Repository
from app.models.social import RepositoryStar
from app.models.task import Task
from app.models.task_event import TaskEvent


router = APIRouter(prefix="/v1/explore", tags=["explore"])


class TrendingRepositoryResponse(BaseModel):
    id: str
    owner: str
    name: str
    description: str | None
    stars: int
    language: str | None = None

    model_config = ConfigDict(from_attributes=True)


@router.get(
    "/trending/repositories",
    response_model=list[TrendingRepositoryResponse],
)
def get_trending_repositories(
    since: str = Query("daily", description="daily, weekly, monthly"),
    db: Session = Depends(get_db),
):
    now = datetime.now(timezone.utc)
    if since == "weekly":
        delta = timedelta(days=7)
    elif since == "monthly":
        delta = timedelta(days=30)
    else:
        delta = timedelta(days=1)

    start_time = now - delta

    trending_query = (
        db.query(
            Repository,
            Actor.name.label("owner_name"),
            func.count(RepositoryStar.actor_id).label("recent_stars"),
        )
        .join(Actor, Repository.owner_id == Actor.id)
        .join(RepositoryStar, Repository.id == RepositoryStar.repository_id)
        .filter(
            Repository.visibility == "public",
            Repository.deleted_at.is_(None),
            RepositoryStar.created_at >= start_time,
        )
        .group_by(Repository.id, Actor.name)
        .order_by(func.count(RepositoryStar.actor_id).desc())
        .limit(25)
    )

    rows = trending_query.all()

    if not rows:
        rows = (
            db.query(Repository, Actor.name.label("owner_name"))
            .join(Actor, Repository.owner_id == Actor.id)
            .filter(
                Repository.visibility == "public",
                Repository.deleted_at.is_(None),
            )
            .order_by(Repository.updated_at.desc())
            .limit(25)
            .all()
        )

    results: list[dict] = []

    for row in rows:
        repo = row[0]
        owner_name = row[1]
        total_stars = db.scalar(
            select(func.count(RepositoryStar.actor_id)).where(
                RepositoryStar.repository_id == repo.id
            )
        ) or 0

        # Do not fabricate a language. If a repository explicitly stores a
        # language in settings, expose it; otherwise return null.
        language = None
        if isinstance(repo.settings, dict):
            value = repo.settings.get("language")
            if isinstance(value, str) and value.strip():
                language = value.strip()

        results.append(
            {
                "id": repo.id,
                "owner": owner_name,
                "name": repo.name,
                "description": repo.description,
                "stars": int(total_stars),
                "language": language,
            }
        )

    return results


class TrendingDiscussionResponse(BaseModel):
    id: str
    title: str
    repo_name: str
    author: str
    comments_count: int


@router.get(
    "/trending/discussions",
    response_model=list[TrendingDiscussionResponse],
)
def get_trending_discussions(
    db: Session = Depends(get_db),
):
    rows = (
        db.query(Discussion, Repository, Actor)
        .join(Repository, Discussion.repository_id == Repository.id)
        .join(Actor, Discussion.author_id == Actor.id)
        .filter(
            Repository.visibility == "public",
            Repository.deleted_at.is_(None),
        )
        .order_by(Discussion.updated_at.desc())
        .limit(10)
        .all()
    )

    results: list[dict] = []

    for discussion, repository, author in rows:
        comments_count = len(discussion.comments or [])
        results.append(
            {
                "id": discussion.id,
                "title": discussion.title,
                "repo_name": repository.name,
                "author": author.name,
                "comments_count": comments_count,
            }
        )

    return results


class TrendingAgentResponse(BaseModel):
    id: str
    name: str
    description: str
    runs: int


@router.get(
    "/trending/agents",
    response_model=list[TrendingAgentResponse],
)
def get_trending_agents(
    db: Session = Depends(get_db),
):
    # Agent identity/access is private by default. Do not expose arbitrary
    # agents on a public Explore page. Only count agents that have actually
    # executed tasks associated with public repositories.
    rows = (
        db.query(
            Agent.id,
            Agent.name,
            Agent.description,
            func.count(TaskEvent.id).label("runs"),
        )
        .join(
            Task,
            Task.assigned_agent_id == Agent.id,
        )
        .join(
            Repository,
            Repository.id == Task.repository_id,
        )
        .join(
            TaskEvent,
            (TaskEvent.task_id == Task.id)
            & (TaskEvent.actor_id == Agent.id)
            & (TaskEvent.event_type == TaskEvent.EVENT_STARTED),
        )
        .filter(
            Agent.is_active.is_(True),
            Agent.status == "active",
            Repository.visibility == "public",
            Repository.deleted_at.is_(None),
        )
        .group_by(
            Agent.id,
            Agent.name,
            Agent.description,
        )
        .order_by(func.count(TaskEvent.id).desc())
        .limit(10)
        .all()
    )

    return [
        {
            "id": agent_id,
            "name": name,
            "description": description or "",
            "runs": int(runs),
        }
        for agent_id, name, description, runs in rows
    ]
