from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.actor import Actor
from app.models.git_push_event import GitPushEvent
from app.models.issue import Issue
from app.models.pull_request import PullRequest
from app.models.repository import Repository
from app.models.social import ActorFollow
from app.models.user import User


router = APIRouter(
    prefix="/v1/profiles",
    tags=["profiles"],
)


class PublicRepository(BaseModel):
    id: str
    name: str
    description: str | None
    visibility: str
    default_branch: str
    updated_at: datetime


class ProfileResponse(BaseModel):
    id: str
    username: str
    type: str

    followers: int
    following: int

    full_name: str | None = None
    bio: str | None = None

    social_links: dict[str, str] = Field(
        default_factory=dict
    )

    created_at: datetime

    repositories: list[PublicRepository] = Field(
        default_factory=list
    )

    public_repository_count: int = 0
    pull_request_count: int = 0
    issue_count: int = 0


class ContributionDay(BaseModel):
    date: str
    count: int


class ProfileContributions(BaseModel):
    total_contributions: int
    days: list[ContributionDay]
    github_synced: bool = False
    github_account: str | None = None


def _find_actor(
    username: str,
    db: Session,
) -> Actor:
    actor = db.scalar(
        select(Actor).where(
            Actor.name == username,
        )
    )

    if actor is None:
        raise HTTPException(
            status_code=404,
            detail="Profile not found",
        )

    return actor


def _public_repositories(
    actor: Actor,
    db: Session,
) -> list[PublicRepository]:
    repositories = db.scalars(
        select(Repository)
        .where(
            Repository.owner_id == actor.id,
            Repository.deleted_at.is_(None),
            Repository.visibility == "public",
        )
        .order_by(
            Repository.updated_at.desc()
        )
        .limit(12)
    ).all()

    return [
        PublicRepository(
            id=repository.id,
            name=repository.name,
            description=repository.description,
            visibility=repository.visibility,
            default_branch=repository.default_branch,
            updated_at=repository.updated_at,
        )
        for repository in repositories
    ]


@router.get(
    "/{username}",
    response_model=ProfileResponse,
)
def get_profile(
    username: str,
    db: Session = Depends(get_db),
):
    actor = _find_actor(
        username,
        db,
    )

    # Actor.owner_id is the corresponding User.id
    # for human profiles.
    user = db.scalar(
        select(User).where(
            User.id == actor.owner_id,
        )
    )

    followers = db.scalar(
        select(func.count())
        .select_from(ActorFollow)
        .where(
            ActorFollow.following_id
            == actor.id
        )
    ) or 0

    following = db.scalar(
        select(func.count())
        .select_from(ActorFollow)
        .where(
            ActorFollow.follower_id
            == actor.id
        )
    ) or 0

    repositories = _public_repositories(
        actor,
        db,
    )

    # PullRequest.author_id references users.id.
    pull_request_count = db.scalar(
        select(func.count())
        .select_from(PullRequest)
        .where(
            PullRequest.author_id
            == actor.owner_id
        )
    ) or 0

    # Issue.author_id references actors.id.
    issue_count = db.scalar(
        select(func.count())
        .select_from(Issue)
        .where(
            Issue.author_id
            == actor.id
        )
    ) or 0

    social_links = {}

    if user is not None:
        social_links = (
            user.social_links
            if isinstance(
                user.social_links,
                dict,
            )
            else {}
        )

    return ProfileResponse(
        id=actor.id,
        username=actor.name,
        type=actor.type,
        followers=followers,
        following=following,
        full_name=(
            user.full_name
            if user is not None
            else None
        ),
        bio=(
            user.bio
            if user is not None
            else None
        ),
        social_links=social_links,
        created_at=actor.created_at,
        repositories=repositories,
        public_repository_count=len(
            repositories
        ),
        pull_request_count=pull_request_count,
        issue_count=issue_count,
    )


@router.get(
    "/{username}/contributions",
    response_model=ProfileContributions,
)
def get_contributions(
    username: str,
    db: Session = Depends(get_db),
):
    actor = _find_actor(
        username,
        db,
    )

    end_date = datetime.now(
        timezone.utc
    )

    start_date = (
        end_date
        - timedelta(days=365)
    )

    contribution_map: dict[
        str,
        int,
    ] = {}

    def add_counts(
        rows,
    ) -> None:
        for day, count in rows:
            if day is None:
                continue

            day_key = (
                day.isoformat()
                if hasattr(
                    day,
                    "isoformat",
                )
                else str(day)
            )

            contribution_map[
                day_key
            ] = (
                contribution_map.get(
                    day_key,
                    0,
                )
                + int(count or 0)
            )

    # Git pushes are attributed to the Actor.
    push_rows = db.execute(
        select(
            func.date(
                GitPushEvent.created_at
            ).label("day"),
            func.count(
                GitPushEvent.id
            ).label("count"),
        )
        .where(
            GitPushEvent.actor_id
            == actor.id,
            GitPushEvent.created_at
            >= start_date,
        )
        .group_by(
            func.date(
                GitPushEvent.created_at
            )
        )
    ).all()

    add_counts(push_rows)

    # Issues are attributed to the Actor.
    issue_rows = db.execute(
        select(
            func.date(
                Issue.created_at
            ).label("day"),
            func.count(
                Issue.id
            ).label("count"),
        )
        .where(
            Issue.author_id
            == actor.id,
            Issue.created_at
            >= start_date,
        )
        .group_by(
            func.date(
                Issue.created_at
            )
        )
    ).all()

    add_counts(issue_rows)

    # Pull requests are attributed to the User.
    pr_rows = db.execute(
        select(
            func.date(
                PullRequest.created_at
            ).label("day"),
            func.count(
                PullRequest.id
            ).label("count"),
        )
        .where(
            PullRequest.author_id
            == actor.owner_id,
            PullRequest.created_at
            >= start_date,
        )
        .group_by(
            func.date(
                PullRequest.created_at
            )
        )
    ).all()

    add_counts(pr_rows)

    # Synchronize external GitHub contributions
    from app.models.github_installation import GitHubInstallation
    from app.services.github_contributions_service import fetch_github_contributions, clean_github_username

    github_synced = False
    github_account: str | None = None

    user = db.scalar(
        select(User).where(
            User.id == actor.owner_id,
        )
    )

    candidate_handles: list[str] = []
    if user:
        gh_inst = db.scalar(
            select(GitHubInstallation).where(
                GitHubInstallation.user_id == user.id,
            )
        )
        if gh_inst and gh_inst.github_account_login:
            candidate_handles.append(gh_inst.github_account_login)

        if isinstance(user.social_links, dict):
            raw_social_gh = user.social_links.get("github")
            if raw_social_gh:
                candidate_handles.append(raw_social_gh)

    if actor.type == "user":
        candidate_handles.append(actor.name)

    for cand in candidate_handles:
        handle = clean_github_username(cand)
        if not handle:
            continue
        gh_map, ok = fetch_github_contributions(handle)
        if ok and gh_map:
            github_synced = True
            github_account = handle
            for day_key, gh_count in gh_map.items():
                if day_key:
                    contribution_map[day_key] = contribution_map.get(day_key, 0) + int(gh_count)
            break

    # Return a complete 365-day series.
    days: list[
        ContributionDay
    ] = []

    current = start_date.date()
    end = end_date.date()

    while current <= end:
        day_key = current.isoformat()

        days.append(
            ContributionDay(
                date=day_key,
                count=contribution_map.get(
                    day_key,
                    0,
                ),
            )
        )

        current += timedelta(
            days=1
        )

    total = sum(
        day.count
        for day in days
    )

    return ProfileContributions(
        total_contributions=total,
        days=days,
        github_synced=github_synced,
        github_account=github_account,
    )