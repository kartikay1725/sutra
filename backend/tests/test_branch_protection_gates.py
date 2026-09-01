from uuid import uuid4

from sqlalchemy import select

from app.models.actor import Actor
from app.models.agent import Agent
from app.models.change import Change
from app.models.change_review import ChangeReview
from app.models.pull_request import PullRequest
from app.models.user import User
from app.services.agent_review_service import AgentReviewService
from app.services.branch_protection_service import (
    BranchProtectionService,
)
from app.services.inline_review_service import (
    InlineReviewService,
)
from app.services.pull_request_service import (
    PullRequestService,
)
from app.services.repository_service import (
    RepositoryService,
)


def _create_human_actor(
    db,
    user: User,
) -> Actor:
    actor = Actor(
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

    db.add(actor)
    db.flush()

    return actor


def setup_bp_gates_fixtures(db):
    user_author = User(
        id=str(uuid4()),
        username=f"bp_gauthor_{uuid4().hex[:8]}",
        email=f"bpgauthor_{uuid4().hex[:8]}@example.com",
        password_hash="hash",
    )

    user_rev1 = User(
        id=str(uuid4()),
        username=f"bp_grev1_{uuid4().hex[:8]}",
        email=f"bpgrev1_{uuid4().hex[:8]}@example.com",
        password_hash="hash",
    )

    user_rev2 = User(
        id=str(uuid4()),
        username=f"bp_grev2_{uuid4().hex[:8]}",
        email=f"bpgrev2_{uuid4().hex[:8]}@example.com",
        password_hash="hash",
    )

    db.add_all(
        [
            user_author,
            user_rev1,
            user_rev2,
        ]
    )
    db.flush()

    # These users are used as PullRequest authors, reviewers, and
    # inline-review actors. Create their human Actor records explicitly.
    _create_human_actor(
        db,
        user_author,
    )

    _create_human_actor(
        db,
        user_rev1,
    )

    _create_human_actor(
        db,
        user_rev2,
    )

    repo = RepositoryService(db).create(
        owner_id=user_author.id,
        name=f"bp_grepo_{uuid4().hex[:8]}",
        description="BP Gates Repo",
        visibility="public",
    )

    agent = Agent(
        id=str(uuid4()),
        owner_id=user_author.id,
        name="bp_gates_agent",
        token_prefix="prefix_bpgate_12",
        token_hash="hash",
        is_active=True,
        status="active",
    )

    db.add(agent)

    actor = Actor(
        id=agent.id,
        owner_id=user_author.id,
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
        intent="BP Gates Change",
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
        user_author.id,
        change.id,
        "BP Gates PR",
        "main",
    )

    db.commit()

    return (
        user_author,
        user_rev1,
        user_rev2,
        agent,
        repo,
        change,
        pr,
    )


def test_gate_19g_approval_counting_semantics(db):
    (
        user_author,
        user_rev1,
        user_rev2,
        agent,
        repo,
        change,
        pr,
    ) = setup_bp_gates_fixtures(db)

    bp_svc = BranchProtectionService(db)

    # Require 2 independent approvals, no author self-approval.
    rule = bp_svc.create_rule(
        repository_id=repo.id,
        actor_user_id=user_author.id,
        branch_pattern="main",
        required_approvals=2,
        allow_author_self_approval=False,
    )

    assert rule is not None

    # 1. Author self-approval attempt should not count.
    rev_author = ChangeReview(
        id=str(uuid4()),
        change_id=change.id,
        requested_by=user_author.id,
        reviewer_id=user_author.id,
        status="approved",
    )

    db.add(rev_author)
    db.commit()

    eval1 = bp_svc.evaluate_pull_request(
        pr.id
    )

    assert eval1["passed"] is False
    assert "insufficient_approvals" in eval1[
        "failed_gates"
    ]

    # 2. Add first valid reviewer approval.
    rev1 = ChangeReview(
        id=str(uuid4()),
        change_id=change.id,
        requested_by=user_author.id,
        reviewer_id=user_rev1.id,
        status="approved",
    )

    db.add(rev1)
    db.commit()

    eval2 = bp_svc.evaluate_pull_request(
        pr.id
    )

    assert eval2["passed"] is False
    assert eval2["actual_approvals"] == 1

    # 3. Add second valid reviewer approval.
    rev2 = ChangeReview(
        id=str(uuid4()),
        change_id=change.id,
        requested_by=user_author.id,
        reviewer_id=user_rev2.id,
        status="approved",
    )

    db.add(rev2)
    db.commit()

    eval3 = bp_svc.evaluate_pull_request(
        pr.id
    )

    assert eval3["passed"] is True
    assert eval3["actual_approvals"] == 2


def test_gate_19h_inline_review_thread_gates(db):
    (
        user_author,
        user_rev1,
        user_rev2,
        agent,
        repo,
        change,
        pr,
    ) = setup_bp_gates_fixtures(db)

    bp_svc = BranchProtectionService(db)
    inline_svc = InlineReviewService(db)

    # Require resolved threads.
    bp_svc.create_rule(
        repository_id=repo.id,
        actor_user_id=user_author.id,
        branch_pattern="main",
        required_approvals=0,
        require_change_review=False,
        require_resolved_threads=True,
    )

    # 1. Create active inline comment.
    comment = inline_svc.create_comment(
        pull_request_id=pr.id,
        author_id=user_rev1.id,
        body="Please fix this function",
        path="src/main.py",
        line_number=10,
    )

    db.commit()

    eval1 = bp_svc.evaluate_pull_request(
        pr.id
    )

    assert eval1["passed"] is False
    assert "unresolved_inline_threads" in eval1[
        "failed_gates"
    ]

    # 2. Resolve comment thread.
    inline_svc.resolve_thread(
        comment.id,
        user_author.id,
    )

    db.commit()

    eval2 = bp_svc.evaluate_pull_request(
        pr.id
    )

    assert eval2["passed"] is True

    # 3. Reopen comment thread.
    inline_svc.reopen_thread(
        comment.id,
        user_rev1.id,
    )

    db.commit()

    eval3 = bp_svc.evaluate_pull_request(
        pr.id
    )

    assert eval3["passed"] is False
    assert "unresolved_inline_threads" in eval3[
        "failed_gates"
    ]


def test_gate_19i_agent_review_findings_gates(db):
    (
        user_author,
        user_rev1,
        user_rev2,
        agent,
        repo,
        change,
        pr,
    ) = setup_bp_gates_fixtures(db)

    bp_svc = BranchProtectionService(db)
    agent_svc = AgentReviewService(db)

    # Require agent review and no blocking agent findings.
    bp_svc.create_rule(
        repository_id=repo.id,
        actor_user_id=user_author.id,
        branch_pattern="main",
        required_approvals=0,
        require_change_review=False,
        require_resolved_threads=False,
        require_agent_review=True,
        require_no_blocking_agent_findings=True,
    )

    # Initially missing agent review.
    eval1 = bp_svc.evaluate_pull_request(
        pr.id
    )

    assert eval1["passed"] is False
    assert "missing_agent_review" in eval1[
        "failed_gates"
    ]

    # Agent posts a CRITICAL finding.
    agent_svc.create_agent_finding(
        agent_id=agent.id,
        pull_request_id=pr.id,
        severity="critical",
        category="security",
        message="Critical security vulnerability found",
    )

    db.commit()

    eval2 = bp_svc.evaluate_pull_request(
        pr.id
    )

    assert eval2["passed"] is False
    assert "unresolved_agent_findings" in eval2[
        "failed_gates"
    ]

    # Agent findings must not create ChangeReview records.
    reviews = db.scalars(
        select(ChangeReview).where(
            ChangeReview.change_id == change.id
        )
    ).all()

    assert len(reviews) == 0