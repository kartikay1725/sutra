from datetime import datetime, timezone
from uuid import uuid4
import pytest
from fastapi import status
from sqlalchemy import select

from app.models.actor import Actor
from app.models.agent import Agent
from app.models.change import Change
from app.models.change_file import ChangeFile
from app.models.change_review import ChangeReview
from app.models.pull_request import PullRequest
from app.models.repository import Repository
from app.models.user import User
from app.services.change_policy_service import ChangePolicyService
from app.services.pull_request_service import PullRequestService
from app.services.repository_service import RepositoryService
from tests.conftest import ensure_test_actor


def setup_policy_fixtures(db):
    author = User(
        id=str(uuid4()),
        username=f"policy_author_{uuid4().hex[:8]}",
        email=f"pauthor_{uuid4().hex[:8]}@example.com",
        password_hash="hash",
    )
    db.add(author)

    reviewer = User(
        id=str(uuid4()),
        username=f"policy_reviewer_{uuid4().hex[:8]}",
        email=f"previewer_{uuid4().hex[:8]}@example.com",
        password_hash="hash",
    )
    db.add(reviewer)

    unauthorized_user = User(
        id=str(uuid4()),
        username=f"policy_unauth_{uuid4().hex[:8]}",
        email=f"punauth_{uuid4().hex[:8]}@example.com",
        password_hash="hash",
    )
    db.add(unauthorized_user)
    db.flush()

    ensure_test_actor(db, author)
    ensure_test_actor(db, reviewer)
    ensure_test_actor(db, unauthorized_user)

    repo = RepositoryService(db).create(
        owner_id=author.id,
        name=f"policy_repo_{uuid4().hex[:8]}",
        description="Policy Test Repo",
        visibility="private",
    )

    agent = Agent(
        id=str(uuid4()),
        owner_id=author.id,
        name="policy_agent",
        token_prefix="prefix_policy_123",
        token_hash="hash",
        is_active=True,
        status="active",
    )
    db.add(agent)

    actor = Actor(
        id=agent.id,
        owner_id=author.id,
        type="agent",
        name=agent.name,
        capabilities='["repository.read", "repository.write", "change.create"]',
    )
    db.add(actor)
    db.commit()

    import subprocess
    from pathlib import Path
    from app.core.config import settings

    repo_dir = Path(settings.repository_storage_path) / repo.storage_key

    main_result = subprocess.run(
        [
            "git",
            "--git-dir",
            str(repo_dir),
            "rev-parse",
            "--verify",
            "refs/heads/main",
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    base_commit = main_result.stdout.strip()

    tree_result = subprocess.run(
        [
            "git",
            "--git-dir",
            str(repo_dir),
            "rev-parse",
            f"{base_commit}^{{tree}}",
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    tree_sha = tree_result.stdout.strip()

    def make_real_commit(msg):
        feature_result = subprocess.run(
            [
                "git",
                "--git-dir",
                str(repo_dir),
                "commit-tree",
                tree_sha,
                "-p",
                base_commit,
                "-m",
                msg,
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        return feature_result.stdout.strip()

    # Change with ALLOW policy (low risk, proposed, resulting commit present, no conflicts)
    change_allow = Change(
        id=str(uuid4()),
        repository_id=repo.id,
        actor_id=actor.id,
        intent="ALLOW Change",
        risk_level="low",
        resulting_commit=make_real_commit("ALLOW Change commit"),
        base_commit=base_commit,
        operation_key=(uuid4().hex * 2)[:64],
        status="proposed",
    )
    db.add(change_allow)

    # Change with REVIEW policy (high risk)
    change_review = Change(
        id=str(uuid4()),
        repository_id=repo.id,
        actor_id=actor.id,
        intent="REVIEW Change",
        risk_level="high",
        resulting_commit=make_real_commit("REVIEW Change commit"),
        base_commit=base_commit,
        operation_key=(uuid4().hex * 2)[:64],
        status="proposed",
    )
    db.add(change_review)

    # Change with BLOCK policy (critical risk)
    change_block = Change(
        id=str(uuid4()),
        repository_id=repo.id,
        actor_id=actor.id,
        intent="BLOCK Change",
        risk_level="critical",
        resulting_commit=make_real_commit("BLOCK Change commit"),
        base_commit=base_commit,
        operation_key=(uuid4().hex * 2)[:64],
        status="proposed",
    )
    db.add(change_block)
    db.commit()

    return author, reviewer, unauthorized_user, repo, actor, change_allow, change_review, change_block


def test_policy_allow_permits_valid_pr_operation(db):
    author, reviewer, unauth, repo, actor, change_allow, change_review, change_block = setup_policy_fixtures(db)
    svc = PullRequestService(db)

    # Policy decision is ALLOW
    policy = ChangePolicyService(db).evaluate(change_allow)
    assert policy.decision == ChangePolicyService.ALLOW

    # PR creation succeeds
    pr = svc.create_pull_request(repo.id, author.id, change_allow.id, "ALLOW PR", "main")
    assert pr.status == PullRequest.STATUS_OPEN

    # Create review request and approve
    svc.create_pull_request_review_request(pr, requester_id=author.id)

    # Approval by non-author succeeds for ALLOW policy
    approved_pr = svc.approve_pull_request(pr, approver_id=reviewer.id)
    assert approved_pr.status == PullRequest.STATUS_APPROVED


def test_policy_review_requires_approved_change_review(db):
    author, reviewer, unauth, repo, actor, change_allow, change_review, change_block = setup_policy_fixtures(db)
    svc = PullRequestService(db)

    # Policy decision is REVIEW
    policy = ChangePolicyService(db).evaluate(change_review)
    assert policy.decision == ChangePolicyService.REVIEW

    # PR creation succeeds
    pr = svc.create_pull_request(repo.id, author.id, change_review.id, "REVIEW PR", "main")
    assert pr.status == PullRequest.STATUS_OPEN

    # Approval without ChangeReview fails
    with pytest.raises(ValueError, match="An approved ChangeReview is required"):
        svc.approve_pull_request(pr, approver_id=reviewer.id)

    # Request review and approve
    rev_req = svc.create_pull_request_review_request(pr, requester_id=author.id)
    assert rev_req.status == "pending"

    approved_pr = svc.approve_pull_request(pr, approver_id=reviewer.id)
    assert approved_pr.status == PullRequest.STATUS_APPROVED


def test_policy_block_rejects_pr_creation_and_approval(db):
    author, reviewer, unauth, repo, actor, change_allow, change_review, change_block = setup_policy_fixtures(db)
    svc = PullRequestService(db)

    # Real ChangePolicyService evaluates critical risk change as BLOCK
    policy = ChangePolicyService(db).evaluate(change_block)
    assert policy.decision == ChangePolicyService.BLOCK

    # Creating PR on BLOCK change fails
    with pytest.raises(ValueError, match="Blocked changes cannot enter pull request"):
        svc.create_pull_request(repo.id, author.id, change_block.id, "BLOCK PR", "main")

    # Verify no PR was persisted for change_block
    existing_pr = db.scalar(select(PullRequest).where(PullRequest.source_change_id == change_block.id))
    assert existing_pr is None


def test_policy_block_does_not_mutate_pr_or_create_false_review(db):
    author, reviewer, unauth, repo, actor, change_allow, change_review, change_block = setup_policy_fixtures(db)
    svc = PullRequestService(db)

    # Create PR under ALLOW, then escalate change to BLOCK
    pr = svc.create_pull_request(repo.id, author.id, change_allow.id, "Escalated PR", "main")
    assert pr.status == PullRequest.STATUS_OPEN

    # Change escalated to critical risk (BLOCK)
    change_allow.risk_level = "critical"
    db.commit()

    # Attempted approval fails
    with pytest.raises(ValueError, match="blocked by policy"):
        svc.approve_pull_request(pr, approver_id=reviewer.id)

    # PR remains strictly in OPEN status, no false approval created
    db.refresh(pr)
    assert pr.status == PullRequest.STATUS_OPEN

    # No ChangeReview records created
    reviews = db.scalars(select(ChangeReview).where(ChangeReview.change_id == change_allow.id)).all()
    assert len(reviews) == 0


def test_unauthorized_user_cannot_bypass_policy_or_access_pr(db, client):
    author, reviewer, unauth, repo, actor, change_allow, change_review, change_block = setup_policy_fixtures(db)
    svc = PullRequestService(db)

    pr = svc.create_pull_request(repo.id, author.id, change_allow.id, "Auth PR", "main")

    from app.api.dependencies import get_current_user
    from app.main import app

    app.dependency_overrides[get_current_user] = lambda: unauth

    # Unauthorized user gets 404 for private repository PR (IDOR protection)
    res_get = client.get(f"/v1/pull-requests/{pr.id}")
    assert res_get.status_code == status.HTTP_404_NOT_FOUND

    res_app = client.post(f"/v1/pull-requests/{pr.id}/approve")
    assert res_app.status_code == status.HTTP_404_NOT_FOUND

    app.dependency_overrides.clear()


def test_invalid_lifecycle_transition_and_merged_immutability(db):
    author, reviewer, unauth, repo, actor, change_allow, change_review, change_block = setup_policy_fixtures(db)
    svc = PullRequestService(db)

    pr = svc.create_pull_request(repo.id, author.id, change_allow.id, "Lifecycle PR", "main")
    svc.create_pull_request_review_request(pr, requester_id=author.id)
    svc.approve_pull_request(pr, approver_id=reviewer.id)
    result = svc.merge_pull_request(pr, merger_id=author.id)
    assert result.status in {"merged", "merge_ready"}

    assert pr.status == PullRequest.STATUS_MERGED

    # Merged PR cannot be re-approved, re-opened, or rejected
    with pytest.raises(ValueError, match="Cannot approve PullRequest in status 'merged'"):
        svc.approve_pull_request(pr, approver_id=reviewer.id)

    with pytest.raises(ValueError, match="Cannot transition PullRequest from 'merged' to 'open'"):
        svc.transition_pull_request(pr, PullRequest.STATUS_OPEN)

    with pytest.raises(ValueError, match="Cannot transition PullRequest from 'merged' to 'rejected'"):
        svc.transition_pull_request(pr, PullRequest.STATUS_REJECTED)
