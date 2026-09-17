from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.db.session import get_db
from app.models.actor import Actor
from app.models.change import Change
from app.models.ci_job import CIJob
from app.models.deployment import Deployment
from app.models.pull_request import PullRequest
from app.models.repository import Repository
from app.models.user import User


router = APIRouter(
    prefix="/v1/repositories/{owner}/{repo}/insights",
    tags=["insights"],
)


class InsightsResponse(BaseModel):
    deployments_per_week: float
    lead_time_minutes: int
    ci_pass_rate: float
    agent_changes_percent: int
    human_changes_percent: int
    agent_lead_time_minutes: int
    human_lead_time_minutes: int
    actionable_signal: str
    actionable_signal_details: str


def _repository_for_user(
    db: Session,
    owner: str,
    repo: str,
    current_user: User,
) -> Repository:
    repository = db.scalar(
        select(Repository)
        .join(User, Repository.owner_id == User.id)
        .where(
            (User.username == owner) | (Repository.provider_owner == owner),
            (Repository.name == repo) | (Repository.slug == repo.lower()),
            Repository.deleted_at.is_(None),
        )
    )

    if repository is None:
        repository = db.scalar(
            select(Repository)
            .join(Actor, Repository.owner_id == Actor.id)
            .where(
                (Actor.name == owner) | (Repository.provider_owner == owner),
                (Repository.name == repo) | (Repository.slug == repo.lower()),
                Repository.deleted_at.is_(None),
            )
        )

    if repository is None:
        candidates = db.scalars(
            select(Repository).where(
                (Repository.name == repo) | (Repository.slug == repo.lower()),
                Repository.deleted_at.is_(None),
            )
        ).all()
        for c in candidates:
            if c.owner_id == current_user.id or c.visibility == "public":
                repository = c
                break

    if repository is None:
        raise HTTPException(
            status_code=404,
            detail="Repository not found",
        )

    if repository.owner_id != current_user.id and repository.visibility != "public":
        raise HTTPException(
            status_code=404,
            detail="Repository not found",
        )

    return repository


def _avg_lead_time_minutes(values: list[timedelta]) -> int:
    if not values:
        return 0
    return round(
        sum(value.total_seconds() for value in values)
        / 60
        / len(values)
    )


@router.get("", response_model=InsightsResponse)
def get_insights(
    owner: str,
    repo: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    repository = _repository_for_user(
        db,
        owner,
        repo,
        current_user,
    )

    now = datetime.now(timezone.utc)
    window_start = now - timedelta(days=30)
    week_start = now - timedelta(days=7)
    previous_week_start = now - timedelta(days=14)

    # ------------------------------------------------------------------
    # Deployment frequency
    # ------------------------------------------------------------------
    successful_deployments = db.scalar(
        select(func.count(Deployment.id)).where(
            Deployment.repository_id == repository.id,
            Deployment.status == Deployment.STATUS_SUCCESS,
            Deployment.created_at >= window_start,
            Deployment.created_at <= now,
        )
    ) or 0

    deployments_per_week = round(
        (successful_deployments / 30) * 7,
        1,
    )

    # ------------------------------------------------------------------
    # CI pass rate
    # ------------------------------------------------------------------
    terminal_ci = db.scalars(
        select(CIJob).where(
            CIJob.repository_id == repository.id,
            CIJob.created_at >= window_start,
            CIJob.created_at <= now,
            CIJob.status.in_(
                [
                    CIJob.STATUS_PASSED,
                    CIJob.STATUS_FAILED,
                ]
            ),
        )
    ).all()

    passed_ci = sum(
        job.status == CIJob.STATUS_PASSED
        for job in terminal_ci
    )
    ci_pass_rate = round(
        (passed_ci / len(terminal_ci)) * 100,
        1,
    ) if terminal_ci else 0.0

    # ------------------------------------------------------------------
    # Merged changes + lead time + agent/human split
    # ------------------------------------------------------------------
    merged_rows = db.execute(
        select(Change, PullRequest, Actor)
        .join(
            PullRequest,
            PullRequest.source_change_id == Change.id,
        )
        .join(
            Actor,
            Actor.id == Change.actor_id,
        )
        .where(
            Change.repository_id == repository.id,
            PullRequest.status == PullRequest.STATUS_MERGED,
            PullRequest.merged_at.is_not(None),
            PullRequest.merged_at >= window_start,
            PullRequest.merged_at <= now,
        )
    ).all()

    agent_lead_times: list[timedelta] = []
    human_lead_times: list[timedelta] = []
    agent_changes = 0
    human_changes = 0
    all_lead_times: list[timedelta] = []

    for change, pull_request, actor in merged_rows:
        if not pull_request.merged_at:
            continue

        created_at = change.created_at
        merged_at = pull_request.merged_at
        if not created_at or not merged_at:
            continue

        lead_time = merged_at - created_at
        if lead_time.total_seconds() < 0:
            # Guard against inconsistent historical timestamps.
            continue

        all_lead_times.append(lead_time)

        if actor.type == "agent":
            agent_changes += 1
            agent_lead_times.append(lead_time)
        else:
            human_changes += 1
            human_lead_times.append(lead_time)

    total_changes = agent_changes + human_changes

    agent_changes_percent = round(
        (agent_changes / total_changes) * 100
    ) if total_changes else 0
    human_changes_percent = 100 - agent_changes_percent if total_changes else 0

    # ------------------------------------------------------------------
    # Actionable signal from actual CI/deployment history
    # ------------------------------------------------------------------
    current_week_failed_ci = db.scalar(
        select(func.count(CIJob.id)).where(
            CIJob.repository_id == repository.id,
            CIJob.status == CIJob.STATUS_FAILED,
            CIJob.created_at >= week_start,
            CIJob.created_at <= now,
        )
    ) or 0

    previous_week_failed_ci = db.scalar(
        select(func.count(CIJob.id)).where(
            CIJob.repository_id == repository.id,
            CIJob.status == CIJob.STATUS_FAILED,
            CIJob.created_at >= previous_week_start,
            CIJob.created_at < week_start,
        )
    ) or 0

    current_week_failed_deployments = db.scalar(
        select(func.count(Deployment.id)).where(
            Deployment.repository_id == repository.id,
            Deployment.status.in_(
                [
                    Deployment.STATUS_FAILED,
                    Deployment.STATUS_ROLLED_BACK,
                ]
            ),
            Deployment.created_at >= week_start,
            Deployment.created_at <= now,
        )
    ) or 0

    actionable_signal = "No actionable signal yet."
    actionable_signal_details = (
        "SUTRA does not have enough recent repository activity to identify a meaningful trend."
    )

    if current_week_failed_ci > previous_week_failed_ci:
        delta = current_week_failed_ci - previous_week_failed_ci
        actionable_signal = "CI failures increased this week."
        actionable_signal_details = (
            f"{current_week_failed_ci} CI failures occurred in the last 7 days, "
            f"up by {delta} from the previous 7-day period."
        )
    elif current_week_failed_deployments > 0:
        actionable_signal = "Recent deployments need attention."
        actionable_signal_details = (
            f"{current_week_failed_deployments} deployment(s) failed or were rolled back "
            "in the last 7 days."
        )
    elif all_lead_times and len(all_lead_times) >= 2:
        actionable_signal = "Lead time is measurable from real merged changes."
        actionable_signal_details = (
            f"Median-style average lead time is { _avg_lead_time_minutes(all_lead_times) } minutes "
            f"across {len(all_lead_times)} merged change(s) in the last 30 days."
        )

    return InsightsResponse(
        deployments_per_week=deployments_per_week,
        lead_time_minutes=_avg_lead_time_minutes(all_lead_times),
        ci_pass_rate=ci_pass_rate,
        agent_changes_percent=agent_changes_percent,
        human_changes_percent=human_changes_percent,
        agent_lead_time_minutes=_avg_lead_time_minutes(agent_lead_times),
        human_lead_time_minutes=_avg_lead_time_minutes(human_lead_times),
        actionable_signal=actionable_signal,
        actionable_signal_details=actionable_signal_details,
    )


global_router = APIRouter(
    prefix="/v1/insights",
    tags=["insights"],
)


@global_router.get("", response_model=InsightsResponse)
def get_global_insights(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Aggregate engineering insights across all repositories owned by the current user."""
    repo_ids = db.scalars(
        select(Repository.id).where(
            Repository.owner_id == current_user.id,
            Repository.deleted_at.is_(None),
        )
    ).all()

    now = datetime.now(timezone.utc)
    window_start = now - timedelta(days=30)
    week_start = now - timedelta(days=7)
    previous_week_start = now - timedelta(days=14)

    if not repo_ids:
        return InsightsResponse(
            deployments_per_week=0.0,
            lead_time_minutes=0,
            ci_pass_rate=0.0,
            agent_changes_percent=0,
            human_changes_percent=0,
            agent_lead_time_minutes=0,
            human_lead_time_minutes=0,
            actionable_signal="No repositories configured yet.",
            actionable_signal_details="Create or import repositories to begin tracking engineering signals.",
        )

    # Deployment frequency
    successful_deployments = db.scalar(
        select(func.count(Deployment.id)).where(
            Deployment.repository_id.in_(repo_ids),
            Deployment.status == Deployment.STATUS_SUCCESS,
            Deployment.created_at >= window_start,
            Deployment.created_at <= now,
        )
    ) or 0

    deployments_per_week = round((successful_deployments / 30) * 7, 1)

    # CI pass rate
    terminal_ci = db.scalars(
        select(CIJob).where(
            CIJob.repository_id.in_(repo_ids),
            CIJob.created_at >= window_start,
            CIJob.created_at <= now,
            CIJob.status.in_([CIJob.STATUS_PASSED, CIJob.STATUS_FAILED]),
        )
    ).all()

    passed_ci = sum(job.status == CIJob.STATUS_PASSED for job in terminal_ci)
    ci_pass_rate = round((passed_ci / len(terminal_ci)) * 100, 1) if terminal_ci else 0.0

    # Merged rows + lead time
    merged_rows = db.execute(
        select(Change, PullRequest, Actor)
        .join(PullRequest, PullRequest.source_change_id == Change.id)
        .join(Actor, Actor.id == Change.actor_id)
        .where(
            Change.repository_id.in_(repo_ids),
            PullRequest.status == PullRequest.STATUS_MERGED,
            PullRequest.merged_at.is_not(None),
            PullRequest.merged_at >= window_start,
            PullRequest.merged_at <= now,
        )
    ).all()

    agent_lead_times: list[timedelta] = []
    human_lead_times: list[timedelta] = []
    agent_changes = 0
    human_changes = 0
    all_lead_times: list[timedelta] = []

    for change, pull_request, actor in merged_rows:
        if not pull_request.merged_at or not change.created_at:
            continue
        lead_time = pull_request.merged_at - change.created_at
        if lead_time.total_seconds() < 0:
            continue
        all_lead_times.append(lead_time)
        if actor.type == "agent":
            agent_changes += 1
            agent_lead_times.append(lead_time)
        else:
            human_changes += 1
            human_lead_times.append(lead_time)

    total_changes = agent_changes + human_changes
    agent_changes_percent = round((agent_changes / total_changes) * 100) if total_changes else 0
    human_changes_percent = 100 - agent_changes_percent if total_changes else 0

    # Actionable signals
    current_week_failed_ci = db.scalar(
        select(func.count(CIJob.id)).where(
            CIJob.repository_id.in_(repo_ids),
            CIJob.status == CIJob.STATUS_FAILED,
            CIJob.created_at >= week_start,
            CIJob.created_at <= now,
        )
    ) or 0

    previous_week_failed_ci = db.scalar(
        select(func.count(CIJob.id)).where(
            CIJob.repository_id.in_(repo_ids),
            CIJob.status == CIJob.STATUS_FAILED,
            CIJob.created_at >= previous_week_start,
            CIJob.created_at < week_start,
        )
    ) or 0

    current_week_failed_deployments = db.scalar(
        select(func.count(Deployment.id)).where(
            Deployment.repository_id.in_(repo_ids),
            Deployment.status.in_([Deployment.STATUS_FAILED, Deployment.STATUS_ROLLED_BACK]),
            Deployment.created_at >= week_start,
            Deployment.created_at <= now,
        )
    ) or 0

    actionable_signal = "No actionable signal yet."
    actionable_signal_details = "SUTRA does not have enough recent cross-repository activity to identify a meaningful trend."

    if current_week_failed_ci > previous_week_failed_ci:
        delta = current_week_failed_ci - previous_week_failed_ci
        actionable_signal = "CI failures increased across repositories this week."
        actionable_signal_details = (
            f"{current_week_failed_ci} CI failures occurred across repositories in the last 7 days, "
            f"up by {delta} from the previous period."
        )
    elif current_week_failed_deployments > 0:
        actionable_signal = "Recent deployments need attention."
        actionable_signal_details = (
            f"{current_week_failed_deployments} deployment(s) failed or were rolled back across repositories."
        )
    elif all_lead_times and len(all_lead_times) >= 2:
        actionable_signal = "Lead time is measurable from real merged changes."
        actionable_signal_details = (
            f"Cross-repository average lead time is {_avg_lead_time_minutes(all_lead_times)} minutes "
            f"across {len(all_lead_times)} merged change(s) in the last 30 days."
        )

    return InsightsResponse(
        deployments_per_week=deployments_per_week,
        lead_time_minutes=_avg_lead_time_minutes(all_lead_times),
        ci_pass_rate=ci_pass_rate,
        agent_changes_percent=agent_changes_percent,
        human_changes_percent=human_changes_percent,
        agent_lead_time_minutes=_avg_lead_time_minutes(agent_lead_times),
        human_lead_time_minutes=_avg_lead_time_minutes(human_lead_times),
        actionable_signal=actionable_signal,
        actionable_signal_details=actionable_signal_details,
    )

