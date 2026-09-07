import json
import logging
from fastapi import APIRouter, Request, HTTPException, Depends, Header, status
from sqlalchemy.orm import Session
from sqlalchemy import select

from datetime import datetime
from uuid import uuid4
from app.core.config import settings
from app.db.session import get_db
from app.models.repository import Repository
from app.models.actor import Actor
from app.models.pull_request import PullRequest
from app.models.change import Change
from app.models.task import Task
from app.models.ci_job import CIJob
from datetime import timezone
from app.providers.github.events import GitHubWebhookAdapter
from app.providers.events import (
    NormalizedPushEvent,
    NormalizedPullRequestEvent,
    NormalizedCheckRunEvent,
)
from app.services.git_push_event_service import GitPushEventService

logger = logging.getLogger("sutra.api.webhooks.github")
router = APIRouter(prefix="/v1/webhooks", tags=["webhooks"])

webhook_adapter = GitHubWebhookAdapter()


@router.post(
    "/github",
    status_code=status.HTTP_200_OK,
    summary="GitHub Webhook Receiver",
    description="Receives, cryptographically verifies, and normalizes GitHub webhook events.",
)
async def handle_github_webhook(
    request: Request,
    db: Session = Depends(get_db),
    x_github_event: str = Header(..., alias="X-GitHub-Event"),
    x_hub_signature_256: str = Header(..., alias="X-Hub-Signature-256"),
):
    payload_bytes = await request.body()
    webhook_secret = getattr(settings, "github_webhook_secret", None)
    if not webhook_secret:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="GitHub webhook secret is not configured",
        )

    headers_dict = dict(request.headers)
    if not webhook_adapter.verify_signature(payload_bytes, headers_dict, webhook_secret):
        logger.warning("Rejected GitHub webhook with invalid HMAC signature")
        raise HTTPException(status_code=401, detail="Invalid webhook signature")

    try:
        payload_json = json.loads(payload_bytes.decode("utf-8"))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid JSON payload: {e}")

    normalized_event = webhook_adapter.parse_event(x_github_event, payload_json)
    if not normalized_event:
        return {"status": "ignored", "event": x_github_event}

    if isinstance(normalized_event, NormalizedPushEvent):
        # Resolve repository in SUTRA
        repo = db.scalar(
            select(Repository).where(
                Repository.slug == normalized_event.repository_name.lower(),
                Repository.deleted_at.is_(None),
            )
        )
        if repo:
            actor = db.scalar(
                select(Actor).where(
                    Actor.name == normalized_event.pusher_username,
                    Actor.type == "agent",
                )
            )
            if not actor:
                # Resolve via repository agent grants
                from app.models.agent_repository_access import AgentRepositoryAccess
                grant = db.scalar(
                    select(AgentRepositoryAccess).where(
                        AgentRepositoryAccess.repository_id == repo.id,
                        AgentRepositoryAccess.enabled.is_(True),
                    )
                )
                if grant:
                    actor = db.scalar(select(Actor).where(Actor.id == grant.agent_id))
                if not actor:
                    # Resolve any active agent belonging to the repository owner
                    actor = db.scalar(
                        select(Actor).where(
                            Actor.owner_id == repo.owner_id,
                            Actor.type == "agent",
                        )
                    )

            if not actor:
                logger.warning(f"Could not resolve agent actor for push on {repo.slug}")
                return {"status": "ignored", "reason": "No agent actor associated with repository push"}

            before_refs = {normalized_event.ref: normalized_event.before_sha}
            after_refs = {normalized_event.ref: normalized_event.after_sha}

            try:
                push_service = GitPushEventService(db)
                push_event = push_service.create_event(
                    repository=repo,
                    actor=actor,
                    before_refs=before_refs,
                    after_refs=after_refs,
                )
                return {
                    "status": "processed",
                    "event": "push",
                    "push_event_id": push_event.id,
                }
            except Exception as e:
                logger.error(f"Failed to record GitPushEvent from webhook: {e}")
                return {"status": "error", "detail": str(e)}

    elif isinstance(normalized_event, NormalizedCheckRunEvent):
        repo = db.scalar(
            select(Repository).where(
                Repository.slug == normalized_event.repository_name.lower(),
                Repository.deleted_at.is_(None),
            )
        )
        if not repo:
            repo = db.scalar(
                select(Repository).where(
                    Repository.name == normalized_event.repository_name,
                    Repository.deleted_at.is_(None),
                )
            )

        if repo:
            pr = db.scalar(
                select(PullRequest).where(
                    PullRequest.repository_id == repo.id,
                    PullRequest.source_commit == normalized_event.head_sha,
                )
            )

            # Map GitHub status / conclusion to SUTRA CIJob status
            conclusion = (normalized_event.conclusion or "").lower()
            evt_status = (normalized_event.status or "").lower()
            if conclusion == "success":
                job_status = CIJob.STATUS_PASSED
            elif conclusion in ("failure", "timed_out", "action_required"):
                job_status = CIJob.STATUS_FAILED
            elif conclusion in ("cancelled", "skipped", "neutral"):
                job_status = CIJob.STATUS_CANCELLED if conclusion == "cancelled" else CIJob.STATUS_PASSED
            elif evt_status in ("in_progress", "running"):
                job_status = CIJob.STATUS_RUNNING
            else:
                job_status = CIJob.STATUS_QUEUED

            if pr:
                job_trigger = f"github_check_{normalized_event.check_run_id}"
                job = db.scalar(
                    select(CIJob).where(
                        CIJob.pull_request_id == pr.id,
                        CIJob.commit_sha == normalized_event.head_sha,
                        CIJob.trigger == job_trigger,
                    )
                )

                started_dt = None
                if normalized_event.started_at:
                    try:
                        started_dt = datetime.fromisoformat(normalized_event.started_at.replace("Z", "+00:00"))
                    except Exception:
                        pass

                completed_dt = None
                if normalized_event.completed_at:
                    try:
                        completed_dt = datetime.fromisoformat(normalized_event.completed_at.replace("Z", "+00:00"))
                    except Exception:
                        pass

                if not job:
                    job = CIJob(
                        id=str(uuid4()),
                        pull_request_id=pr.id,
                        repository_id=repo.id,
                        change_id=pr.source_change_id,
                        commit_sha=normalized_event.head_sha,
                        target_branch=pr.target_branch,
                        status=job_status,
                        trigger=job_trigger,
                        runner_type="github_actions",
                        output_log=normalized_event.html_url or normalized_event.details_url,
                        failure_reason=conclusion if job_status == CIJob.STATUS_FAILED else None,
                        started_at=started_dt,
                        completed_at=completed_dt,
                    )
                    db.add(job)
                else:
                    job.status = job_status
                    if normalized_event.html_url:
                        job.output_log = normalized_event.html_url
                    if completed_dt:
                        job.completed_at = completed_dt
                    if job_status == CIJob.STATUS_FAILED:
                        job.failure_reason = conclusion

                db.commit()
                return {
                    "status": "processed",
                    "event": "check_run",
                    "check_run_id": normalized_event.check_run_id,
                    "pull_request_id": pr.id,
                    "job_id": job.id,
                    "job_status": job.status,
                }
            else:
                return {
                    "status": "accepted",
                    "event": "check_run",
                    "reason": "No matching SUTRA pull request for head SHA",
                    "head_sha": normalized_event.head_sha,
                }

    elif isinstance(normalized_event, NormalizedPullRequestEvent):
        repo = db.scalar(
            select(Repository).where(
                Repository.slug == normalized_event.repository_name.lower(),
                Repository.deleted_at.is_(None),
            )
        )
        if not repo:
            repo = db.scalar(
                select(Repository).where(
                    Repository.name == normalized_event.repository_name,
                    Repository.deleted_at.is_(None),
                )
            )

        if repo:
            pr = db.scalar(
                select(PullRequest)
                .join(Change, PullRequest.source_change_id == Change.id)
                .where(
                    PullRequest.repository_id == repo.id,
                    Change.metadata_json.contains(f'"github_pr_number": {normalized_event.pr_number}'),
                )
            )
            if not pr and normalized_event.head_ref:
                pr = db.scalar(
                    select(PullRequest)
                    .join(Change, PullRequest.source_change_id == Change.id)
                    .where(
                        PullRequest.repository_id == repo.id,
                        Change.branch == normalized_event.head_ref,
                    )
                )

            if pr:
                change = db.scalar(select(Change).where(Change.id == pr.source_change_id))
                action = (normalized_event.action or "").lower()

                if action == "synchronize":
                    new_head = normalized_event.head_sha
                    old_head = pr.source_commit
                    if new_head and new_head != old_head:
                        pr.source_commit = new_head
                        if change:
                            change.resulting_commit = new_head
                            change_meta = {}
                            if change.metadata_json:
                                try:
                                    change_meta = json.loads(change.metadata_json)
                                except Exception:
                                    pass
                            approved_head = change_meta.get("approved_head_sha")
                            if approved_head and approved_head != new_head:
                                change_meta["approved_head_sha"] = None
                                change.metadata_json = json.dumps(change_meta, sort_keys=True)
                                if pr.status == PullRequest.STATUS_APPROVED:
                                    pr.status = PullRequest.STATUS_OPEN
                        db.commit()
                        return {
                            "status": "processed",
                            "event": "pull_request",
                            "action": "synchronize",
                            "pull_request_id": pr.id,
                            "new_head_sha": new_head,
                        }

                elif action == "closed":
                    now = datetime.now(timezone.utc)
                    if normalized_event.is_merged:
                        pr.status = PullRequest.STATUS_MERGED
                        pr.merged_at = pr.merged_at or now
                        if pr.target_commit is None:
                            pr.target_commit = normalized_event.base_sha or pr.source_commit
                        if change:
                            change.status = "recorded"
                            change_meta = {}
                            if change.metadata_json:
                                try:
                                    change_meta = json.loads(change.metadata_json)
                                except Exception:
                                    pass
                            change_meta["merged"] = True
                            change.metadata_json = json.dumps(change_meta, sort_keys=True)

                        linked_task = db.scalar(
                            select(Task).where(
                                (Task.resulting_pull_request_id == pr.id) |
                                (Task.resulting_change_id == pr.source_change_id)
                            )
                        )
                        if linked_task and linked_task.status != Task.STATUS_COMPLETED:
                            from app.services.task_service import TaskService
                            TaskService(db)._complete_locked_task(linked_task, actor_id=pr.author_id)
                    else:
                        pr.status = PullRequest.STATUS_CLOSED
                        pr.closed_at = pr.closed_at or now

                    db.commit()
                    return {
                        "status": "processed",
                        "event": "pull_request",
                        "action": "closed",
                        "pull_request_id": pr.id,
                        "merged": normalized_event.is_merged,
                    }

                elif action == "reopened":
                    pr.status = PullRequest.STATUS_OPEN
                    pr.closed_at = None
                    db.commit()
                    return {
                        "status": "processed",
                        "event": "pull_request",
                        "action": "reopened",
                        "pull_request_id": pr.id,
                    }

                return {
                    "status": "accepted",
                    "event": "pull_request",
                    "action": action,
                    "pull_request_id": pr.id,
                }
            else:
                return {
                    "status": "accepted",
                    "event": "pull_request",
                    "reason": "No matching SUTRA pull request found",
                    "pr_number": normalized_event.pr_number,
                }

    return {"status": "accepted", "event": x_github_event}
