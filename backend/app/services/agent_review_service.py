from datetime import datetime, timezone
import json
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.actor import Actor
from app.models.agent import Agent
from app.models.change_event import ChangeEvent
from app.models.inline_review_comment import InlineReviewComment
from app.models.pull_request import PullRequest
from app.models.repository import Repository
from app.models.user import User
from app.services.authorization_service import AuthorizationService
from app.services.inline_review_service import InlineReviewService


class AgentReviewService:
    """
    Authoritative service for Agent-Aware Reviews.

    Architecture Rule:
      - ChangeReview remains the sole authoritative approval mechanism.
      - Agent reviews, comments, and findings are discussion & analysis artifacts.
      - Capability checks delegate strictly to AuthorizationService.
    """

    VALID_SEVERITIES = {"low", "medium", "high", "critical"}
    VALID_CATEGORIES = {
        "bug",
        "security",
        "correctness",
        "performance",
        "style",
        "maintainability",
        "test",
        "dependency",
    }

    def __init__(self, db: Session):
        self.db = db
        self.inline_service = InlineReviewService(db)

    def _get_agent_and_actor(self, agent_id: str) -> tuple[Agent, Actor]:
        agent = self.db.scalar(
            select(Agent).where(
                Agent.id == agent_id,
                Agent.is_active.is_(True),
                Agent.status == "active",
            )
        )
        if agent is None:
            raise PermissionError("Agent is inactive or not found")

        actor = self.db.scalar(
            select(Actor).where(
                Actor.id == agent.id,
                Actor.type == "agent",
            )
        )
        if actor is None:
            raise PermissionError("Agent actor record not found")

        return agent, actor

    def _authorize_agent_repo_access(
        self,
        agent_id: str,
        repository: Repository,
        capability: str,
    ) -> tuple[Agent, Actor]:
        agent, actor = self._get_agent_and_actor(agent_id)
        AuthorizationService.require(actor, repository, capability)
        return agent, actor

    def create_agent_comment(
        self,
        agent_id: str,
        pull_request_id: str,
        body: str,
        path: str | None = None,
        diff_side: str | None = None,
        line_number: int | None = None,
        commit_sha: str | None = None,
        parent_id: str | None = None,
    ) -> InlineReviewComment:
        pr = self.db.scalar(select(PullRequest).where(PullRequest.id == pull_request_id))
        if pr is None:
            raise ValueError("PullRequest not found")

        repository = self.db.scalar(
            select(Repository).where(
                Repository.id == pr.repository_id,
                Repository.deleted_at.is_(None),
            )
        )
        if repository is None:
            raise ValueError("Repository not found or deleted")

        agent, actor = self._authorize_agent_repo_access(
            agent_id, repository, AuthorizationService.WRITE
        )

        comment = self.inline_service.create_comment(
            pull_request_id=pull_request_id,
            author_id=agent.owner_id,
            body=body,
            path=path,
            diff_side=diff_side,
            line_number=line_number,
            commit_sha=commit_sha,
            parent_id=parent_id,
        )

        event_type = "agent_review.reply_created" if parent_id else "agent_review.comment_created"
        event_meta = {
            "pull_request_id": pr.id,
            "repository_id": pr.repository_id,
            "comment_id": comment.id,
            "agent_id": agent.id,
            "agent_name": agent.name,
        }
        event = ChangeEvent(
            change_id=pr.source_change_id,
            actor_id=actor.id,
            event_type=event_type,
            from_status=None,
            to_status=comment.status,
            reason=None,
            metadata_json=json.dumps(event_meta, sort_keys=True),
        )
        self.db.add(event)
        self.db.flush()
        return comment

    def create_agent_finding(
        self,
        agent_id: str,
        pull_request_id: str,
        severity: str,
        category: str,
        message: str,
        path: str | None = None,
        line_number: int | None = None,
        diff_side: str | None = None,
        suggested_fix: str | None = None,
    ) -> InlineReviewComment:
        if severity not in self.VALID_SEVERITIES:
            raise ValueError(f"Invalid severity '{severity}'. Must be one of {sorted(self.VALID_SEVERITIES)}")
        if category not in self.VALID_CATEGORIES:
            raise ValueError(f"Invalid category '{category}'. Must be one of {sorted(self.VALID_CATEGORIES)}")
        if not message or not message.strip():
            raise ValueError("Finding message cannot be empty")

        pr = self.db.scalar(select(PullRequest).where(PullRequest.id == pull_request_id))
        if pr is None:
            raise ValueError("PullRequest not found")

        repository = self.db.scalar(
            select(Repository).where(
                Repository.id == pr.repository_id,
                Repository.deleted_at.is_(None),
            )
        )
        if repository is None:
            raise ValueError("Repository not found or deleted")

        agent, actor = self._authorize_agent_repo_access(
            agent_id, repository, AuthorizationService.WRITE
        )

        body_text = f"[{severity.upper()}] [{category.upper()}] {message.strip()}"
        if suggested_fix and suggested_fix.strip():
            body_text += f"\n\nSuggested Fix:\n```\n{suggested_fix.strip()}\n```"

        comment = self.inline_service.create_comment(
            pull_request_id=pull_request_id,
            author_id=agent.owner_id,
            body=body_text,
            path=path,
            diff_side=diff_side,
            line_number=line_number,
        )

        finding_meta = {
            "pull_request_id": pr.id,
            "repository_id": pr.repository_id,
            "comment_id": comment.id,
            "agent_id": agent.id,
            "agent_name": agent.name,
            "severity": severity,
            "category": category,
            "path": path,
            "line_number": line_number,
            "suggested_fix": suggested_fix,
        }
        event = ChangeEvent(
            change_id=pr.source_change_id,
            actor_id=actor.id,
            event_type="agent_review.finding_created",
            from_status=None,
            to_status=comment.status,
            reason=None,
            metadata_json=json.dumps(finding_meta, sort_keys=True),
        )
        self.db.add(event)
        self.db.flush()
        return comment

    def resolve_agent_thread(self, agent_id: str, comment_id: str) -> InlineReviewComment:
        comment = self.db.scalar(select(InlineReviewComment).where(InlineReviewComment.id == comment_id))
        if comment is None:
            raise ValueError("Comment not found")

        pr = self.db.scalar(select(PullRequest).where(PullRequest.id == comment.pull_request_id))
        if pr is None:
            raise ValueError("PullRequest not found")

        repository = self.db.scalar(
            select(Repository).where(
                Repository.id == pr.repository_id,
                Repository.deleted_at.is_(None),
            )
        )
        if repository is None:
            raise ValueError("Repository not found or deleted")

        agent, actor = self._authorize_agent_repo_access(agent_id, repository, AuthorizationService.WRITE)
        resolved = self.inline_service.resolve_thread(comment_id, agent.owner_id)

        event_meta = {
            "pull_request_id": pr.id,
            "repository_id": pr.repository_id,
            "comment_id": resolved.id,
            "agent_id": agent.id,
        }
        event = ChangeEvent(
            change_id=pr.source_change_id,
            actor_id=actor.id,
            event_type="agent_review.thread_resolved",
            from_status=None,
            to_status="resolved",
            reason=None,
            metadata_json=json.dumps(event_meta, sort_keys=True),
        )
        self.db.add(event)
        self.db.flush()
        return resolved

    def reopen_agent_thread(self, agent_id: str, comment_id: str) -> InlineReviewComment:
        comment = self.db.scalar(select(InlineReviewComment).where(InlineReviewComment.id == comment_id))
        if comment is None:
            raise ValueError("Comment not found")

        pr = self.db.scalar(select(PullRequest).where(PullRequest.id == comment.pull_request_id))
        if pr is None:
            raise ValueError("PullRequest not found")

        repository = self.db.scalar(
            select(Repository).where(
                Repository.id == pr.repository_id,
                Repository.deleted_at.is_(None),
            )
        )
        if repository is None:
            raise ValueError("Repository not found or deleted")

        agent, actor = self._authorize_agent_repo_access(agent_id, repository, AuthorizationService.WRITE)
        reopened = self.inline_service.reopen_thread(comment_id, agent.owner_id)

        event_meta = {
            "pull_request_id": pr.id,
            "repository_id": pr.repository_id,
            "comment_id": reopened.id,
            "agent_id": agent.id,
        }
        event = ChangeEvent(
            change_id=pr.source_change_id,
            actor_id=actor.id,
            event_type="agent_review.thread_reopened",
            from_status=None,
            to_status="active",
            reason=None,
            metadata_json=json.dumps(event_meta, sort_keys=True),
        )
        self.db.add(event)
        self.db.flush()
        return reopened

    def get_agent_review_summary(self, pull_request_id: str, requestor_id: str, is_agent: bool = False) -> dict:
        pr = self.db.scalar(select(PullRequest).where(PullRequest.id == pull_request_id))
        if pr is None:
            raise ValueError("PullRequest not found")

        repository = self.db.scalar(
            select(Repository).where(
                Repository.id == pr.repository_id,
                Repository.deleted_at.is_(None),
            )
        )
        if repository is None:
            raise ValueError("Repository not found or deleted")

        if is_agent:
            self._authorize_agent_repo_access(requestor_id, repository, AuthorizationService.READ)
        else:
            user = self.db.scalar(select(User).where(User.id == requestor_id))
            if user is None:
                raise PermissionError("User not found")
            if repository.visibility == "private" and repository.owner_id != requestor_id:
                raise PermissionError("User does not have access to this private repository")

        # Query agent finding events
        events = self.db.scalars(
            select(ChangeEvent).where(
                ChangeEvent.change_id == pr.source_change_id,
                ChangeEvent.event_type.in_([
                    "agent_review.comment_created",
                    "agent_review.finding_created",
                    "agent_review.thread_resolved",
                    "agent_review.thread_reopened",
                ]),
            )
        ).all()

        findings = []
        participating_agents = set()
        severity_counts = {"low": 0, "medium": 0, "high": 0, "critical": 0}

        for ev in events:
            if ev.event_type == "agent_review.finding_created":
                try:
                    meta = json.loads(ev.metadata_json or "{}")
                    sev = meta.get("severity", "low")
                    if sev in severity_counts:
                        severity_counts[sev] += 1
                    if "agent_id" in meta:
                        participating_agents.add(meta["agent_id"])
                    findings.append(meta)
                except json.JSONDecodeError:
                    continue

        return {
            "pull_request_id": pr.id,
            "repository_id": pr.repository_id,
            "total_findings": len(findings),
            "severity_distribution": severity_counts,
            "participating_agents_count": len(participating_agents),
            "participating_agent_ids": sorted(list(participating_agents)),
            "findings": findings,
        }
