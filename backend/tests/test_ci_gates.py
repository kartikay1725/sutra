from uuid import uuid4

from sqlalchemy import select

from app.models.actor import Actor
from app.models.agent import Agent
from app.models.change import Change
from app.models.ci_job import CIJob
from app.models.pull_request import PullRequest
from app.models.user import User
from app.services.branch_protection_service import (
    BranchProtectionService,
)
from app.services.ci_service import CIService
from app.services.pull_request_service import (
    PullRequestService,
)
from app.services.repository_service import (
    RepositoryService,
)


def setup_ci_gates_fixtures(db):
    user = User(
        id=str(uuid4()),
        username=f"ci_guser_{uuid4().hex[:8]}",
        email=f"ciguser_{uuid4().hex[:8]}@example.com",
        password_hash="hash",
    )

    db.add(user)
    db.flush()

    # PullRequestService resolves the PR author through Actor.
    # Create the human Actor explicitly rather than relying on a
    # global SQLAlchemy session hook.
    user_actor = Actor(
        id=user.id,
        owner_id=user.id,
        type="human",
        name=user.username,
        capabilities=(
            '["repository.read", '
            '"repository.write", '
            '"change.create", '
            '"change.review", '
            '"change.approve"]'
        ),
    )

    db.add(user_actor)
    db.flush()

    repo = RepositoryService(db).create(
        owner_id=user.id,
        name=f"ci_grepo_{uuid4().hex[:8]}",
        description="CI Gates Repo",
        visibility="private",
    )

    agent = Agent(
        id=str(uuid4()),
        owner_id=user.id,
        name="ci_gagent",
        token_prefix="prefix_cigag_12",
        token_hash="hash",
        is_active=True,
        status="active",
    )

    db.add(agent)

    actor = Actor(
        id=agent.id,
        owner_id=user.id,
        type="agent",
        name=agent.name,
        capabilities=(
            '["repository.read", '
            '"repository.write", '
            '"change.create"]'
        ),
    )

    db.add(actor)
    db.commit()

    change = Change(
        id=str(uuid4()),
        repository_id=repo.id,
        actor_id=actor.id,
        intent="CI Gates Change",
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
        user.id,
        change.id,
        "CI Gates PR",
        "main",
    )

    db.commit()

    return user, repo, change, pr


def test_gate_20h_branch_protection_ci_passed_requirement(db):
    user, repo, change, pr = (
        setup_ci_gates_fixtures(db)
    )

    bp_svc = BranchProtectionService(db)
    ci_svc = CIService(db)

    # Create a rule requiring CI to pass.
    bp_svc.create_rule(
        repository_id=repo.id,
        actor_user_id=user.id,
        branch_pattern="main",
        required_approvals=0,
        require_change_review=False,
        require_resolved_threads=False,
        require_clean_conflict=False,
        require_ci_passed=True,
    )

    # No CI job initially -> gate fails.
    eval1 = bp_svc.evaluate_pull_request(
        pr.id
    )

    assert eval1["passed"] is False
    assert "missing_or_failed_ci" in eval1[
        "failed_gates"
    ]

    # Trigger CI job and execute it.
    job = ci_svc.create_job(
        pr.id,
        user.id,
    )

    ci_svc.run_execution(
        job.id,
        worker_id="test_worker",
    )

    db.commit()

    # Evaluation passes after the correct CI job succeeds.
    eval2 = bp_svc.evaluate_pull_request(
        pr.id
    )

    assert eval2["passed"] is True


def test_stale_commit_ci_rejection(db):
    user, repo, change, pr = (
        setup_ci_gates_fixtures(db)
    )

    bp_svc = BranchProtectionService(db)

    bp_svc.create_rule(
        repository_id=repo.id,
        actor_user_id=user.id,
        branch_pattern="main",
        required_approvals=0,
        require_change_review=False,
        require_clean_conflict=False,
        require_ci_passed=True,
    )

    # Create a passed CI job for a different, stale commit.
    stale_job = CIJob(
        pull_request_id=pr.id,
        repository_id=repo.id,
        change_id=change.id,
        commit_sha=(
            "9999999999999999999999999999999999999999"
        ),
        target_branch="main",
        status=CIJob.STATUS_PASSED,
        trigger="pull_request",
    )

    db.add(stale_job)
    db.commit()

    # The CI gate must fail because the successful CI job belongs
    # to a different commit.
    eval_res = bp_svc.evaluate_pull_request(
        pr.id
    )

    assert eval_res["passed"] is False
    assert "missing_or_failed_ci" in eval_res[
        "failed_gates"
    ]