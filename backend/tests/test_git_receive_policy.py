import json

from app.services.change_policy_service import ChangePolicyService
from app.services.git_receive_policy_service import (
    GitReceivePolicyService,
    RefUpdateProposal,
)


class Obj:
    pass


def make_repository():
    repo = Obj()
    repo.id = "repo-1"
    repo.owner_id = "owner-1"
    return repo


def make_actor(capabilities):
    actor = Obj()
    actor.id = "agent-1"
    actor.type = "agent"
    actor.owner_id = "owner-1"
    actor.capabilities = json.dumps(capabilities)
    return actor


def proposal(*, operation="update", forced=False):
    return RefUpdateProposal(
        before_commit="a" * 40,
        after_commit="b" * 40,
        ref="refs/heads/main",
        operation=operation,
        forced=forced,
    )


def test_normal_agent_receive_is_allowed():
    decision = GitReceivePolicyService(None).evaluate(
        make_repository(),
        make_actor(["repository.read", "repository.write"]),
        [proposal()],
    )

    assert decision.decision == ChangePolicyService.ALLOW
    assert decision.reasons == []


def test_missing_write_capability_is_blocked():
    decision = GitReceivePolicyService(None).evaluate(
        make_repository(),
        make_actor(["repository.read"]),
        [proposal()],
    )

    assert decision.decision == ChangePolicyService.BLOCK
    assert "repository.write" in decision.reason


def test_force_update_is_blocked_before_ref_update():
    decision = GitReceivePolicyService(None).evaluate(
        make_repository(),
        make_actor(["repository.read", "repository.write"]),
        [proposal(forced=True)],
    )

    assert decision.decision == ChangePolicyService.BLOCK
    assert "Force update" in decision.reason


def test_branch_delete_is_blocked_before_ref_update():
    update = RefUpdateProposal(
        before_commit="a" * 40,
        after_commit=None,
        ref="refs/heads/feature",
        operation="delete",
    )

    decision = GitReceivePolicyService(None).evaluate(
        make_repository(),
        make_actor(["repository.read", "repository.write"]),
        [update],
    )

    assert decision.decision == ChangePolicyService.BLOCK
    assert "Branch deletion" in decision.reason


def test_all_ref_updates_are_evaluated_atomically():
    decision = GitReceivePolicyService(None).evaluate(
        make_repository(),
        make_actor(["repository.read", "repository.write"]),
        [proposal(), proposal(forced=True)],
    )

    assert decision.decision == ChangePolicyService.BLOCK
    assert len(decision.reasons) == 1

def test_wrong_owner_agent_is_blocked():
    repository = make_repository()

    actor = make_actor(
        [
            "repository.read",
            "repository.write",
        ]
    )

    actor.owner_id = "different-owner"

    decision = GitReceivePolicyService(None).evaluate(
        repository,
        actor,
        [proposal()],
    )

    assert decision.decision == ChangePolicyService.BLOCK
    assert (
        "does not own the target repository"
        in decision.reason
    )


def test_non_agent_actor_is_blocked():
    repository = make_repository()

    actor = make_actor(
        [
            "repository.read",
            "repository.write",
        ]
    )

    actor.type = "human"

    decision = GitReceivePolicyService(None).evaluate(
        repository,
        actor,
        [proposal()],
    )

    assert decision.decision == ChangePolicyService.BLOCK
    assert "Only agent actors" in decision.reason


def test_non_head_ref_is_blocked():
    decision = GitReceivePolicyService(None).evaluate(
        make_repository(),
        make_actor(
            [
                "repository.read",
                "repository.write",
            ]
        ),
        [
            RefUpdateProposal(
                before_commit="a" * 40,
                after_commit="b" * 40,
                ref="refs/tags/v1.0.0",
                operation="update",
            )
        ],
    )

    assert decision.decision == ChangePolicyService.BLOCK
    assert "outside the supported heads namespace" in decision.reason


def test_branch_creation_is_allowed():
    decision = GitReceivePolicyService(None).evaluate(
        make_repository(),
        make_actor(
            [
                "repository.read",
                "repository.write",
            ]
        ),
        [
            RefUpdateProposal(
                before_commit=None,
                after_commit="b" * 40,
                ref="refs/heads/feature",
                operation="create",
            )
        ],
    )

    assert decision.decision == ChangePolicyService.ALLOW
    assert decision.reasons == []


def test_multiple_invalid_updates_are_all_reported():
    updates = [
        RefUpdateProposal(
            before_commit="a" * 40,
            after_commit=None,
            ref="refs/heads/main",
            operation="delete",
        ),
        RefUpdateProposal(
            before_commit="a" * 40,
            after_commit="b" * 40,
            ref="refs/heads/feature",
            operation="update",
            forced=True,
        ),
        RefUpdateProposal(
            before_commit="a" * 40,
            after_commit="b" * 40,
            ref="refs/tags/v1",
            operation="update",
        ),
    ]

    decision = GitReceivePolicyService(None).evaluate(
        make_repository(),
        make_actor(
            [
                "repository.read",
                "repository.write",
            ]
        ),
        updates,
    )

    assert decision.decision == ChangePolicyService.BLOCK
    assert len(decision.reasons) == 3