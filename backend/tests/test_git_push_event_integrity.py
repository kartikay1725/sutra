import json
import uuid
from datetime import datetime, timezone

import pytest

from app.services.git_push_event_integrity import (
    GitPushEventIntegrity,
)


def make_payload():
    return {
        "event_id": str(uuid.uuid4()),
        "repository_id": "repo-1",
        "actor_id": "agent-1",
        "before_refs": {
            "refs/heads/main": "a" * 40,
            "refs/heads/feature": "b" * 40,
        },
        "after_refs": {
            "refs/heads/main": "c" * 40,
            "refs/heads/feature": "d" * 40,
        },
        "created_at": datetime(
            2026,
            8,
            14,
            12,
            30,
            45,
            123456,
            tzinfo=timezone.utc,
        ),
    }


def test_hash_is_deterministic():
    payload = make_payload()

    first = GitPushEventIntegrity.fingerprint(
        **payload
    )

    second = GitPushEventIntegrity.fingerprint(
        **payload
    )

    assert first == second
    assert len(first) == 64


def test_hash_is_sha256():
    payload = make_payload()

    value = GitPushEventIntegrity.fingerprint(
        **payload
    )

    assert len(value) == 64

    int(value, 16)


def test_hash_changes_when_event_id_changes():
    payload = make_payload()

    first = GitPushEventIntegrity.fingerprint(
        **payload
    )

    payload["event_id"] = str(uuid.uuid4())

    second = GitPushEventIntegrity.fingerprint(
        **payload
    )

    assert first != second


def test_hash_changes_when_repository_changes():
    payload = make_payload()

    first = GitPushEventIntegrity.fingerprint(
        **payload
    )

    payload["repository_id"] = "repo-attacker"

    second = GitPushEventIntegrity.fingerprint(
        **payload
    )

    assert first != second


def test_hash_changes_when_actor_changes():
    payload = make_payload()

    first = GitPushEventIntegrity.fingerprint(
        **payload
    )

    payload["actor_id"] = "agent-attacker"

    second = GitPushEventIntegrity.fingerprint(
        **payload
    )

    assert first != second


def test_hash_changes_when_before_refs_change():
    payload = make_payload()

    first = GitPushEventIntegrity.fingerprint(
        **payload
    )

    payload["before_refs"][
        "refs/heads/main"
    ] = "e" * 40

    second = GitPushEventIntegrity.fingerprint(
        **payload
    )

    assert first != second


def test_hash_changes_when_after_refs_change():
    payload = make_payload()

    first = GitPushEventIntegrity.fingerprint(
        **payload
    )

    payload["after_refs"][
        "refs/heads/main"
    ] = "e" * 40

    second = GitPushEventIntegrity.fingerprint(
        **payload
    )

    assert first != second


def test_hash_changes_when_created_at_changes():
    payload = make_payload()

    first = GitPushEventIntegrity.fingerprint(
        **payload
    )

    payload["created_at"] = datetime(
        2026,
        8,
        14,
        12,
        30,
        46,
        123456,
        tzinfo=timezone.utc,
    )

    second = GitPushEventIntegrity.fingerprint(
        **payload
    )

    assert first != second


def test_ref_dictionary_order_does_not_change_hash():
    payload = make_payload()

    first = GitPushEventIntegrity.fingerprint(
        **payload
    )

    payload["before_refs"] = {
        "refs/heads/feature": "b" * 40,
        "refs/heads/main": "a" * 40,
    }

    payload["after_refs"] = {
        "refs/heads/feature": "d" * 40,
        "refs/heads/main": "c" * 40,
    }

    second = GitPushEventIntegrity.fingerprint(
        **payload
    )

    assert first == second


def test_domain_and_version_are_present():
    payload = make_payload()

    canonical = GitPushEventIntegrity.canonical_payload(
        **payload
    )

    assert (
        canonical["domain"]
        == "SUTRA-GIT-PUSH-EVENT"
    )

    assert (
        canonical["version"]
        == 1
    )


def test_canonical_json_is_stable():
    payload = make_payload()

    first = GitPushEventIntegrity.canonical_bytes(
        **payload
    )

    second = GitPushEventIntegrity.canonical_bytes(
        **payload
    )

    assert first == second

    decoded = json.loads(
        first.decode("utf-8")
    )

    assert decoded["event_id"] == payload["event_id"]


def test_missing_hash_fails_verification():
    payload = make_payload()

    assert not GitPushEventIntegrity.verify(
        stored_fingerprint=None,
        **payload,
    )


def test_invalid_hash_fails_verification():
    payload = make_payload()

    assert not GitPushEventIntegrity.verify(
        stored_fingerprint="0" * 64,
        **payload,
    )


def test_valid_hash_passes_verification():
    payload = make_payload()

    fingerprint = (
        GitPushEventIntegrity.fingerprint(
            **payload
        )
    )

    assert GitPushEventIntegrity.verify(
        stored_fingerprint=fingerprint,
        **payload,
    )
