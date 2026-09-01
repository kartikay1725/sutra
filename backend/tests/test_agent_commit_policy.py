import json
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from app.models.actor import Actor
from app.models.change import Change
from app.models.change_file import ChangeFile
from app.models.repository import Repository
from app.services.change_policy_service import ChangePolicyService
from app.services.change_service import ChangeService


class FakeScalarResult:
    def __init__(self, values=None):
        self.values = values or []

    def all(self):
        return self.values


class FakeDB:
    """
    Minimal SQLAlchemy-session-compatible fake used to test
    ChangeService.record_commit() without requiring the full
    application database.
    """

    def __init__(
        self,
        actor,
        existing_files=None,
    ):
        self.actor = actor
        self.existing_files = existing_files or []
        self.added = []
        self.deleted = []
        self.flushed = False
        self.committed = False
        self.rolled_back = False

    def scalar(self, statement):
        return self.actor

    def scalars(self, statement):
        return FakeScalarResult(self.existing_files)

    def add(self, value):
        self.added.append(value)

    def delete(self, value):
        self.deleted.append(value)

    def flush(self):
        self.flushed = True

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True

    def refresh(self, value):
        return None


def make_actor():
    return Actor(
        id="agent-1",
        type="agent",
        name="Policy Test Agent",
        owner_id="owner-1",
        capabilities=json.dumps(
            [
                "repository.read",
                "repository.write",
                "change.create",
                "change.commit",
                "change.conflict.read",
            ]
        ),
    )


def make_repository():
    return Repository(
        id="repo-1",
        owner_id="owner-1",
        name="hello-sutra",
        slug="hello-sutra",
        storage_key="hello-sutra.git",
        default_branch="main",
        visibility="private",
    )


def make_change(
    *,
    status="proposed",
    risk_level="low",
    base_commit="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    resulting_commit=None,
):
    return Change(
        id="change-1",
        repository_id="repo-1",
        actor_id="agent-1",
        intent="Agent policy enforcement test",
        base_commit=base_commit,
        resulting_commit=resulting_commit,
        status=status,
        risk_level=risk_level,
        metadata_json="{}",
    )


def make_change_file():
    return ChangeFile(
        id="file-1",
        change_id="change-1",
        path="README.md",
        operation="modified",
    )


def clean_policy():
    return SimpleNamespace(
        decision=ChangePolicyService.ALLOW,
        reason="Change satisfies the current deterministic SUTRA policy.",
    )


def blocked_policy():
    return SimpleNamespace(
        decision=ChangePolicyService.BLOCK,
        reason="Change is blocked because Git detected an actual merge conflict.",
    )


def review_policy():
    return SimpleNamespace(
        decision=ChangePolicyService.REVIEW,
        reason="Change requires review before it can be treated as safe.",
    )


def test_agent_commit_blocked_by_conflict_rolls_back():
    actor = make_actor()
    repository = make_repository()
    change = make_change()

    db = FakeDB(actor)

    service = ChangeService(db)

    with (
        patch.object(
            service,
            "resolve_commit",
            side_effect=[
                change.base_commit,
                "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
            ],
        ),
        patch.object(
            service,
            "verify_ancestor",
        ),
        patch.object(
            service,
            "get_changed_files",
            return_value=[
                {
                    "path": "README.md",
                    "operation": "modified",
                }
            ],
        ),
        patch(
            "app.services.change_service.ChangePolicyService.evaluate",
            return_value=blocked_policy(),
        ),
    ):
        with pytest.raises(
            ValueError,
            match="Change blocked by SUTRA policy",
        ):
            service.record_commit(
                change=change,
                repository=repository,
                actor=actor,
                resulting_commit="bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
            )

    assert db.rolled_back is True
    assert db.committed is False

    # The Change status must not be finalized.
    assert change.status == "proposed"


def test_agent_commit_allowed_records_change():
    actor = make_actor()
    repository = make_repository()
    change = make_change()

    db = FakeDB(actor)

    service = ChangeService(db)

    resulting_commit = (
        "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
    )

    with (
        patch.object(
            service,
            "resolve_commit",
            side_effect=[
                change.base_commit,
                resulting_commit,
            ],
        ),
        patch.object(
            service,
            "verify_ancestor",
        ),
        patch.object(
            service,
            "get_changed_files",
            return_value=[
                {
                    "path": "README.md",
                    "operation": "modified",
                }
            ],
        ),
        patch(
            "app.services.change_service.ChangePolicyService.evaluate",
            return_value=clean_policy(),
        ),
    ):
        result = service.record_commit(
            change=change,
            repository=repository,
            actor=actor,
            resulting_commit=resulting_commit,
        )

    assert result is change

    assert db.committed is True
    assert db.rolled_back is False

    assert change.status == "recorded"
    assert change.base_commit == (
        "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
    )
    assert change.resulting_commit == resulting_commit

    added_files = [
        value
        for value in db.added
        if isinstance(value, ChangeFile)
    ]

    assert len(added_files) == 1
    assert added_files[0].path == "README.md"
    assert added_files[0].operation == "modified"


def test_agent_commit_invalid_ancestry_is_rejected_without_mutation():
    actor = make_actor()
    repository = make_repository()
    change = make_change()

    db = FakeDB(actor)

    service = ChangeService(db)

    with (
        patch.object(
            service,
            "resolve_commit",
            side_effect=[
                change.base_commit,
                "cccccccccccccccccccccccccccccccccccccccc",
            ],
        ),
        patch.object(
            service,
            "verify_ancestor",
            side_effect=ValueError(
                "Resulting commit is not based on the change base commit"
            ),
        ),
    ):
        with pytest.raises(
            ValueError,
            match="Resulting commit is not based on the change base commit",
        ):
            service.record_commit(
                change=change,
                repository=repository,
                actor=actor,
                resulting_commit=(
                    "cccccccccccccccccccccccccccccccccccccccc"
                ),
            )

    assert db.committed is False
    assert db.rolled_back is False

    assert change.status == "proposed"
    assert change.resulting_commit is None


def test_agent_commit_wrong_actor_is_rejected():
    actor = make_actor()
    repository = make_repository()
    change = make_change()

    wrong_actor = Actor(
        id="agent-2",
        type="agent",
        name="Wrong Agent",
        owner_id="owner-1",
        capabilities=json.dumps(
            [
                "repository.read",
                "change.create",
            ]
        ),
    )

    db = FakeDB(actor)

    service = ChangeService(db)

    with pytest.raises(
        ValueError,
        match="Actor does not own this change",
    ):
        service.record_commit(
            change=change,
            repository=repository,
            actor=wrong_actor,
            resulting_commit=(
                "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
            ),
        )

    assert db.committed is False
    assert change.status == "proposed"
    assert change.resulting_commit is None


def test_agent_commit_wrong_repository_is_rejected():
    actor = make_actor()
    repository = make_repository()
    change = make_change()

    wrong_repository = make_repository()
    wrong_repository.id = "repo-2"

    db = FakeDB(actor)

    service = ChangeService(db)

    with pytest.raises(
        ValueError,
        match="Change does not belong to this repository",
    ):
        service.record_commit(
            change=change,
            repository=wrong_repository,
            actor=actor,
            resulting_commit=(
                "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
            ),
        )

    assert db.committed is False
    assert change.status == "proposed"
    assert change.resulting_commit is None