import json
from types import SimpleNamespace
from unittest.mock import patch

from app.models.actor import Actor
from app.models.change import Change
from app.services.change_policy_service import ChangePolicyService
from app.services.conflict_service import ConflictResult, ConflictService


class FakeScalarResult:
    def __init__(self, value):
        self.value = value

    def all(self):
        return []


class FakeDB:
    def __init__(self, actor, dependencies=None):
        self.actor = actor
        self.dependencies = dependencies or []

    def scalar(self, statement):
        sql_str = str(statement).lower()
        if "from repositories" in sql_str or "repositories." in sql_str:
            from app.models.repository import Repository
            return Repository(
                id="repo-1",
                owner_id=getattr(self.actor, "owner_id", getattr(self.actor, "id", "owner-1")),
                name="test-repo",
                slug="test-repo",
                visibility="private",
            )
        if "from actors" in sql_str or "actors." in sql_str:
            return self.actor
        return None

    def scalars(self, statement):
        result = FakeScalarResult(None)
        result.all = lambda: self.dependencies
        return result


def make_actor(capabilities):
    return Actor(
        id="actor-1",
        type="agent",
        name="Test Agent",
        capabilities=json.dumps(capabilities),
    )


def make_change(
    risk_level="low",
    status="recorded",
    resulting_commit="abcdef1234567",
):
    return Change(
        id="change-1",
        repository_id="repo-1",
        actor_id="actor-1",
        intent="Test change",
        base_commit="1234567890abcdef",
        resulting_commit=resulting_commit,
        status=status,
        risk_level=risk_level,
    )


def conflict(level=ConflictService.LEVEL_NONE):
    return ConflictResult(
        level=level,
        reason="test",
        paths=[],
        related_change_ids=[],
    )


REQUIRED_CAPABILITIES = [
    "repository.read",
    "change.create",
]


def evaluate(change, conflict_level=ConflictService.LEVEL_NONE):
    db = FakeDB(
        make_actor(REQUIRED_CAPABILITIES)
    )

    with patch(
        "app.services.change_policy_service.ConflictService.analyze",
        return_value=conflict(conflict_level),
    ):
        return ChangePolicyService(db).evaluate(change)


def test_clean_low_risk_recorded_change_is_allowed():
    result = evaluate(
        make_change(
            risk_level="low",
            status="recorded",
        )
    )

    assert result.decision == "allow"
    assert result.conflict_level == "none"
    assert result.related_change_ids == []


def test_actual_git_conflict_is_blocked():
    result = evaluate(
        make_change(),
        ConflictService.LEVEL_CONFLICT,
    )

    assert result.decision == "block"
    assert result.conflict_level == "conflict"
    assert (
        "Git detected an actual merge conflict."
        in result.reasons
    )
    assert (
        result.reason
        == "Change is blocked because Git detected "
        "an actual merge conflict."
    )


def test_potential_conflict_requires_review():
    result = evaluate(
        make_change(),
        ConflictService.LEVEL_POTENTIAL,
    )

    assert result.decision == "review"
    assert result.conflict_level == "potential_conflict"


def test_overlapping_change_requires_review():
    result = evaluate(
        make_change(),
        ConflictService.LEVEL_OVERLAP,
    )

    assert result.decision == "review"
    assert result.conflict_level == "overlap"


def test_critical_change_is_blocked():
    result = evaluate(
        make_change(risk_level="critical")
    )

    assert result.decision == "block"
    assert "Critical-risk" in result.reasons[0]


def test_high_risk_change_requires_review():
    result = evaluate(
        make_change(risk_level="high")
    )

    assert result.decision == "review"
    assert "High-risk" in result.reasons[0]


def test_medium_risk_change_requires_review():
    result = evaluate(
        make_change(risk_level="medium")
    )

    assert result.decision == "review"
    assert "Medium-risk" in result.reasons[0]


def test_missing_capability_blocks_change():
    db = FakeDB(
        make_actor(
            ["repository.read"]
        )
    )

    change = make_change()

    with patch(
        "app.services.change_policy_service.ConflictService.analyze",
        return_value=conflict(),
    ):
        result = ChangePolicyService(db).evaluate(change)

    assert result.decision == "block"
    assert (
        "change.create"
        in result.reasons[0]
    )


def test_missing_resulting_commit_requires_review():
    result = evaluate(
        make_change(
            status="proposed",
            resulting_commit=None,
        )
    )

    assert result.decision == "review"
    assert (
        "Change does not have a resulting commit yet."
        in result.reasons
    )


def test_invalid_change_status_requires_review():
    result = evaluate(
        make_change(
            status="rejected",
        )
    )

    assert result.decision == "review"
    assert any(
        "is not eligible for policy evaluation"
        in reason
        for reason in result.reasons
    )


def test_conflict_takes_priority_over_medium_risk():
    result = evaluate(
        make_change(risk_level="medium"),
        ConflictService.LEVEL_CONFLICT,
    )

    assert result.decision == "block"
    assert result.conflict_level == "conflict"


def test_conflict_takes_priority_over_high_risk():
    result = evaluate(
        make_change(risk_level="high"),
        ConflictService.LEVEL_CONFLICT,
    )

    assert result.decision == "block"
    assert result.conflict_level == "conflict"
