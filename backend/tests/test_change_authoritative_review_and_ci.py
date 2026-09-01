from datetime import datetime, timezone
from uuid import uuid4

import pytest
from sqlalchemy import select

from app.core.security import create_access_token
from app.models.actor import Actor
from app.models.change import Change
from app.models.change_file import ChangeFile
from app.models.change_review import ChangeReview
from app.models.ci_job import CIJob
from app.models.pull_request import PullRequest
from app.models.repository import Repository
from app.models.user import User
from app.services.repository_service import RepositoryService
from tests.conftest import ensure_test_actor


def _create_user_and_actor(db, username: str) -> tuple[User, Actor]:
    user = User(
        id=str(uuid4()),
        username=username,
        email=f"{username}@example.com",
        password_hash="hash",
    )
    db.add(user)
    db.flush()

    actor = ensure_test_actor(db, user)
    return user, actor


def setup_test_context(db):
    owner, owner_actor = _create_user_and_actor(db, f"owner_{uuid4().hex[:8]}")
    other_user, other_actor = _create_user_and_actor(db, f"other_{uuid4().hex[:8]}")

    repo = RepositoryService(db).create(
        owner_id=owner.id,
        name=f"test_repo_{uuid4().hex[:8]}",
        description="Test repo",
        visibility="private",
    )

    change = Change(
        id=str(uuid4()),
        repository_id=repo.id,
        actor_id=owner_actor.id,
        intent="Authoritative Change Test",
        risk_level="low",
        resulting_commit="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        base_commit="0000000000000000000000000000000000000000",
        operation_key=(uuid4().hex * 2)[:64],
        status="proposed",
    )
    db.add(change)
    db.flush()

    pr = PullRequest(
        id=str(uuid4()),
        repository_id=repo.id,
        author_id=owner_actor.id,
        source_change_id=change.id,
        title="Test PR for Change",
        target_branch="main",
        status="open",
    )
    db.add(pr)
    db.flush()
    db.commit()

    return owner, other_user, repo, change, pr


def test_change_authoritative_review_approved(db, client):
    owner, _, repo, change, pr = setup_test_context(db)

    # Add approved ChangeReview
    review = ChangeReview(
        id=str(uuid4()),
        change_id=change.id,
        requested_by=owner.id,
        reviewer_id=owner.id,
        status="approved",
        reason="Looks great!",
        reviewed_at=datetime.now(timezone.utc),
    )
    db.add(review)
    db.commit()

    token = create_access_token(subject=owner.id)
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Fetch Change - must link to PR
    res_change = client.get(f"/v1/changes/{change.id}", headers=headers)
    assert res_change.status_code == 200
    data = res_change.json()
    assert data["pull_request_id"] == pr.id
    assert data["pull_request_title"] == pr.title

    # 2. Fetch Reviews - must return authoritative review with status approved
    res_reviews = client.get(f"/v1/changes/{change.id}/reviews", headers=headers)
    assert res_reviews.status_code == 200
    reviews = res_reviews.json()
    assert len(reviews) == 1
    assert reviews[0]["id"] == review.id
    assert reviews[0]["status"] == "approved"
    assert reviews[0]["reviewer_id"] == owner.id


def test_change_authoritative_review_pending(db, client):
    owner, _, repo, change, pr = setup_test_context(db)

    review = ChangeReview(
        id=str(uuid4()),
        change_id=change.id,
        requested_by=owner.id,
        status="pending",
        reason="Agent PR submitted for human review",
    )
    db.add(review)
    db.commit()

    token = create_access_token(subject=owner.id)
    headers = {"Authorization": f"Bearer {token}"}

    res_reviews = client.get(f"/v1/changes/{change.id}/reviews", headers=headers)
    assert res_reviews.status_code == 200
    reviews = res_reviews.json()
    assert len(reviews) == 1
    assert reviews[0]["status"] == "pending"


def test_change_authoritative_review_empty(db, client):
    owner, _, repo, change, pr = setup_test_context(db)

    token = create_access_token(subject=owner.id)
    headers = {"Authorization": f"Bearer {token}"}

    res_reviews = client.get(f"/v1/changes/{change.id}/reviews", headers=headers)
    assert res_reviews.status_code == 200
    reviews = res_reviews.json()
    assert len(reviews) == 0


def test_change_linked_pr_ci_jobs_passed(db, client):
    owner, _, repo, change, pr = setup_test_context(db)

    ci_job = CIJob(
        id=str(uuid4()),
        pull_request_id=pr.id,
        repository_id=repo.id,
        change_id=change.id,
        commit_sha=change.resulting_commit,
        target_branch="main",
        status=CIJob.STATUS_PASSED,
        trigger="pull_request",
        runner_type="isolated_process",
        exit_code=0,
        output_log="CI All checks passed.",
    )
    db.add(ci_job)
    db.commit()

    token = create_access_token(subject=owner.id)
    headers = {"Authorization": f"Bearer {token}"}

    # Fetch Change to get linked PR
    res_change = client.get(f"/v1/changes/{change.id}", headers=headers)
    pr_id = res_change.json()["pull_request_id"]
    assert pr_id == pr.id

    # Fetch CI jobs for PR
    res_ci = client.get(f"/v1/pull-requests/{pr_id}/ci", headers=headers)
    assert res_ci.status_code == 200
    jobs = res_ci.json()
    assert len(jobs) == 1
    assert jobs[0]["status"] == "passed"
    assert jobs[0]["exit_code"] == 0


def test_change_linked_pr_ci_jobs_failed(db, client):
    owner, _, repo, change, pr = setup_test_context(db)

    ci_job = CIJob(
        id=str(uuid4()),
        pull_request_id=pr.id,
        repository_id=repo.id,
        change_id=change.id,
        commit_sha=change.resulting_commit,
        target_branch="main",
        status=CIJob.STATUS_FAILED,
        trigger="pull_request",
        runner_type="isolated_process",
        exit_code=1,
        failure_reason="Unit test failure in test_main.py",
        output_log="FAILED test_main.py",
    )
    db.add(ci_job)
    db.commit()

    token = create_access_token(subject=owner.id)
    headers = {"Authorization": f"Bearer {token}"}

    res_ci = client.get(f"/v1/pull-requests/{pr.id}/ci", headers=headers)
    assert res_ci.status_code == 200
    jobs = res_ci.json()
    assert len(jobs) == 1
    assert jobs[0]["status"] == "failed"
    assert jobs[0]["failure_reason"] == "Unit test failure in test_main.py"


def test_change_linked_pr_ci_jobs_empty(db, client):
    owner, _, repo, change, pr = setup_test_context(db)

    token = create_access_token(subject=owner.id)
    headers = {"Authorization": f"Bearer {token}"}

    res_ci = client.get(f"/v1/pull-requests/{pr.id}/ci", headers=headers)
    assert res_ci.status_code == 200
    jobs = res_ci.json()
    assert len(jobs) == 0


def test_unauthorized_user_cannot_access_change_reviews_or_ci(db, client):
    owner, other_user, repo, change, pr = setup_test_context(db)

    review = ChangeReview(
        id=str(uuid4()),
        change_id=change.id,
        requested_by=owner.id,
        status="approved",
    )
    db.add(review)
    db.commit()

    # unauthorized user token
    token = create_access_token(subject=other_user.id)
    headers = {"Authorization": f"Bearer {token}"}

    # Cannot view private change
    res_change = client.get(f"/v1/changes/{change.id}", headers=headers)
    assert res_change.status_code == 404

    # Cannot view private change reviews
    res_reviews = client.get(f"/v1/changes/{change.id}/reviews", headers=headers)
    assert res_reviews.status_code == 404

    # Cannot view private PR CI
    res_ci = client.get(f"/v1/pull-requests/{pr.id}/ci", headers=headers)
    assert res_ci.status_code in {403, 404}
