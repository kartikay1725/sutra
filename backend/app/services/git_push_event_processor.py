import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.actor import Actor
from app.models.agent import Agent
from app.models.repository import Repository
from app.services.change_service import ChangeService
from app.services.git_push_event_service import GitPushEventService, LeaseLostError


class RetryableError(Exception):
    pass


class PermanentError(Exception):
    pass


class GitPushEventProcessor:
    """
    Consumes persisted Git push events and turns them into
    SUTRA-native Change records.

    A GitPushEvent represents a successful transport operation,
    not permanent authorization to create a Change.

    Processing performs:

        1. Event integrity verification
        2. Repository resolution
        3. Agent/actor reauthorization
        4. Atomic semantic Change creation
        5. Event finalization

    One GitPushEvent is one transaction boundary.
    """

    def __init__(self, db: Session):
        self.db = db
        self.events = GitPushEventService(db)
        self.changes = ChangeService(db)

    # ---------------------------------------------------------
    # PUBLIC PROCESSING API
    # ---------------------------------------------------------

    def process_event(
        self,
        event_id: str,
    ):

        event = self.events.get_event(event_id)

        if event is None:
            raise ValueError(
                f"Git push event '{event_id}' not found"
            )

        if event.status not in {
            GitPushEventService.STATUS_PENDING,
            GitPushEventService.STATUS_FAILED,
        }:
            return event

        self.events.mark_processing(event)
        self.db.commit()

        return self.process_claimed_event(event)

    # ---------------------------------------------------------
    # PROCESSING AUTHORIZATION
    # ---------------------------------------------------------

    def _resolve_authorized_agent(
        self,
        event,
        repository: Repository,
    ) -> Actor:

        actor = self.db.scalar(
            select(Actor).where(
                Actor.id == event.actor_id,
                Actor.type == "agent",
            )
        )

        if actor is None:
            raise PermanentError(
                "Agent actor no longer exists"
            )

        agent = self.db.scalar(
            select(Agent).where(
                Agent.id == actor.id,
            )
        )

        if agent is None:
            raise PermanentError(
                "Agent identity no longer exists"
            )

        if agent.owner_id != repository.owner_id:
            raise PermanentError(
                "Agent does not own repository"
            )

        if actor.owner_id != repository.owner_id:
            raise PermanentError(
                "Agent actor does not own repository"
            )

        if not agent.is_active:
            raise PermanentError(
                "Agent is inactive"
            )

        if agent.status != "active":
            raise PermanentError(
                "Agent is not active"
            )

        if actor.id != agent.id:
            raise PermanentError(
                "Agent actor identity mismatch"
            )

        return actor

    # ---------------------------------------------------------
    # CLAIMED EVENT PROCESSING
    # ---------------------------------------------------------

    def process_claimed_event(
        self,
        event,
        worker_id: str | None = None,
    ):

        try:

            if worker_id is not None:
                self.events.verify_lease(
                    event,
                    worker_id,
                )

            # -------------------------------------------------
            # INTEGRITY BOUNDARY
            # -------------------------------------------------

            try:
                self.events.verify_integrity(event)
            except ValueError as e:
                raise PermanentError(str(e))

            # -------------------------------------------------
            # REPOSITORY
            # -------------------------------------------------

            repository = self.db.scalar(
                select(Repository).where(
                    Repository.id == event.repository_id,
                    Repository.deleted_at.is_(None),
                )
            )

            if repository is None:
                raise PermanentError(
                    "Repository no longer exists"
                )

            # -------------------------------------------------
            # PROCESSING-TIME REAUTHORIZATION
            # -------------------------------------------------

            actor = self._resolve_authorized_agent(
                event=event,
                repository=repository,
            )

            # -------------------------------------------------
            # DECODE IMMUTABLE PAYLOAD
            # -------------------------------------------------

            before_refs = self.events.decode_refs(
                event.before_refs_json
            )

            after_refs = self.events.decode_refs(
                event.after_refs_json
            )

            changed_refs = sorted(
                set(before_refs).union(after_refs)
            )

            # -------------------------------------------------
            # ATOMIC EVENT TRANSACTION
            #
            # Every Change for this event is created with
            # commit=False.
            #
            # Therefore:
            #
            #     ref 1 succeeds
            #     ref 2 fails
            #
            # => BOTH are rolled back.
            # -------------------------------------------------

            for ref in changed_refs:

                old_commit = before_refs.get(ref)
                new_commit = after_refs.get(ref)

                # Deleted refs currently do not produce Changes.
                if new_commit is None:
                    continue

                # No actual ref change.
                if old_commit == new_commit:
                    continue

                branch = ref.removeprefix(
                    "refs/heads/"
                )

                operation = (
                    "create"
                    if old_commit is None
                    else "update"
                )

                metadata = {
                    "source": "git_push_event",
                    "event_id": event.id,
                    "branch": branch,
                    "ref": ref,
                    "operation": operation,
                    "actor_type": "agent",
                    "actor_id": actor.id,
                    "before_commit": old_commit,
                    "after_commit": new_commit,
                }

                intent = (
                    f"Agent Git {operation} "
                    f"on branch '{branch}'."
                )

                if worker_id is not None:
                    self.events.verify_lease(
                        event,
                        worker_id,
                    )

                self.changes.record_agent_push(
                    repository=repository,
                    actor=actor,
                    base_commit=old_commit,
                    resulting_commit=new_commit,
                    intent=intent,
                    risk_level="unknown",
                    metadata_json=json.dumps(
                        metadata,
                        separators=(",", ":"),
                        sort_keys=True,
                    ),
                    commit=False,
                    event_id=event.id,
                )

            # Opportunistic Knowledge Graph indexing on git push
            try:
                from app.services import knowledge_graph_service
                knowledge_graph_service.index_repository_files(
                    db=self.db,
                    repository=repository,
                    commit_sha=new_commit if new_commit != "0" * 40 else "HEAD",
                )
            except Exception:
                pass

            # -------------------------------------------------
            # EVENT FINALIZATION
            # -------------------------------------------------

            self.events.mark_processed(
                event,
                expected_worker_id=worker_id,
            )

            # One commit for:
            #
            # - all Changes
            # - all ChangeFiles
            # - all ChangeEvents
            # - event status
            #
            self.db.commit()

            self.db.refresh(event)

            return event
            
        except LeaseLostError:
            self.db.rollback()
            return event

        except PermanentError as exc:

            # -------------------------------------------------
            # ROLLBACK ALL SEMANTIC WORK
            # -------------------------------------------------

            self.db.rollback()

            failed = self.events.get_event(event.id)

            if failed is None:
                raise

            self.events.mark_failed(
                failed,
                str(exc),
                permanent=True,
                expected_worker_id=worker_id,
            )

            self.db.commit()
            self.db.refresh(failed)

            return failed

        except Exception as exc:

            # -------------------------------------------------
            # ROLLBACK ALL SEMANTIC WORK
            # -------------------------------------------------

            self.db.rollback()

            # -------------------------------------------------
            # RELOAD EVENT AFTER ROLLBACK
            # -------------------------------------------------

            failed = self.events.get_event(
                event.id
            )

            if failed is None:
                raise

            # -------------------------------------------------
            # FAILURE IS A NEW TRANSACTION
            #
            # The semantic transaction above must remain
            # completely rolled back.
            # -------------------------------------------------

            self.events.mark_failed(
                failed,
                str(exc),
                permanent=False,
                expected_worker_id=worker_id,
            )

            self.db.commit()
            self.db.refresh(failed)

            return failed

    # ---------------------------------------------------------
    # BATCH PROCESSING
    # ---------------------------------------------------------

    def process_pending(
        self,
        limit: int = 100,
        stale_timeout_seconds: int = 300,
    ) -> list:

        recovered = (
            self.events.recover_stale_processing(
                timeout_seconds=stale_timeout_seconds
            )
        )

        if recovered:
            self.db.commit()

        events = self.events.claim_pending(
            limit=limit
        )

        self.db.commit()

        processed = []

        for event in events:

            processed.append(
                self.process_claimed_event(event)
            )

        return processed