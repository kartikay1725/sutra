import hashlib
import json
from datetime import datetime, timezone
from typing import Any


class GitPushEventIntegrity:
    """
    Deterministic integrity fingerprinting for GitPushEvent.

    Design goals:

    - SHA-256 for strong collision resistance.
    - Canonical JSON so equivalent dictionaries produce identical
      byte sequences.
    - Explicit domain separation.
    - Explicit schema versioning.
    - UTC-normalized timestamps.
    - Security-critical immutable event fields are included.
    """

    DOMAIN = "SUTRA-GIT-PUSH-EVENT"
    VERSION = 1
    HASH_ALGORITHM = "sha256"

    @classmethod
    def _canonical_datetime(
        cls,
        value: datetime,
    ) -> str:
        """
        Convert a datetime into a deterministic UTC ISO-8601 string.
        """

        if value.tzinfo is None:
            value = value.replace(
                tzinfo=timezone.utc
            )

        value = value.astimezone(timezone.utc)

        return value.isoformat(
            timespec="microseconds"
        ).replace(
            "+00:00",
            "Z",
        )

    @classmethod
    def canonical_payload(
        cls,
        *,
        event_id: str,
        repository_id: str,
        actor_id: str,
        before_refs: dict[str, str],
        after_refs: dict[str, str],
        created_at: datetime,
    ) -> dict[str, Any]:
        """
        Build the canonical immutable event payload.

        Do not add mutable operational fields such as:

        - status
        - attempts
        - last_error
        - processed_at
        - updated_at

        Those fields describe processing state rather than the
        original Git transport fact.
        """

        return {
            "domain": cls.DOMAIN,
            "version": cls.VERSION,
            "event_id": event_id,
            "repository_id": repository_id,
            "actor_id": actor_id,
            "before_refs": dict(
                sorted(before_refs.items())
            ),
            "after_refs": dict(
                sorted(after_refs.items())
            ),
            "created_at": cls._canonical_datetime(
                created_at
            ),
        }

    @classmethod
    def canonical_bytes(
        cls,
        *,
        event_id: str,
        repository_id: str,
        actor_id: str,
        before_refs: dict[str, str],
        after_refs: dict[str, str],
        created_at: datetime,
    ) -> bytes:
        payload = cls.canonical_payload(
            event_id=event_id,
            repository_id=repository_id,
            actor_id=actor_id,
            before_refs=before_refs,
            after_refs=after_refs,
            created_at=created_at,
        )

        encoded = json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")

        return encoded

    @classmethod
    def fingerprint(
        cls,
        *,
        event_id: str,
        repository_id: str,
        actor_id: str,
        before_refs: dict[str, str],
        after_refs: dict[str, str],
        created_at: datetime,
    ) -> str:
        """
        Return the SHA-256 fingerprint as lowercase hexadecimal.
        """

        canonical = cls.canonical_bytes(
            event_id=event_id,
            repository_id=repository_id,
            actor_id=actor_id,
            before_refs=before_refs,
            after_refs=after_refs,
            created_at=created_at,
        )

        return hashlib.sha256(
            canonical
        ).hexdigest()

    @classmethod
    def verify(
        cls,
        *,
        stored_fingerprint: str | None,
        event_id: str,
        repository_id: str,
        actor_id: str,
        before_refs: dict[str, str],
        after_refs: dict[str, str],
        created_at: datetime,
    ) -> bool:
        """
        Verify an event fingerprint.

        Missing fingerprints are deliberately treated as invalid.
        We never silently generate a replacement fingerprint during
        processing because doing so would erase evidence of a
        potentially modified event.
        """

        if not stored_fingerprint:
            return False

        expected = cls.fingerprint(
            event_id=event_id,
            repository_id=repository_id,
            actor_id=actor_id,
            before_refs=before_refs,
            after_refs=after_refs,
            created_at=created_at,
        )

        return (
            stored_fingerprint.lower()
            == expected.lower()
        )