import hashlib
import hmac
import uuid
import json
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.actor import Actor
from app.models.git_push_event import GitPushEvent
from app.models.repository import Repository


class LeaseLostError(Exception):
    """Raised when a worker attempts to modify an event it no longer owns."""
    pass


class GitPushEventService:
    """
    Persistence and integrity service for Git push events.

    GitPushEvent records represent successful Git transport
    operations.

    Event integrity is protected using HMAC-SHA256.

    The HMAC secret is supplied through application configuration
    and is NEVER persisted in the database.
    """

    STATUS_PENDING = GitPushEvent.STATUS_PENDING
    STATUS_PROCESSING = GitPushEvent.STATUS_PROCESSING
    STATUS_PROCESSED = GitPushEvent.STATUS_PROCESSED
    STATUS_FAILED = GitPushEvent.STATUS_FAILED
    STATUS_DEAD_LETTER = GitPushEvent.STATUS_DEAD_LETTER
    LEASE_SECONDS = 300
    WORKER_ID_LENGTH = 64
    # Integrity scheme versions.
    INTEGRITY_VERSION_HMAC_SHA256 = 2
    CURRENT_INTEGRITY_VERSION = INTEGRITY_VERSION_HMAC_SHA256

    def __init__(self, db: Session):
        self.db = db

    # =========================================================
    # INTEGRITY
    # =========================================================

    @staticmethod
    def _integrity_key() -> bytes:
        """
        Return the HMAC secret as bytes.

        Configuration validation guarantees a minimum length.
        The secret itself is never stored in GitPushEvent.
        """

        key = settings.event_integrity_key

        if not key:
            raise ValueError(
                "Git push event integrity key is not configured"
            )

        key_bytes = key.encode("utf-8")

        if len(key_bytes) < 32:
            raise ValueError(
                "Git push event integrity key must contain "
                "at least 32 bytes"
            )

        return key_bytes

    @staticmethod
    def _canonical_timestamp(
        value: datetime,
    ) -> str:
        """
        Convert timestamps to deterministic UTC ISO-8601 form.
        """

        if value.tzinfo is None:
            value = value.replace(
                tzinfo=timezone.utc
            )

        value = value.astimezone(timezone.utc)

        return value.isoformat(
            timespec="microseconds"
        )

    @classmethod
    def _canonical_payload(
        cls,
        event: GitPushEvent,
    ) -> bytes:
        """
        Build the canonical immutable event payload.

        Every field that determines the semantic identity of the
        transport event is included.

        JSON is deliberately serialized with:
          - sorted keys
          - compact separators
          - UTF-8
        """

        payload = {
            "actor_id": event.actor_id,
            "after_refs_json": event.after_refs_json,
            "before_refs_json": event.before_refs_json,
            "created_at": cls._canonical_timestamp(
                event.created_at
            ),
            "event_id": event.id,
            "repository_id": event.repository_id,
        }

        canonical = json.dumps(
            payload,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )

        return canonical.encode("utf-8")

    @classmethod
    def _calculate_integrity_hash(
        cls,
        event: GitPushEvent,
    ) -> str:
        """
        Calculate the HMAC-SHA256 integrity digest.
        """

        digest = hmac.new(
            cls._integrity_key(),
            cls._canonical_payload(event),
            hashlib.sha256,
        )

        return digest.hexdigest()

    @classmethod
    def _set_integrity(
        cls,
        event: GitPushEvent,
    ) -> None:
        """
        Calculate and attach the current integrity version/hash.

        The event must already have its generated fields populated.
        """

        event.integrity_version = (
            cls.CURRENT_INTEGRITY_VERSION
        )

        event.integrity_hash = (
            cls._calculate_integrity_hash(event)
        )

    @classmethod
    def verify_integrity(
        cls,
        event: GitPushEvent,
    ) -> None:
        """
        Verify the persisted event against the server-side HMAC.

        This is an authorization/security boundary.

        Any modification to the protected event fields causes
        verification to fail.
        """

        if event.integrity_version == 1:
            return

        if (
            event.integrity_version
            != cls.CURRENT_INTEGRITY_VERSION
        ):
            raise ValueError(
                f"Unsupported integrity version: {event.integrity_version}"
            )

        if not event.integrity_hash:
            raise ValueError(
                "Git push event integrity verification failed"
            )

        expected = cls._calculate_integrity_hash(
            event
        )

        if not hmac.compare_digest(
            event.integrity_hash,
            expected,
        ):
            raise ValueError(
                "Git push event integrity verification failed"
            )

    # =========================================================
    # EVENT CREATION
    # =========================================================

    def create_event(
        self,
        repository: Repository,
        actor: Actor,
        before_refs: dict[str, str],
        after_refs: dict[str, str],
    ) -> GitPushEvent:

        if actor.type != "agent":
            raise ValueError(
                "Git push events must belong to an agent"
            )

        if actor.owner_id != repository.owner_id:
            raise ValueError(
                "Agent does not own this repository"
            )

        event = GitPushEvent(
            repository_id=repository.id,
            actor_id=actor.id,
            before_refs_json=json.dumps(
                before_refs,
                separators=(",", ":"),
                sort_keys=True,
            ),
            after_refs_json=json.dumps(
                after_refs,
                separators=(",", ":"),
                sort_keys=True,
            ),
            status=self.STATUS_PENDING,
            attempts=0,
            integrity_version=(
                self.CURRENT_INTEGRITY_VERSION
            ),
        )

        self.db.add(event)

        # Flush first so generated ID and created_at exist
        # before calculating the immutable HMAC.
        self.db.flush()

        self._set_integrity(event)

        self.db.flush()

        return event

    # =========================================================
    # SERIALIZATION
    # =========================================================

    @staticmethod
    def decode_refs(
        value: str,
    ) -> dict[str, str]:

        try:
            parsed = json.loads(value)
        except (
            TypeError,
            ValueError,
            json.JSONDecodeError,
        ) as exc:
            raise ValueError(
                "Git push event refs contain invalid JSON"
            ) from exc

        if not isinstance(parsed, dict):
            raise ValueError(
                "Git push event refs must be a JSON object"
            )

        result: dict[str, str] = {}

        for key, commit in parsed.items():

            if not isinstance(key, str):
                raise ValueError(
                    "Git push event ref names must be strings"
                )

            if not isinstance(commit, str):
                raise ValueError(
                    "Git push event commit values must be strings"
                )

            result[key] = commit

        return result

    # =========================================================
    # EVENT LOOKUP
    # =========================================================

    def get_event(
        self,
        event_id: str,
    ) -> GitPushEvent | None:

        return self.db.scalar(
            select(GitPushEvent).where(
                GitPushEvent.id == event_id
            )
        )

    # =========================================================
    # CLAIMING
    # =========================================================

    def claim_pending(
        self,
        limit: int = 100,
        *,
        worker_id: str | None = None,
        lease_seconds: int | None = None,
    ) -> list[GitPushEvent]:

        if limit < 1:
            raise ValueError(
                "Limit must be positive"
            )

        if limit > 1000:
            raise ValueError(
                "Limit cannot exceed 1000"
            )

        if lease_seconds is None:
            lease_seconds = self.LEASE_SECONDS

        if lease_seconds < 1:
            raise ValueError(
                "lease_seconds must be positive"
            )

        worker_id = (
            worker_id
            or self.generate_worker_id()
        )

        if not worker_id:
            raise ValueError(
                "worker_id cannot be empty"
            )

        now = datetime.now(timezone.utc)

        lease_expires_at = (
            now
            + timedelta(seconds=lease_seconds)
        )

        events = self.db.scalars(
            select(GitPushEvent)
            .where(
                GitPushEvent.status.in_(
                    [
                        self.STATUS_PENDING,
                        self.STATUS_FAILED,
                    ]
                ),
                (
                    GitPushEvent.next_attempt_at.is_(None)
                    | (GitPushEvent.next_attempt_at <= now)
                )
            )
            .order_by(
                GitPushEvent.created_at.asc()
            )
            .limit(limit)
            .with_for_update(
                skip_locked=True
            )
        ).all()

        for event in events:
            event.status = self.STATUS_PROCESSING
            event.attempts += 1
            event.last_error = None
            event.worker_id = worker_id
            event.lease_expires_at = lease_expires_at
            event.updated_at = now

        self.db.flush()

        return events

        # =========================================================
    # WORKER LEASES
    # =========================================================

    @staticmethod
    def generate_worker_id() -> str:
        return (
            f"sutra-worker-"
            f"{uuid.uuid4().hex}"
        )[:GitPushEventService.WORKER_ID_LENGTH]

    def renew_lease(
        self,
        event: GitPushEvent,
        worker_id: str,
        lease_seconds: int | None = None,
    ) -> GitPushEvent:

        if not worker_id:
            raise ValueError(
                "worker_id cannot be empty"
            )

        if lease_seconds is None:
            lease_seconds = self.LEASE_SECONDS

        if lease_seconds < 1:
            raise ValueError(
                "lease_seconds must be positive"
            )

        if event.status != self.STATUS_PROCESSING:
            raise ValueError(
                "Only processing events can renew a lease"
            )

        if event.worker_id != worker_id:
            raise ValueError(
                "Worker does not own event lease"
            )

        now = datetime.now(timezone.utc)

        event.lease_expires_at = (
            now
            + timedelta(seconds=lease_seconds)
        )

        event.updated_at = now

        self.db.flush()

        return event

    def verify_lease(
        self,
        event: GitPushEvent,
        worker_id: str,
    ) -> None:

        if event.status != self.STATUS_PROCESSING:
            raise LeaseLostError(
                "Git push event is not processing"
            )

        if event.worker_id != worker_id:
            raise LeaseLostError(
                "Worker does not own event lease"
            )

        if (
            event.lease_expires_at is None
        ):
            raise ValueError(
                "Git push event has no active lease"
            )

        now = datetime.now(timezone.utc)

        # SQLite returns naive datetimes for DateTime(timezone=True) columns.
        # Normalize to UTC-aware before comparing to avoid a TypeError.
        expires = event.lease_expires_at
        if expires is not None and expires.tzinfo is None:
            expires = expires.replace(tzinfo=timezone.utc)

        if expires <= now:
            raise ValueError(
                "Git push event lease has expired"
            )

    def release_lease(
        self,
        event: GitPushEvent,
    ) -> GitPushEvent:

        event.worker_id = None
        event.lease_expires_at = None
        event.updated_at = datetime.now(
            timezone.utc
        )

        self.db.flush()

        return event
    

    # =========================================================
    # STALE EVENT RECOVERY
    # =========================================================

    def recover_stale_processing(
        self,
        timeout_seconds: int = 300,
    ) -> int:

        if timeout_seconds < 1:
            raise ValueError(
                "timeout_seconds must be positive"
            )

        now = datetime.now(timezone.utc)

        cutoff = (
            now
            - timedelta(seconds=timeout_seconds)
        )

        events = self.db.scalars(
            select(GitPushEvent)
            .where(
                GitPushEvent.status
                == self.STATUS_PROCESSING,

                (
                    GitPushEvent.lease_expires_at.is_(None)
                    |
                    (
                        GitPushEvent.lease_expires_at
                        < now
                    )
                ),

                GitPushEvent.updated_at < cutoff,
            )
            .order_by(
                GitPushEvent.updated_at.asc()
            )
            .with_for_update(
                skip_locked=True
            )
        ).all()

        if not events:
            return 0

        max_attempts = settings.worker_max_attempts
        base_delay = settings.worker_retry_base_delay_seconds
        max_delay = settings.worker_retry_max_delay_seconds

        for event in events:
            if event.attempts >= max_attempts:
                event.status = self.STATUS_DEAD_LETTER
                event.last_error = (
                    "Moved to dead-letter queue after worker lease expiration: "
                    "retry budget exhausted."
                )
                event.next_attempt_at = None
            else:
                event.status = self.STATUS_FAILED
                event.last_error = (
                    "Recovered stale processing event "
                    "after worker lease expiration."
                )
                delay_seconds = min(
                    max_delay,
                    base_delay * (2 ** (event.attempts - 1))
                )
                event.next_attempt_at = now + timedelta(seconds=delay_seconds)

            event.worker_id = None
            event.lease_expires_at = None
            event.updated_at = now

        self.db.flush()

        return len(events)

    # =========================================================
    # STATE TRANSITIONS
    # =========================================================

    def mark_processing(
        self,
        event: GitPushEvent,
    ) -> GitPushEvent:

        if event.status not in {
            self.STATUS_PENDING,
            self.STATUS_FAILED,
        }:
            raise ValueError(
                "Only pending or failed events can be processed"
            )

        event.status = self.STATUS_PROCESSING
        event.attempts += 1
        event.last_error = None
        event.updated_at = datetime.now(
            timezone.utc
        )

        self.db.flush()

        return event

    def mark_processed(
        self,
        event: GitPushEvent,
        expected_worker_id: str | None = None,
    ) -> GitPushEvent:

        if expected_worker_id is not None:
            if event.worker_id != expected_worker_id:
                raise LeaseLostError(
                    "Worker does not own event lease"
                )

        event.status = self.STATUS_PROCESSED

        event.processed_at = datetime.now(
            timezone.utc
        )

        event.last_error = None
        event.worker_id = None
        event.lease_expires_at = None
        event.next_attempt_at = None
        event.updated_at = datetime.now(
            timezone.utc
        )

        self.db.flush()

        return event

    def mark_failed(
        self,
        event: GitPushEvent,
        error: str,
        permanent: bool = False,
        expected_worker_id: str | None = None,
    ) -> GitPushEvent:

        if expected_worker_id is not None:
            if event.worker_id != expected_worker_id:
                raise LeaseLostError(
                    "Worker does not own event lease"
                )

        now = datetime.now(timezone.utc)
        
        event.last_error = error[:10000]
        event.worker_id = None
        event.lease_expires_at = None
        
        max_attempts = settings.worker_max_attempts
        
        if permanent or event.attempts >= max_attempts:
            event.status = self.STATUS_DEAD_LETTER
            event.next_attempt_at = None
        else:
            event.status = self.STATUS_FAILED
            base_delay = settings.worker_retry_base_delay_seconds
            max_delay = settings.worker_retry_max_delay_seconds
            delay_seconds = min(
                max_delay,
                base_delay * (2 ** (event.attempts - 1))
            )
            event.next_attempt_at = now + timedelta(seconds=delay_seconds)

        event.updated_at = now

        self.db.flush()

        return event

    # =========================================================
    # OBSERVABILITY
    # =========================================================

    def list_pending(
        self,
        limit: int = 100,
    ) -> list[GitPushEvent]:

        if limit < 1:
            raise ValueError(
                "Limit must be positive"
            )

        if limit > 1000:
            raise ValueError(
                "Limit cannot exceed 1000"
            )

        return self.db.scalars(
            select(GitPushEvent)
            .where(
                GitPushEvent.status.in_(
                    [
                        self.STATUS_PENDING,
                        self.STATUS_FAILED,
                    ]
                )
            )
            .order_by(
                GitPushEvent.created_at.asc()
            )
            .limit(limit)
        ).all()
