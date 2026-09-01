from typing import Optional, Any
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.core.config import settings
from app.models.change import Change
from app.models.repository import Repository
from app.models.pull_request import PullRequest
from app.providers.checks import (
    CheckProvider,
    CheckRunReport,
    CheckStatus,
    CheckConclusion,
)
from app.providers.registry import ProviderRegistry
from app.services.change_policy_service import PolicyDecision


class CheckService:
    """
    Authoritative service for publishing and synchronizing SUTRA policy decisions
    and review gates to substrate Check Runs.
    """

    def __init__(self, db: Session, registry: ProviderRegistry):
        self.db = db
        self.registry = registry

    def publish_change_policy_check(
        self,
        change: Change,
        repository: Repository,
        policy_decision: PolicyDecision,
        review_approved: bool = False,
    ) -> str:
        if not change.resulting_commit:
            return ""

        check_provider = self.registry.get_check_provider(repository)

        if policy_decision.decision == "allow" and review_approved:
            status = CheckStatus.COMPLETED
            conclusion = CheckConclusion.SUCCESS
            title = "SUTRA Policy & Review Approved"
            summary = "All deterministic policy checks and human review approvals passed."
        elif policy_decision.decision == "block":
            status = CheckStatus.COMPLETED
            conclusion = CheckConclusion.FAILURE
            title = "SUTRA Policy Blocked"
            summary = f"Change is blocked by SUTRA policy: {policy_decision.reason}"
        else:
            status = CheckStatus.IN_PROGRESS
            conclusion = CheckConclusion.ACTION_REQUIRED
            title = "SUTRA Review or Policy Verification Required"
            summary = f"Change requires human review or additional checks. Reason: {policy_decision.reason}"

        details_url = f"{settings.sutra_base_url}/changes/{change.id}"
        owner_name = (repository.settings or {}).get("github_owner")
        if not owner_name:
            from app.models.actor import Actor
            actor = self.db.scalar(select(Actor).where(Actor.id == repository.owner_id))
            owner_name = actor.name if actor else repository.owner_id

        report = CheckRunReport(
            check_name="SUTRA / Policy Engine & Gate",
            head_sha=change.resulting_commit,
            status=status,
            conclusion=conclusion,
            title=title,
            summary=summary,
            details_url=details_url,
            external_id=change.id,
        )

        return check_provider.report_check_run(
            owner=owner_name,
            name=repository.slug,
            report=report,
        )
