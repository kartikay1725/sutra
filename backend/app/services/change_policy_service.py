import json
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.actor import Actor
from app.models.change import Change
from app.models.change_dependency import ChangeDependency
from app.models.repository import Repository
from app.services.authorization_service import AuthorizationService
from app.services.conflict_service import ConflictService


@dataclass
class PolicyDecision:
    decision: str
    reason: str
    reasons: list[str]
    conflict_level: str
    related_change_ids: list[str]
    dependency_count: int
    capabilities: list[str]


class ChangePolicyService:
    """
    Deterministic policy evaluation for SUTRA Changes.

    Authorization is delegated to AuthorizationService.

    This layer is responsible for:
      - change risk
      - Git conflict analysis
      - dependency relationships
      - lifecycle safety

    It does not mutate the Change.
    """

    ALLOW = "allow"
    REVIEW = "review"
    BLOCK = "block"

    def __init__(self, db: Session):
        self.db = db

    def evaluate(
        self,
        change: Change,
    ) -> PolicyDecision:

        actor = self.db.scalar(
            select(Actor).where(
                Actor.id == change.actor_id
            )
        )

        if actor is None:
            return PolicyDecision(
                decision=self.BLOCK,
                reason="Change actor identity could not be resolved.",
                reasons=[
                    "Change actor identity could not be resolved."
                ],
                conflict_level="potential_conflict",
                related_change_ids=[],
                dependency_count=0,
                capabilities=[],
            )

        repository = self.db.scalar(
            select(Repository).where(
                Repository.id == change.repository_id,
                Repository.deleted_at.is_(None),
            )
        )

        if repository is None:
            return PolicyDecision(
                decision=self.BLOCK,
                reason="Change repository could not be resolved.",
                reasons=[
                    "Change repository could not be resolved."
                ],
                conflict_level="potential_conflict",
                related_change_ids=[],
                dependency_count=0,
                capabilities=[],
            )

        capabilities = sorted(
            AuthorizationService._capabilities(actor)
        )

        reasons: list[str] = []

        # -------------------------------------------------
        # AUTHORIZATION / CAPABILITY POLICY
        # -------------------------------------------------

        required_capabilities = {
            AuthorizationService.READ,
            AuthorizationService.CHANGE_CREATE,
        }

        missing_capabilities = sorted(
            capability
            for capability in required_capabilities
            if not AuthorizationService.check(
                actor=actor,
                repository=repository,
                capability=capability,
                db=self.db,
            ).allowed
        )

        if missing_capabilities:
            reasons.append(
                "Actor is missing required capabilities: "
                + ", ".join(missing_capabilities)
            )

        # -------------------------------------------------
        # CHANGE STATE POLICY
        # -------------------------------------------------

        if change.status not in {
            "proposed",
            "recorded",
        }:
            reasons.append(
                f"Change status '{change.status}' is not eligible "
                "for policy evaluation."
            )

        if not change.resulting_commit:
            reasons.append(
                "Change does not have a resulting commit yet."
            )

        # -------------------------------------------------
        # RISK POLICY
        # -------------------------------------------------

        if change.risk_level == "critical":
            reasons.append(
                "Critical-risk changes require explicit review."
            )

        elif change.risk_level == "high":
            reasons.append(
                "High-risk changes require review."
            )

        elif change.risk_level == "medium":
            reasons.append(
                "Medium-risk change requires additional review."
            )

        # -------------------------------------------------
        # CONFLICT POLICY
        # -------------------------------------------------

        conflict = ConflictService(
            self.db
        ).analyze(change)

        if conflict.level == ConflictService.LEVEL_CONFLICT:
            reasons.append(
                "Git detected an actual merge conflict."
            )

        elif conflict.level == ConflictService.LEVEL_POTENTIAL:
            reasons.append(
                "Git could not establish a conflict-free merge."
            )

        elif conflict.level == ConflictService.LEVEL_OVERLAP:
            reasons.append(
                "Change overlaps another recorded change."
            )

        # -------------------------------------------------
        # DEPENDENCY POLICY
        # -------------------------------------------------

        dependencies = self.db.scalars(
            select(ChangeDependency).where(
                (
                    ChangeDependency.source_change_id
                    == change.id
                )
                |
                (
                    ChangeDependency.target_change_id
                    == change.id
                )
            )
        ).all()

        blocking_dependency_count = sum(
            1
            for dependency in dependencies
            if dependency.relationship in {
                "depends_on",
                "conflicts_with",
            }
        )

        if blocking_dependency_count:
            reasons.append(
                f"Change has {blocking_dependency_count} "
                "dependency/conflict relationship(s)."
            )

        # -------------------------------------------------
        # FINAL DECISION
        # -------------------------------------------------

        if missing_capabilities:
            decision = self.BLOCK
            reason = (
                "Change is blocked because the actor lacks "
                "required capabilities."
            )

        elif conflict.level == ConflictService.LEVEL_CONFLICT:
            decision = self.BLOCK
            reason = (
                "Change is blocked because Git detected "
                "an actual merge conflict."
            )

        elif conflict.level == ConflictService.LEVEL_POTENTIAL:
            decision = self.REVIEW
            reason = (
                "Change requires review because Git could not "
                "establish a clean merge."
            )

        elif change.risk_level == "critical":
            decision = self.BLOCK
            reason = (
                "Critical-risk changes are blocked pending "
                "explicit approval."
            )

        elif (
            change.risk_level in {"high", "medium"}
            or conflict.level == ConflictService.LEVEL_OVERLAP
            or blocking_dependency_count > 0
            or not change.resulting_commit
            or change.status not in {"proposed", "recorded"}
        ):
            decision = self.REVIEW
            reason = (
                "Change requires review before it can be "
                "treated as safe."
            )

        else:
            decision = self.ALLOW
            reason = (
                "Change satisfies the current deterministic "
                "SUTRA policy."
            )

        return PolicyDecision(
            decision=decision,
            reason=reason,
            reasons=reasons,
            conflict_level=conflict.level,
            related_change_ids=conflict.related_change_ids,
            dependency_count=len(dependencies),
            capabilities=capabilities,
        )