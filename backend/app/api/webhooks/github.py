import json
import logging
from fastapi import APIRouter, Request, HTTPException, Depends, Header, status
from sqlalchemy.orm import Session
from sqlalchemy import select

from datetime import datetime, timezone
from uuid import uuid4
from app.core.config import settings
from app.db.session import get_db
from app.models.repository import Repository
from app.models.actor import Actor
from app.models.pull_request import PullRequest
from app.models.change import Change
from app.models.task import Task
from app.models.ci_job import CIJob
from app.models.issue import Issue, IssueComment
from app.providers.github.events import GitHubWebhookAdapter
from app.providers.events import (
    NormalizedPushEvent,
    NormalizedPullRequestEvent,
    NormalizedCheckRunEvent,
    NormalizedIssueEvent,
    NormalizedIssueCommentEvent,
)
from app.services.git_push_event_service import GitPushEventService
from app.services.pull_request_service import PullRequestService
from app.services import knowledge_graph_service
from app.core.redis_service import redis_service

logger = logging.getLogger("sutra.api.webhooks.github")
router = APIRouter(prefix="/v1/webhooks", tags=["webhooks"])

webhook_adapter = GitHubWebhookAdapter()


def _invalidate_repo_cache(repo_id: str, event_type: str) -> None:
    """
    Invalidate affected Redis response cache keys on webhook events.
    """
    try:
        if event_type == "push":
            redis_service.delete(f"github:cache:branches:{repo_id}")
            redis_service.delete_by_pattern(f"github:cache:commits:{repo_id}:*")
            redis_service.delete_by_pattern(f"github:cache:tree:{repo_id}:*")
            redis_service.delete_by_pattern(f"github:cache:file:{repo_id}:*")
            redis_service.delete_by_pattern(f"github:cache:blame:{repo_id}:*")
        elif event_type in ("issues", "issue_comment"):
            redis_service.delete_by_pattern(f"github:cache:issues:{repo_id}:*")
        elif event_type == "pull_request":
            redis_service.delete(f"github:cache:branches:{repo_id}")
            redis_service.delete_by_pattern(f"github:cache:pr:{repo_id}:*")
            redis_service.delete_by_pattern(f"github:cache:commits:{repo_id}:*")
        elif event_type == "check_run":
            redis_service.delete_by_pattern(f"github:cache:ci:{repo_id}:*")
            redis_service.delete_by_pattern(f"github:cache:pr:{repo_id}:*")
    except Exception as e:
        logger.warning(f"Cache invalidation failed for repo {repo_id} on {event_type}: {e}")


def _resolve_repository(db: Session, event) -> Repository | None:
    """
    Resolve repository securely using priority order:
    1. GitHub external ID (if present and persisted)
    2. provider_owner + repository_name
    3. slug or name fallback
    """
    external_id = getattr(event, "repository_external_id", None)
    if external_id:
        repo = db.scalar(
            select(Repository).where(
                Repository.provider_type == "github",
                Repository.external_id == str(external_id),
                Repository.deleted_at.is_(None),
            )
        )
        if repo:
            return repo

    owner = getattr(event, "repository_owner", None)
    name = getattr(event, "repository_name", None)
    if owner and name:
        repo = db.scalar(
            select(Repository).where(
                Repository.provider_owner == owner,
                Repository.slug == name.lower(),
                Repository.deleted_at.is_(None),
            )
        )
        if repo:
            return repo

        repo = db.scalar(
            select(Repository).where(
                Repository.provider_owner == owner,
                Repository.name == name,
                Repository.deleted_at.is_(None),
            )
        )
        if repo:
            return repo

    if name:
        repo = db.scalar(
            select(Repository).where(
                Repository.slug == name.lower(),
                Repository.deleted_at.is_(None),
            )
        )
        if repo:
            return repo

        repo = db.scalar(
            select(Repository).where(
                Repository.name == name,
                Repository.deleted_at.is_(None),
            )
        )
        if repo:
            return repo

    return None


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

    repo = _resolve_repository(db, normalized_event)

    if isinstance(normalized_event, NormalizedPushEvent):
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
                _invalidate_repo_cache(repo.id, "push")
                return {
                    "status": "processed",
                    "event": "push",
                    "push_event_id": push_event.id,
                }
            except Exception as e:
                logger.error(f"Failed to record GitPushEvent from webhook: {e}")
                return {"status": "error", "detail": str(e)}

    elif isinstance(normalized_event, NormalizedCheckRunEvent):
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
                _invalidate_repo_cache(repo.id, "check_run")
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

    elif isinstance(normalized_event, NormalizedIssueEvent):
        if not repo:
            return {
                "status": "accepted",
                "event": "issues",
                "reason": "Repository not found",
            }

        now = datetime.now(timezone.utc)
        parsed_created_at = None
        if normalized_event.created_at:
            try:
                parsed_created_at = datetime.fromisoformat(normalized_event.created_at.replace("Z", "+00:00"))
            except Exception:
                pass

        parsed_updated_at = None
        if normalized_event.updated_at:
            try:
                parsed_updated_at = datetime.fromisoformat(normalized_event.updated_at.replace("Z", "+00:00"))
            except Exception:
                pass

        parsed_closed_at = None
        if normalized_event.closed_at:
            try:
                parsed_closed_at = datetime.fromisoformat(normalized_event.closed_at.replace("Z", "+00:00"))
            except Exception:
                pass
        elif normalized_event.state == "closed":
            parsed_closed_at = now

        # Locate existing Issue by repository + github_issue_id or github_issue_number
        issue = db.scalar(
            select(Issue).where(
                Issue.repository_id == repo.id,
                (Issue.github_issue_id == normalized_event.issue_id) |
                (Issue.github_issue_number == normalized_event.issue_number)
            )
        )

        if not issue:
            # Genuinely human/GitHub-created issue
            issue = Issue(
                repository_id=repo.id,
                github_issue_id=normalized_event.issue_id,
                github_issue_number=normalized_event.issue_number,
                github_html_url=normalized_event.html_url,
                source_type="human",
                agent_id=None,
                agent_session_id=None,
                task_id=None,
                actor_id=repo.owner_id,
                title=normalized_event.title,
                body=normalized_event.body,
                status=normalized_event.state,
                github_author_login=normalized_event.author_login,
                created_at=parsed_created_at or now,
                updated_at=parsed_updated_at or now,
                closed_at=parsed_closed_at,
            )
            db.add(issue)
        else:
            # Update existing issue idempotently, STRICTLY PRESERVING agent provenance if present
            issue.github_issue_id = normalized_event.issue_id
            issue.github_issue_number = normalized_event.issue_number
            issue.github_html_url = normalized_event.html_url
            issue.title = normalized_event.title
            issue.body = normalized_event.body
            issue.status = normalized_event.state
            issue.github_author_login = normalized_event.author_login
            if parsed_created_at:
                issue.created_at = parsed_created_at
            issue.updated_at = parsed_updated_at or now
            issue.closed_at = parsed_closed_at

        repo.github_objects_synced_at = now
        db.commit()
        db.refresh(issue)

        # Trigger incremental Knowledge Graph indexing for repository
        try:
            knowledge_graph_service.index_engineering_lifecycle(db, repo)
            db.commit()
        except Exception as e:
            logger.warning(f"Failed to update Knowledge Graph on issue webhook: {e}")

        _invalidate_repo_cache(repo.id, "issues")

        return {
            "status": "processed",
            "event": "issues",
            "action": normalized_event.action,
            "issue_id": issue.id,
            "github_issue_number": issue.github_issue_number,
            "state": issue.status,
        }

    elif isinstance(normalized_event, NormalizedIssueCommentEvent):
        if not repo:
            return {"status": "accepted", "event": "issue_comment", "reason": "Repository not found"}

        issue = db.scalar(
            select(Issue).where(
                Issue.repository_id == repo.id,
                Issue.github_issue_number == normalized_event.issue_number,
            )
        )
        if not issue:
            return {"status": "accepted", "event": "issue_comment", "reason": "Parent issue not found"}

        now = datetime.now(timezone.utc)
        parsed_created_at = None
        if normalized_event.created_at:
            try:
                parsed_created_at = datetime.fromisoformat(normalized_event.created_at.replace("Z", "+00:00"))
            except Exception:
                pass

        parsed_updated_at = None
        if normalized_event.updated_at:
            try:
                parsed_updated_at = datetime.fromisoformat(normalized_event.updated_at.replace("Z", "+00:00"))
            except Exception:
                pass

        existing_c = db.scalar(
            select(IssueComment).where(IssueComment.github_comment_id == normalized_event.comment_id)
        )
        if existing_c:
            if normalized_event.action == "deleted":
                db.delete(existing_c)
            else:
                existing_c.body = normalized_event.body
                existing_c.github_html_url = normalized_event.html_url
                existing_c.github_author_login = normalized_event.author_login
                existing_c.updated_at = parsed_updated_at or now
        elif normalized_event.action != "deleted":
            c = IssueComment(
                issue_id=issue.id,
                github_comment_id=normalized_event.comment_id,
                github_html_url=normalized_event.html_url,
                author_id=None,
                github_author_login=normalized_event.author_login,
                body=normalized_event.body,
                created_at=parsed_created_at or now,
                updated_at=parsed_updated_at or now,
            )
            db.add(c)

        repo.github_objects_synced_at = now
        db.commit()
        _invalidate_repo_cache(repo.id, "issue_comment")
        return {
            "status": "processed",
            "event": "issue_comment",
            "action": normalized_event.action,
            "comment_id": normalized_event.comment_id,
        }

    elif isinstance(normalized_event, NormalizedPullRequestEvent):
        if not repo:
            return {
                "status": "accepted",
                "event": "pull_request",
                "reason": "Repository not found",
            }

        action = (normalized_event.action or "").lower()
        is_closed = (action == "closed")
        is_merged = normalized_event.is_merged

        pr_svc = PullRequestService(db)
        pr = pr_svc.upsert_github_pull_request(
            repository=repo,
            pr_number=normalized_event.pr_number,
            title=normalized_event.title or f"GitHub PR #{normalized_event.pr_number}",
            target_branch=normalized_event.base_ref,
            head_branch=normalized_event.head_ref,
            head_sha=normalized_event.head_sha,
            base_sha=normalized_event.base_sha,
            description=normalized_event.body,
            html_url=normalized_event.html_url,
            author_login=normalized_event.author_login,
            is_merged=is_merged,
            is_closed=is_closed,
            action=action,
        )

        # If merged, complete linked task if any
        if is_merged and pr:
            linked_task = db.scalar(
                select(Task).where(
                    (Task.resulting_pull_request_id == pr.id) |
                    (Task.resulting_change_id == pr.source_change_id)
                )
            )
            if linked_task and linked_task.status != Task.STATUS_COMPLETED:
                from app.services.task_service import TaskService
                TaskService(db)._complete_locked_task(linked_task, actor_id=pr.author_id)

        db.commit()

        # Update Knowledge Graph
        try:
            knowledge_graph_service.index_engineering_lifecycle(db, repo)
            db.commit()
        except Exception as e:
            logger.warning(f"Failed to update Knowledge Graph on PR webhook: {e}")

        _invalidate_repo_cache(repo.id, "pull_request")

        return {
            "status": "processed",
            "event": "pull_request",
            "action": action,
            "pull_request_id": pr.id,
            "pr_number": normalized_event.pr_number,
            "status_state": pr.status,
        }

    return {"status": "accepted", "event": x_github_event}
