from datetime import datetime, timezone
from uuid import uuid4
import pytest
from fastapi import status
from sqlalchemy import select

from app.models.actor import Actor
from app.models.agent import Agent
from app.models.change import Change
from app.models.change_review import ChangeReview
from app.models.pull_request import PullRequest
from app.models.repository import Repository
from app.models.user import User
from app.services.change_policy_service import ChangePolicyService
from app.services.pull_request_service import PullRequestService
from app.services.repository_service import RepositoryService
from tests.conftest import ensure_test_actor


def setup_pr_review_fixtures(db):
    author = User(
        id=str(uuid4()),
        username=f"author_{uuid4().hex[:8]}",
        email=f"author_{uuid4().hex[:8]}@example.com",
        password_hash="hash",
    )
    db.add(author)

    reviewer = User(
        id=str(uuid4()),
        username=f"reviewer_{uuid4().hex[:8]}",
        email=f"reviewer_{uuid4().hex[:8]}@example.com",
        password_hash="hash",
    )
    db.add(reviewer)

    unauthorized_user = User(
        id=str(uuid4()),
        username=f"unauth_{uuid4().hex[:8]}",
        email=f"unauth_{uuid4().hex[:8]}@example.com",
        password_hash="hash",
    )
    db.add(unauthorized_user)
    db.flush()

    ensure_test_actor(db, author)
    ensure_test_actor(db, reviewer)
    ensure_test_actor(db, unauthorized_user)

    repo = RepositoryService(db).create(
        owner_id=author.id,
        name=f"pr_review_repo_{uuid4().hex[:8]}",
        description="PR review integration repo",
        visibility="private",
    )

    agent = Agent(
        id=str(uuid4()),
        owner_id=author.id,
        name="pr_review_agent",
        token_prefix="prefix_review_123",
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

    change = Change(
        id=str(uuid4()),
        repository_id=repo.id,
        actor_id=actor.id,
        intent="Review Test Change",
        resulting_commit="1111111111111111111111111111111111111111",
        base_commit="0000000000000000000000000000000000000000",
        operation_key=(uuid4().hex * 2)[:64],
        status="proposed",
    )
    db.add(change)
    db.commit()

    svc = PullRequestService(db)
    pr = svc.create_pull_request(repo.id, author.id, change.id, "PR Review Test", "main")

    return author, reviewer, unauthorized_user, repo, actor, change, pr


def test_pr_approval_with_no_change_review(db):
    author, reviewer, unauth, repo, actor, change, pr = setup_pr_review_fixtures(db)
    svc = PullRequestService(db)

    # PR approval without ChangeReview must fail
    with pytest.raises(ValueError, match="An approved ChangeReview is required"):
        svc.approve_pull_request(pr, approver_id=reviewer.id)


def test_pr_approval_with_pending_change_review(db):
    author, reviewer, unauth, repo, actor, change, pr = setup_pr_review_fixtures(db)
    svc = PullRequestService(db)

    review = svc.create_pull_request_review_request(pr, requester_id=author.id, reason="Please review")
    assert review.status == "pending"

    # Approving PR approves pending ChangeReview
    approved_pr = svc.approve_pull_request(pr, approver_id=reviewer.id, reason="LGTM")
    assert approved_pr.status == PullRequest.STATUS_APPROVED

    # Verify ChangeReview state in DB
    db.refresh(review)
    assert review.status == "approved"
    assert review.reviewer_id == reviewer.id
    assert review.reviewed_at is not None


def test_pr_approval_with_already_approved_change_review(db):
    author, reviewer, unauth, repo, actor, change, pr = setup_pr_review_fixtures(db)
    svc = PullRequestService(db)

    review = ChangeReview(
        change_id=change.id,
        requested_by=author.id,
        reviewer_id=reviewer.id,
        status="approved",
        reason="Pre-approved",
        reviewed_at=datetime.now(timezone.utc),
    )
    db.add(review)
    db.commit()

    approved_pr = svc.approve_pull_request(pr, approver_id=reviewer.id)
    assert approved_pr.status == PullRequest.STATUS_APPROVED


def test_pr_approval_with_rejected_change_review(db):
    author, reviewer, unauth, repo, actor, change, pr = setup_pr_review_fixtures(db)
    svc = PullRequestService(db)

    review = ChangeReview(
        change_id=change.id,
        requested_by=author.id,
        reviewer_id=reviewer.id,
        status="rejected",
        reason="Needs work",
        reviewed_at=datetime.now(timezone.utc),
    )
    db.add(review)
    db.commit()

    with pytest.raises(ValueError, match="ChangeReview has been rejected"):
        svc.approve_pull_request(pr, approver_id=reviewer.id)


def test_self_approval_prohibition(db):
    author, reviewer, unauth, repo, actor, change, pr = setup_pr_review_fixtures(db)
    svc = PullRequestService(db)

    review = svc.create_pull_request_review_request(pr, requester_id=author.id)

    # Author cannot approve their own PR/review
    with pytest.raises(ValueError, match="A reviewer cannot approve their own review request"):
        svc.approve_pull_request(pr, approver_id=author.id)


def test_policy_block_prevents_approval(db):
    author, reviewer, unauth, repo, actor, change, pr = setup_pr_review_fixtures(db)
    svc = PullRequestService(db)

    review = svc.create_pull_request_review_request(pr, requester_id=author.id)

    # Set risk_level to critical to trigger policy BLOCK
    change.risk_level = "critical"
    db.commit()

    with pytest.raises(ValueError, match="blocked by policy"):
        svc.approve_pull_request(pr, approver_id=reviewer.id)


def test_unauthorized_user_cannot_access_or_approve_pr_review(db, client):
    author, reviewer, unauth, repo, actor, change, pr = setup_pr_review_fixtures(db)

    from app.api.dependencies import get_current_user
    from app.main import app

    app.dependency_overrides[get_current_user] = lambda: unauth

    # Unauthorized review request returns 404/403
    res_req = client.post(f"/v1/pull-requests/{pr.id}/reviews", json={"reason": "Unauth review"})
    assert res_req.status_code in {status.HTTP_403_FORBIDDEN, status.HTTP_404_NOT_FOUND}

    # Unauthorized approve returns 404 Not Found (private repo isolation)
    res_app = client.post(f"/v1/pull-requests/{pr.id}/approve")
    assert res_app.status_code == status.HTTP_404_NOT_FOUND

    app.dependency_overrides.clear()


def test_no_duplicate_review_tables_or_records(db):
    author, reviewer, unauth, repo, actor, change, pr = setup_pr_review_fixtures(db)
    svc = PullRequestService(db)

    svc.create_pull_request_review_request(pr, requester_id=author.id)
    svc.approve_pull_request(pr, approver_id=reviewer.id)

    # Verify only ChangeReview rows exist for change.id
    reviews = db.scalars(select(ChangeReview).where(ChangeReview.change_id == change.id)).all()
    assert len(reviews) == 1
    assert reviews[0].status == "approved"
    assert reviews[0].reviewer_id == reviewer.id
