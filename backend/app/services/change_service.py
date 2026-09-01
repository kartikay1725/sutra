import hashlib
import json
import subprocess
from pathlib import Path
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.actor import Actor
from app.models.change import Change
from app.models.change_file import ChangeFile
from app.models.repository import Repository
from app.models.change_review import ChangeReview
from app.models.change_event import ChangeEvent
from app.services.change_policy_service import ChangePolicyService
from app.services.authorization_service import AuthorizationService


class ChangeService:

    # ---------------------------------------------------------
    # AUTHORITATIVE CHANGE LIFECYCLE
    # ---------------------------------------------------------

    VALID_STATUSES = {
        "proposed",
        "recorded",
        "blocked",
        "rejected",
    }

    TERMINAL_STATUSES = {
        "recorded",
        "blocked",
        "rejected",
    }

    VALID_TRANSITIONS = {
        "proposed": {
            "recorded",
            "blocked",
            "rejected",
        },
        "recorded": set(),
        "blocked": set(),
        "rejected": set(),
    }

    AUDIT_ONLY_EVENTS = {
        "change.created",
        "change.policy_evaluated",
        "change.review_requested",
        "change.review_approved",
        "change.review_rejected",
    }

    def __init__(self, db: Session):
        self.db = db

    # ---------------------------------------------------------
    # AUTHORIZATION
    # ---------------------------------------------------------

    def _require_agent_capability(
        self,
        actor: Actor,
        repository: Repository,
        capability: str,
    ) -> None:

        decision = AuthorizationService.check(
            actor=actor,
            repository=repository,
            capability=capability,
            db=self.db,
        )

        if not decision.allowed:
            raise PermissionError(
                decision.reason
            )

    # ---------------------------------------------------------
    # STATE TRANSITION + AUDIT
    # ---------------------------------------------------------

    def transition_change(
        self,
        change: Change,
        new_status: str,
        actor_id: str | None,
        event_type: str,
        reason: str | None = None,
        metadata: dict | None = None,
    ) -> None:

        current_status = change.status

        if new_status not in self.VALID_STATUSES:
            raise ValueError(
                f"Invalid change status: {new_status}"
            )

        if current_status not in self.VALID_STATUSES:
            raise ValueError(
                f"Change currently has invalid status: {current_status}"
            )

        if event_type == "change.created":

            if new_status != "proposed":
                raise ValueError(
                    "A newly created change must enter the proposed state"
                )

            event = ChangeEvent(
                change_id=change.id,
                actor_id=actor_id,
                event_type=event_type,
                from_status=None,
                to_status="proposed",
                reason=reason,
                metadata_json=json.dumps(
                    metadata or {},
                    separators=(",", ":"),
                    sort_keys=True,
                ),
            )

            self.db.add(event)

            change.status = "proposed"

            return

        if current_status == new_status:

            event = ChangeEvent(
                change_id=change.id,
                actor_id=actor_id,
                event_type=event_type,
                from_status=current_status,
                to_status=current_status,
                reason=reason,
                metadata_json=json.dumps(
                    metadata or {},
                    separators=(",", ":"),
                    sort_keys=True,
                ),
            )

            self.db.add(event)

            return

        if current_status in self.TERMINAL_STATUSES:
            raise ValueError(
                "Invalid status transition from terminal state "
                f"{current_status} to {new_status}"
            )

        allowed_targets = self.VALID_TRANSITIONS.get(
            current_status,
            set(),
        )

        if new_status not in allowed_targets:
            raise ValueError(
                f"Invalid status transition from "
                f"{current_status} to {new_status}"
            )

        change.status = new_status

        event = ChangeEvent(
            change_id=change.id,
            actor_id=actor_id,
            event_type=event_type,
            from_status=current_status,
            to_status=new_status,
            reason=reason,
            metadata_json=json.dumps(
                metadata or {},
                separators=(",", ":"),
                sort_keys=True,
            ),
        )

        self.db.add(event)

    # ---------------------------------------------------------
    # REVIEW GATING
    # ---------------------------------------------------------

    def _has_approved_review(
        self,
        change: Change,
    ) -> bool:

        review = self.db.scalar(
            select(ChangeReview)
            .where(
                ChangeReview.change_id == change.id,
                ChangeReview.status == "approved",
                ChangeReview.reviewer_id.is_not(None),
            )
            .order_by(
                ChangeReview.reviewed_at.desc()
            )
        )

        return review is not None

    # ---------------------------------------------------------
    # FINALIZE CHANGE
    # ---------------------------------------------------------

    def finalize_change(
        self,
        change: Change,
    ) -> Change:

        if change.status == "recorded":
            return change

        if change.status != "proposed":
            raise ValueError(
                "Only proposed changes can be finalized, "
                f"current status: {change.status}"
            )

        policy = ChangePolicyService(
            self.db
        ).evaluate(change)

        self.transition_change(
            change=change,
            new_status=change.status,
            actor_id=change.actor_id,
            event_type="change.policy_evaluated",
            reason=policy.reason,
            metadata={
                "decision": policy.decision,
                "reason": policy.reason,
                "risk_level": change.risk_level,
                "conflict_level": getattr(
                    policy,
                    "conflict_level",
                    "unknown",
                ),
                "dependency_count": getattr(
                    policy,
                    "dependency_count",
                    0,
                ),
                "related_change_ids": getattr(
                    policy,
                    "related_change_ids",
                    [],
                ),
            },
        )

        if policy.decision == ChangePolicyService.BLOCK:

            self.transition_change(
                change=change,
                new_status="blocked",
                actor_id=change.actor_id,
                event_type="change.blocked",
                reason=policy.reason,
            )

            self.db.commit()

            raise ValueError(
                "Change blocked by SUTRA policy: "
                + policy.reason
            )

        if policy.decision == ChangePolicyService.REVIEW:

            if not self._has_approved_review(change):

                self.db.commit()

                raise ValueError(
                    "Change requires an approved review: "
                    + policy.reason
                )

        if policy.decision not in {
            ChangePolicyService.ALLOW,
            ChangePolicyService.REVIEW,
        }:

            self.db.commit()

            raise ValueError(
                "Change rejected because SUTRA returned "
                f"an unknown policy decision: {policy.decision}"
            )

        self.transition_change(
            change=change,
            new_status="recorded",
            actor_id=change.actor_id,
            event_type="change.finalized",
            reason="Change finalized successfully.",
        )

        self.db.commit()
        self.db.refresh(change)

        return change

    # ---------------------------------------------------------
    # GIT HELPERS
    # ---------------------------------------------------------

    def _repo_path(
        self,
        repository: Repository,
    ) -> Path:

        return (
            Path(settings.repository_storage_path).resolve()
            / repository.storage_key
        )

    def _git(
        self,
        repository: Repository,
        *args: str,
    ) -> str:

        repo_path = self._repo_path(repository)

        result = subprocess.run(
            [
                "git",
                "--git-dir",
                str(repo_path),
                *args,
            ],
            capture_output=True,
            text=True,
            check=False,
        )

        if result.returncode != 0:
            raise ValueError(
                result.stderr.strip()
                or "Git operation failed"
            )

        return result.stdout.strip()

    def resolve_commit(
        self,
        repository: Repository,
        revision: str,
    ) -> str:

        if not revision:
            raise ValueError(
                "Commit revision cannot be empty"
            )

        return self._git(
            repository,
            "rev-parse",
            f"{revision}^{{commit}}",
        )

    def verify_ancestor(
        self,
        repository: Repository,
        base_commit: str,
        resulting_commit: str,
    ) -> None:

        result = subprocess.run(
            [
                "git",
                "--git-dir",
                str(self._repo_path(repository)),
                "merge-base",
                "--is-ancestor",
                "--",
                base_commit,
                resulting_commit,
            ],
            capture_output=True,
            text=True,
            check=False,
        )

        if result.returncode != 0:
            raise ValueError(
                "Resulting commit is not based on the change base commit"
            )

    def is_ancestor(
        self,
        repository: Repository,
        base_commit: str,
        resulting_commit: str,
    ) -> bool:

        result = subprocess.run(
            [
                "git",
                "--git-dir",
                str(self._repo_path(repository)),
                "merge-base",
                "--is-ancestor",
                "--",
                base_commit,
                resulting_commit,
            ],
            capture_output=True,
            text=True,
            check=False,
        )

        return result.returncode == 0

    def get_changed_files(
        self,
        repository: Repository,
        base_commit: str,
        resulting_commit: str,
    ) -> list[dict[str, str | int | None]]:
        """
        Return changed files with exact Git additions/deletions.

        Git is the source of truth for file-level statistics.
        """

        name_status_output = self._git(
            repository,
            "diff-tree",
            "-r",
            "-z",
            "--name-status",
            "-M",
            base_commit,
            resulting_commit,
            "--",
        )

        numstat_output = self._git(
            repository,
            "diff-tree",
            "-r",
            "-z",
            "--numstat",
            "-M",
            base_commit,
            resulting_commit,
            "--",
        )

        if not name_status_output:
            return []

        # ---------------------------------------------------------
        # Parse numstat
        #
        # Actual Git -z output:
        #
        #   additions<TAB>deletions<TAB>path<NUL>
        #
        # Example:
        #
        #   2<TAB>0<TAB>src/hello.py<NUL>
        #   9<TAB>0<TAB>tests/test_hello.py<NUL>
        # ---------------------------------------------------------

        stats_by_path: dict[str, tuple[int, int]] = {}

        if numstat_output:
            for record in numstat_output.split("\0"):
                if not record:
                    continue

                fields = record.split("\t", 2)

                if len(fields) != 3:
                    continue

                additions_raw, deletions_raw, path = fields

                additions = (
                    int(additions_raw)
                    if additions_raw.isdigit()
                    else 0
                )

                deletions = (
                    int(deletions_raw)
                    if deletions_raw.isdigit()
                    else 0
                )

                stats_by_path[path] = (
                    additions,
                    deletions,
                )

        # ---------------------------------------------------------
        # Parse name-status
        # ---------------------------------------------------------

        name_parts = [
            part
            for part in name_status_output.split("\0")
            if part
        ]

        files: list[dict[str, str | int | None]] = []
        ns_i = 0

        while ns_i < len(name_parts):
            status = name_parts[ns_i]
            ns_i += 1

            # Rename:
            # R100<NUL>old_path<NUL>new_path<NUL>
            if status.startswith("R"):
                if ns_i + 1 >= len(name_parts):
                    break

                old_path = name_parts[ns_i]
                new_path = name_parts[ns_i + 1]
                ns_i += 2

                additions, deletions = stats_by_path.get(
                    new_path,
                    (0, 0),
                )

                files.append(
                    {
                        "operation": "renamed",
                        "path": new_path,
                        "old_path": old_path,
                        "additions": additions,
                        "deletions": deletions,
                    }
                )

                continue

            if ns_i >= len(name_parts):
                break

            path = name_parts[ns_i]
            ns_i += 1

            operation_map = {
                "A": "added",
                "M": "modified",
                "D": "deleted",
            }

            operation = operation_map.get(
                status[:1],
                "modified",
            )

            additions, deletions = stats_by_path.get(
                path,
                (0, 0),
            )

            files.append(
                {
                    "operation": operation,
                    "path": path,
                    "old_path": None,
                    "additions": additions,
                    "deletions": deletions,
                }
            )

        return files
    # ---------------------------------------------------------
    # SHA-256 OPERATION IDENTITY
    # ---------------------------------------------------------

    @staticmethod
    def _canonical_git_operation(
        repository_id: str,
        actor_id: str,
        ref: str,
        before_commit: str | None,
        after_commit: str | None,
    ) -> str:

        values = {
            "actor_id": actor_id,
            "after_commit": after_commit or "",
            "before_commit": before_commit or "",
            "ref": ref,
            "repository_id": repository_id,
        }

        return json.dumps(
            values,
            separators=(",", ":"),
            sort_keys=True,
            ensure_ascii=True,
        )

    @classmethod
    def _git_push_operation_key(
        cls,
        repository: Repository,
        actor: Actor | tuple,
        ref: str,
        before_commit: str | None,
        after_commit: str | None,
    ) -> str:

        actor = cls._normalize_agent_actor(actor)

        canonical = cls._canonical_git_operation(
            repository_id=repository.id,
            actor_id=actor.id,
            ref=ref,
            before_commit=before_commit,
            after_commit=after_commit,
        )

        return hashlib.sha256(
            canonical.encode("utf-8")
        ).hexdigest()

    # ---------------------------------------------------------
    # REF CLASSIFICATION
    # ---------------------------------------------------------

    def _classify_ref_update(
        self,
        repository: Repository,
        before_commit: str | None,
        after_commit: str | None,
    ) -> str:

        if before_commit is None and after_commit is not None:
            return "create"

        if before_commit is not None and after_commit is None:
            return "delete"

        if (
            before_commit is None
            or after_commit is None
        ):
            return "unknown"

        if before_commit == after_commit:
            return "unchanged"

        if self.is_ancestor(
            repository,
            before_commit,
            after_commit,
        ):
            return "update"

        return "force_update"

    # ---------------------------------------------------------
    # HUMAN / AGENT COMMIT RECORDING
    # ---------------------------------------------------------

    def record_commit(
        self,
        change: Change,
        repository: Repository,
        actor: Actor,
        resulting_commit: str,
    ) -> Change:

        if change.actor_id != actor.id:
            raise ValueError(
                "Actor does not own this change"
            )

        if change.repository_id != repository.id:
            raise ValueError(
                "Change does not belong to this repository"
            )

        if change.status != "proposed":
            raise ValueError(
                "Only proposed changes can be recorded"
            )

        if not change.base_commit:
            raise ValueError(
                "Change has no base commit"
            )

        base_commit = self.resolve_commit(
            repository,
            change.base_commit,
        )

        resolved_resulting = self.resolve_commit(
            repository,
            resulting_commit,
        )

        self.verify_ancestor(
            repository,
            base_commit,
            resolved_resulting,
        )

        files = self.get_changed_files(
            repository,
            base_commit,
            resolved_resulting,
        )

        existing_files = self.db.scalars(
            select(ChangeFile).where(
                ChangeFile.change_id == change.id
            )
        ).all()

        for existing in existing_files:
            self.db.delete(existing)

        for file in files:
            self.db.add(
                ChangeFile(
                    change_id=change.id,
                    path=str(file["path"]),
                    operation=str(file["operation"]),
                    additions=file.get("additions", 0),
                    deletions=file.get("deletions", 0),
                )
            )

        change.base_commit = base_commit
        change.resulting_commit = resolved_resulting

        self.db.flush()

        policy = ChangePolicyService(
            self.db
        ).evaluate(change)

        self.transition_change(
            change=change,
            new_status=change.status,
            actor_id=actor.id,
            event_type="change.policy_evaluated",
            reason=policy.reason,
            metadata={
                "decision": policy.decision,
                "reason": policy.reason,
                "risk_level": change.risk_level,
                "conflict_level": getattr(
                    policy,
                    "conflict_level",
                    "unknown",
                ),
                "dependency_count": getattr(
                    policy,
                    "dependency_count",
                    0,
                ),
                "related_change_ids": getattr(
                    policy,
                    "related_change_ids",
                    [],
                ),
            },
        )

        if policy.decision == ChangePolicyService.BLOCK:

            self.db.rollback()

            raise ValueError(
                "Change blocked by SUTRA policy: "
                + policy.reason
            )

        if policy.decision == ChangePolicyService.REVIEW:

            if not self._has_approved_review(change):
                # When review is required and not yet approved:
                # Evidence (resulting_commit, ChangeFiles, policy evaluation) is persisted,
                # and Change remains in status="proposed" pending human review.
                self.db.commit()
                self.db.refresh(change)
                return change

        if policy.decision not in {
            ChangePolicyService.ALLOW,
            ChangePolicyService.REVIEW,
        }:

            self.db.rollback()

            raise ValueError(
                "Change rejected because SUTRA returned "
                f"an unknown policy decision: {policy.decision}"
            )

        self.transition_change(
            change=change,
            new_status="recorded",
            actor_id=actor.id,
            event_type="change.finalized",
            reason="Policy evaluation allowed and change recorded.",
        )

        self.db.commit()
        self.db.refresh(change)

        return change

        # ---------------------------------------------------------
    # AGENT PUSH RECORDING
    # ---------------------------------------------------------

    @staticmethod
    def _normalize_agent_actor(
        actor: Actor | tuple,
    ) -> Actor:
        """
        Tests and some legacy callers may provide the result of
        make_agent_actor(), which is (Agent, Actor).

        Production callers normally provide Actor directly.

        Normalize both forms without changing the public
        Actor-based contract.
        """

        if isinstance(actor, tuple):

            if len(actor) != 2:
                raise ValueError(
                    "Invalid agent actor tuple"
                )

            first, second = actor

            if isinstance(second, Actor):
                return second

            if isinstance(first, Actor):
                return first

            raise ValueError(
                "Agent actor tuple does not contain an Actor"
            )

        if not isinstance(actor, Actor):
            raise ValueError(
                "Actor must be an agent"
            )

        return actor

    def record_agent_push(
        self,
        repository: Repository,
        actor: Actor | tuple,
        base_commit: str | None,
        resulting_commit: str | None,
        intent: str,
        risk_level: str = "unknown",
        metadata_json: str = "{}",
        commit: bool = True,
        event_id: str | None = None,
    ) -> Change:

        # -----------------------------------------------------
        # NORMALIZE ACTOR
        # -----------------------------------------------------

        actor = self._normalize_agent_actor(actor)

        # -----------------------------------------------------
        # AUTHORITATIVE ACTOR VALIDATION
        # -----------------------------------------------------

        if actor.type != "agent":
            raise ValueError(
                "Actor must be an agent"
            )

        if actor.owner_id != repository.owner_id:
            raise ValueError(
                "Agent does not own this repository"
            )

        # -----------------------------------------------------
        # AUTHORITATIVE AGENT CAPABILITY GATE
        # -----------------------------------------------------

        self._require_agent_capability(
            actor,
            repository,
            AuthorizationService.WRITE,
        )

        self._require_agent_capability(
            actor,
            repository,
            AuthorizationService.CHANGE_CREATE,
        )

        # -----------------------------------------------------
        # DECODE METADATA
        # -----------------------------------------------------

        try:
            metadata = json.loads(metadata_json)
        except Exception:
            metadata = {}

        if not isinstance(metadata, dict):
            metadata = {}

        ref = str(
            metadata.get(
                "ref",
                "",
            )
        )

        if not ref:
            raise ValueError(
                "Git push metadata must contain ref"
            )

        # -----------------------------------------------------
        # RESOLVE COMMITS
        # -----------------------------------------------------

        resolved_base: str | None = None
        resolved_resulting: str | None = None

        if base_commit:
            resolved_base = self.resolve_commit(
                repository,
                base_commit,
            )

        if resulting_commit:
            resolved_resulting = self.resolve_commit(
                repository,
                resulting_commit,
            )

        # -----------------------------------------------------
        # CLASSIFY REF UPDATE
        # -----------------------------------------------------

        operation = self._classify_ref_update(
            repository,
            resolved_base,
            resolved_resulting,
        )

        if operation == "unchanged":
            raise ValueError(
                "Git ref did not change"
            )

        if operation == "force_update":
            raise ValueError(
                "Git force update is not permitted"
            )

        # -----------------------------------------------------
        # AUTHORITATIVE SHA-256 OPERATION IDENTITY
        #
        # IMPORTANT:
        #
        # event_id is deliberately NOT included.
        #
        # The same semantic Git operation must always produce
        # the same Change even if:
        #
        # - the worker retries,
        # - the event is replayed,
        # - multiple transport events describe the same operation.
        #
        # Identity:
        #
        # repository
        # actor
        # ref
        # before commit
        # after commit
        #
        # SHA-256 gives us a stable 256-bit operation identity.
        # -----------------------------------------------------

        operation_key = self._git_push_operation_key(
            repository=repository,
            actor=actor,
            ref=ref,
            before_commit=resolved_base,
            after_commit=resolved_resulting,
        )

        # -----------------------------------------------------
        # FAST IDEMPOTENCY PATH
        # -----------------------------------------------------

        existing = self.db.scalar(
            select(Change).where(
                Change.operation_key == operation_key
            )
        )

        if existing is not None:
            return existing

        # -----------------------------------------------------
        # IMMUTABLE METADATA
        # -----------------------------------------------------

        metadata["operation"] = operation
        metadata["operation_key"] = operation_key

        if event_id is not None:
            metadata["event_id"] = event_id

        # -----------------------------------------------------
        # CREATE CHANGE
        # -----------------------------------------------------

        change = Change(
            repository_id=repository.id,
            actor_id=actor.id,
            intent=intent,
            base_commit=resolved_base,
            resulting_commit=resolved_resulting,
            operation_key=operation_key,
            status="proposed",
            risk_level=risk_level,
            metadata_json=json.dumps(
                metadata,
                separators=(",", ":"),
                sort_keys=True,
            ),
        )

        # -----------------------------------------------------
        # DATABASE CONCURRENCY BOUNDARY
        #
        # SELECT above is only an optimization.
        #
        # Two workers can still reach INSERT simultaneously.
        #
        # The database UNIQUE(operation_key) constraint is the
        # authoritative concurrency guard.
        #
        # begin_nested() creates a SAVEPOINT so a duplicate-key
        # race does not destroy the processor's outer transaction.
        # -----------------------------------------------------

        try:

            with self.db.begin_nested():

                self.db.add(change)
                self.db.flush()

        except IntegrityError:

            existing = self.db.scalar(
                select(Change).where(
                    Change.operation_key == operation_key
                )
            )

            if existing is not None:
                return existing

            raise

        # -----------------------------------------------------
        # AUDIT: CREATED
        # -----------------------------------------------------

        self.transition_change(
            change=change,
            new_status="proposed",
            actor_id=actor.id,
            event_type="change.created",
            reason="Change created from agent Git push.",
            metadata={
                "intent": intent,
                "risk_level": risk_level,
                "ref": ref,
                "operation": operation,
                "operation_key": operation_key,
                "event_id": event_id,
            },
        )

        # -----------------------------------------------------
        # CHANGE FILES
        # -----------------------------------------------------

        if (
            resolved_base
            and resolved_resulting
        ):

            files = self.get_changed_files(
                repository,
                resolved_base,
                resolved_resulting,
            )

            for file in files:

                self.db.add(
                    ChangeFile(
                        change_id=change.id,
                        path=str(file["path"]),
                        operation=str(file["operation"]),
                        additions=int(file.get("additions", 0)),
                        deletions=int(file.get("deletions", 0)),
                    )
                )

        self.db.flush()

        # -----------------------------------------------------
        # POLICY
        # -----------------------------------------------------

        policy = ChangePolicyService(
            self.db
        ).evaluate(change)

        self.transition_change(
            change=change,
            new_status=change.status,
            actor_id=actor.id,
            event_type="change.policy_evaluated",
            reason=policy.reason,
            metadata={
                "decision": policy.decision,
                "reason": policy.reason,
                "risk_level": change.risk_level,
                "conflict_level": getattr(
                    policy,
                    "conflict_level",
                    "unknown",
                ),
                "dependency_count": getattr(
                    policy,
                    "dependency_count",
                    0,
                ),
                "related_change_ids": getattr(
                    policy,
                    "related_change_ids",
                    [],
                ),
                "operation_key": operation_key,
                "event_id": event_id,
            },
        )

        # -----------------------------------------------------
        # BLOCK
        # -----------------------------------------------------

        if policy.decision == ChangePolicyService.BLOCK:

            if commit:
                self.db.rollback()

            raise ValueError(
                "Change blocked by SUTRA policy: "
                + policy.reason
            )

        # -----------------------------------------------------
        # REVIEW
        # -----------------------------------------------------

        if policy.decision == ChangePolicyService.REVIEW:

            if commit:

                self.db.commit()
                self.db.refresh(change)

            return change

        # -----------------------------------------------------
        # UNKNOWN
        # -----------------------------------------------------

        if policy.decision != ChangePolicyService.ALLOW:

            if commit:
                self.db.rollback()

            raise ValueError(
                "Change rejected because SUTRA returned "
                f"an unknown policy decision: {policy.decision}"
            )

        # -----------------------------------------------------
        # FINALIZE
        # -----------------------------------------------------

        self.transition_change(
            change=change,
            new_status="recorded",
            actor_id=actor.id,
            event_type="change.finalized",
            reason="Agent push finalized and recorded.",
            metadata={
                "operation_key": operation_key,
                "event_id": event_id,
            },
        )

        # -----------------------------------------------------
        # TRANSACTION OWNERSHIP
        #
        # Normal callers:
        #     commit=True
        #
        # GitPushEventProcessor:
        #     commit=False
        #
        # This allows one Git event containing multiple refs to
        # succeed or fail atomically.
        # -----------------------------------------------------

        if commit:

            self.db.commit()
            self.db.refresh(change)

        return change