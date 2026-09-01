from uuid import uuid4

from sqlalchemy import select

from app.models.actor import Actor
from app.models.agent import Agent
from app.models.change import Change
from app.models.change_review import ChangeReview
from app.models.pull_request import PullRequest
from app.models.user import User
from app.services.branch_protection_service import (
    BranchProtectionService,
)
from app.services.pull_request_service import (
    PullRequestService,
)
from app.services.repository_service import (
    RepositoryService,
)


def setup_bp_service_fixtures(db):
    user_owner = User(
        id=str(uuid4()),
        username=f"bp_owner_{uuid4().hex[:8]}",
        email=f"bpowner_{uuid4().hex[:8]}@example.com",
        password_hash="hash",
    )

    user_reviewer = User(
        id=str(uuid4()),
        username=f"bp_rev_{uuid4().hex[:8]}",
        email=f"bprev_{uuid4().hex[:8]}@example.com",
        password_hash="hash",
    )

    db.add_all(
        [
            user_owner,
            user_reviewer,
        ]
    )
    db.flush()

    # PullRequestService resolves human authors through Actor.
    user_owner_actor = Actor(
        id=user_owner.id,
        owner_id=user_owner.id,
        type="human",
        name=user_owner.username,
        capabilities=(
            '["repository.read", '
            '"repository.write", '
            '"change.create", '
            '"change.review", '
            '"change.approve"]'
        ),
    )

    user_reviewer_actor = Actor(
        id=user_reviewer.id,
        owner_id=user_reviewer.id,
        type="human",
        name=user_reviewer.username,
        capabilities=(
            '["repository.read", '
            '"repository.write", '
            '"change.create", '
            '"change.review", '
            '"change.approve"]'
        ),
    )

    db.add_all(
        [
            user_owner_actor,
            user_reviewer_actor,
        ]
    )
    db.flush()

    repo = RepositoryService(db).create(
        owner_id=user_owner.id,
        name=f"bp_srepo_{uuid4().hex[:8]}",
        description="BP Service Repo",
        visibility="private",
    )

    agent = Agent(
        id=str(uuid4()),
        owner_id=user_owner.id,
        name="bp_agent",
        token_prefix="prefix_bp_12345",
        token_hash="hash",
        is_active=True,
        status="active",
    )
    db.add(agent)

    actor = Actor(
        id=agent.id,
        owner_id=user_owner.id,
        type="agent",
        name=agent.name,
        capabilities=(
            '["repository.read", '
            '"repository.write", '
            '"change.create", '
            '"change.review", '
            '"change.approve"]'
        ),
    )
    db.add(actor)
    db.commit()

    change = Change(
        id=str(uuid4()),
        repository_id=repo.id,
        actor_id=actor.id,
        intent="BP Service Change",
        risk_level="low",
        resulting_commit=(
            "1111111111111111111111111111111111111111"
        ),
        base_commit=(
            "0000000000000000000000000000000000000000"
        ),
        operation_key=(uuid4().hex * 2)[:64],
        status="proposed",
    )
    db.add(change)
    db.commit()

    pr_svc = PullRequestService(db)

    pr = pr_svc.create_pull_request(
        repo.id,
        user_owner.id,
        change.id,
        "BP Service PR",
        "main",
    )
    db.commit()

    return (
        user_owner,
        user_reviewer,
        repo,
        change,
        pr,
    )


def test_branch_protection_crud_and_matching(db):
    (
        user_owner,
        user_reviewer,
        repo,
        change,
        pr,
    ) = setup_bp_service_fixtures(db)

    svc = BranchProtectionService(db)

    # 1. Create rule for main.
    rule = svc.create_rule(
        repository_id=repo.id,
        actor_user_id=user_owner.id,
        branch_pattern="main",
        required_approvals=2,
    )

    assert rule is not None
    assert rule.required_approvals == 2

    # 2. Resolve effective rule for main.
    eff = svc.get_effective_rule(
        repo.id,
        "main",
    )

    assert eff is not None
    assert eff.id == rule.id

    # 3. Resolve effective rule for dev.
    eff_dev = svc.get_effective_rule(
        repo.id,
        "dev",
    )

    assert eff_dev is None

    # 4. Create wildcard rule for release/*.
    rule_wc = svc.create_rule(
        repository_id=repo.id,
        actor_user_id=user_owner.id,
        branch_pattern="release/*",
        required_approvals=1,
    )

    eff_rel = svc.get_effective_rule(
        repo.id,
        "release/v1.0",
    )

    assert eff_rel is not None
    assert eff_rel.id == rule_wc.id


def test_branch_protection_pr_evaluation(db):
    (
        user_owner,
        user_reviewer,
        repo,
        change,
        pr,
    ) = setup_bp_service_fixtures(db)

    svc = BranchProtectionService(db)

    rule = svc.create_rule(
        repository_id=repo.id,
        actor_user_id=user_owner.id,
        branch_pattern="main",
        required_approvals=1,
        require_change_review=True,
        require_resolved_threads=False,
        require_clean_conflict=False,
    )

    # Initially no reviews exist.
    eval_res = svc.evaluate_pull_request(
        pr.id
    )

    assert eval_res["passed"] is False
    assert "missing_change_review" in eval_res[
        "failed_gates"
    ]
    assert "insufficient_approvals" in eval_res[
        "failed_gates"
    ]

    # Add approved ChangeReview by reviewer.
    review = ChangeReview(
        id=str(uuid4()),
        change_id=change.id,
        requested_by=user_owner.id,
        reviewer_id=user_reviewer.id,
        status="approved",
    )

    db.add(review)
    db.commit()

    # Re-evaluate.
    eval_res2 = svc.evaluate_pull_request(
        pr.id
    )

    assert eval_res2["passed"] is True
    assert len(
        eval_res2["failed_gates"]
    ) == 0