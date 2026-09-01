from dataclasses import dataclass

from app.models.actor import Actor
from app.models.repository import Repository
from app.services.authorization_service import AuthorizationService
from app.services.change_policy_service import ChangePolicyService


@dataclass(frozen=True)
class RefUpdateProposal:
    before_commit: str | None
    after_commit: str | None
    ref: str
    operation: str
    forced: bool = False


@dataclass(frozen=True)
class GitReceiveDecision:
    decision: str
    reason: str
    reasons: list[str]
    capabilities: list[str]


class GitReceivePolicyService:
    """Synchronous policy gate for server-side Git ref updates.

    Authorization is delegated to AuthorizationService so Git receive,
    Change APIs, and future agent operations share one authorization
    source of truth.

    This service evaluates the exact ref updates Git is about to apply,
    before receive-pack updates any refs. It deliberately does not
    create a Change or mutate the Change ledger.
    """

    def __init__(self, db):
        self.db = db

    @staticmethod
    def _capabilities(actor: Actor) -> list[str]:
        return sorted(
            AuthorizationService._capabilities(actor)
        )

    def evaluate(
        self,
        repository: Repository,
        actor: Actor,
        updates: list[RefUpdateProposal],
    ) -> GitReceiveDecision:
        capabilities = self._capabilities(actor)
        reasons: list[str] = []

        if getattr(actor, "type", None) != "agent":
            return GitReceiveDecision(
                decision=ChangePolicyService.BLOCK,
                reason="Only agent actors may use Git receive.",
                reasons=["Only agent actors may use Git receive."],
                capabilities=capabilities,
            )

        # ---------------------------------------------------------
        # Central authorization boundary.
        #
        # repository.read and repository.write are both required
        # for an agent Git receive operation.
        # ---------------------------------------------------------

        for capability in (
            AuthorizationService.READ,
            AuthorizationService.WRITE,
        ):
            authorization = AuthorizationService.check(
                actor=actor,
                repository=repository,
                capability=capability,
                db=self.db,
            )

            if not authorization.allowed:
                reason = authorization.reason

                # Avoid reporting the same ownership/type failure
                # twice when checking both capabilities.
                if reason not in reasons:
                    reasons.append(reason)

        # ---------------------------------------------------------
        # Ref-level Git policy.
        # ---------------------------------------------------------

        for update in updates:
            if not update.ref.startswith(
                "refs/heads/"
            ):
                reasons.append(
                    f"Ref '{update.ref}' is outside "
                    "the supported heads namespace."
                )
                continue

            if update.operation == "delete":
                reasons.append(
                    "Branch deletion is blocked by "
                    "the agent receive policy: "
                    f"{update.ref}."
                )

            if update.forced:
                reasons.append(
                    "Force update is blocked by "
                    "the agent receive policy: "
                    f"{update.ref}."
                )

        if reasons:
            return GitReceiveDecision(
                decision=ChangePolicyService.BLOCK,
                reason=reasons[0],
                reasons=reasons,
                capabilities=capabilities,
            )

        return GitReceiveDecision(
            decision=ChangePolicyService.ALLOW,
            reason=(
                "Git ref updates satisfy the "
                "SUTRA receive policy."
            ),
            reasons=[],
            capabilities=capabilities,
        )