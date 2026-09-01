import json
import logging
from fastapi import APIRouter, Request, HTTPException, Depends, Header, status
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.core.config import settings
from app.db.session import get_db
from app.models.repository import Repository
from app.models.actor import Actor
from app.providers.github.events import GitHubWebhookAdapter
from app.providers.events import NormalizedPushEvent, NormalizedPullRequestEvent
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
    webhook_secret = getattr(settings, "github_webhook_secret", None) or settings.jwt_secret

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

    return {"status": "accepted", "event": x_github_event}
