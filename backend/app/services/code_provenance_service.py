from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.actor import Actor
from app.models.agent import Agent
from app.models.agent_session import AgentSession
from app.models.change import Change
from app.models.task import Task


class CodeProvenanceService:
    """
    Resolves a Git commit SHA into SUTRA provenance.

    Resolution order:

        commit SHA
            ↓
        Change.resulting_commit
            ↓
        Actor
            ↓
        Human / Agent

    For agent changes we additionally attempt:

        Change
            ↓
        Task.resulting_change_id
            ↓
        assigned_agent / claimed session

    A commit that does not exist in SUTRA is returned as
    external GitHub history rather than being guessed as
    human-authored.
    """

    def __init__(self, db: Session):
        self.db = db

    def resolve_commit(
        self,
        repository_id: str,
        commit_sha: str,
    ) -> dict[str, Any]:
        normalized_sha = commit_sha.strip().lower()

        if not normalized_sha:
            return self._external(commit_sha)

        change = self.db.scalar(
            select(Change)
            .where(
                Change.repository_id == repository_id,
                Change.resulting_commit.is_not(None),
                Change.resulting_commit == normalized_sha,
            )
        )

        # Some stored SHAs may differ in case.
        if change is None:
            change = self.db.scalar(
                select(Change)
                .where(
                    Change.repository_id == repository_id,
                    Change.resulting_commit.is_not(None),
                )
            )

            if change and (
                change.resulting_commit or ""
            ).lower() != normalized_sha:
                change = None

        if change is None:
            return self._external(commit_sha)

        actor = self.db.scalar(
            select(Actor)
            .where(Actor.id == change.actor_id)
        )

        if actor is None:
            return {
                "source": "sutra",
                "tracked": True,
                "identity_type": "unknown",
                "actor_id": change.actor_id,
                "actor_name": None,
                "change_id": change.id,
                "agent": None,
                "session": None,
                "task": None,
            }

        actor_type = (actor.type or "").lower()

        if actor_type == "agent":
            return self._agent_provenance(
                change=change,
                actor=actor,
                commit_sha=commit_sha,
            )

        return {
            "source": "sutra",
            "tracked": True,
            "identity_type": "human",
            "actor_id": actor.id,
            "actor_name": actor.name,
            "change_id": change.id,
            "agent": None,
            "session": None,
            "task": None,
        }

    def resolve_blame_ranges(
        self,
        repository_id: str,
        ranges: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """
        Enrich GitHub blame ranges with SUTRA provenance.
        """

        enriched: list[dict[str, Any]] = []

        for blame_range in ranges:
            commit_sha = blame_range.get("commit")

            provenance = self.resolve_commit(
                repository_id=repository_id,
                commit_sha=commit_sha or "",
            )

            enriched.append(
                {
                    **blame_range,
                    "provenance": provenance,
                }
            )

        return enriched

    def _agent_provenance(
        self,
        change: Change,
        actor: Actor,
        commit_sha: str,
    ) -> dict[str, Any]:
        task = self.db.scalar(
            select(Task)
            .where(
                Task.repository_id == change.repository_id,
                Task.resulting_change_id == change.id,
            )
        )

        # Fallback to change metadata_json if task link is stored there
        meta = {}
        if change.metadata_json:
            try:
                import json
                meta = json.loads(change.metadata_json)
            except Exception:
                pass

        if task is None and meta.get("task_id"):
            task = self.db.scalar(
                select(Task).where(Task.id == meta["task_id"])
            )

        agent = None
        session = None

        agent_id = task.assigned_agent_id if task else meta.get("agent_id") or actor.id
        if agent_id:
            agent = self.db.scalar(
                select(Agent)
                .where(
                    Agent.id == agent_id
                )
            )

        session_id = task.claimed_by_session_id if task else meta.get("agent_session_id")
        if session_id:
            session = self.db.scalar(
                select(AgentSession)
                .where(
                    AgentSession.id == session_id
                )
            )

        return {
            "source": "sutra",
            "tracked": True,
            "governed": meta.get("commit_origin") == "sutra_governed",
            "commit_origin": meta.get("commit_origin", "unknown"),
            "identity_type": "agent",
            "actor_id": actor.id,
            "actor_name": actor.name,
            "change_id": change.id,
            "agent": (
                {
                    "id": agent.id,
                    "name": agent.name,
                    "provider": agent.provider,
                    "model": agent.model,
                }
                if agent
                else None
            ),
            "session": (
                {
                    "id": session.id,
                    "status": session.status,
                    "expires_at": session.expires_at,
                }
                if session
                else None
            ),
            "task": (
                {
                    "id": task.id,
                    "title": task.title,
                    "status": task.status,
                    "task_type": task.task_type,
                }
                if task
                else None
            ),
        }


    @staticmethod
    def _external(commit_sha: str) -> dict[str, Any]:
        return {
            "source": "github",
            "tracked": False,
            "identity_type": "external",
            "actor_id": None,
            "actor_name": None,
            "change_id": None,
            "agent": None,
            "session": None,
            "task": None,
        }