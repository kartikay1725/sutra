from datetime import datetime, timezone
from uuid import uuid4
import pytest
from fastapi import status
from sqlalchemy import select

from app.models.actor import Actor
from app.models.agent import Agent
from app.models.change import Change
from app.models.change_event import ChangeEvent
from app.models.change_review import ChangeReview
from app.models.pull_request import PullRequest
from app.models.repository import Repository
from app.models.user import User
from app.services.pull_request_service import PullRequestService
from app.services.repository_service import RepositoryService
from tests.conftest import ensure_test_actor


def setup_event_fixtures(db):
    author = User(
        id=str(uuid4()),
        username=f"event_author_{uuid4().hex[:8]}",
        email=f"eauthor_{uuid4().hex[:8]}@example.com",
        password_hash="hash",
    )
    db.add(author)

    reviewer = User(
        id=str(uuid4()),
        username=f"event_reviewer_{uuid4().hex[:8]}",
        email=f"ereviewer_{uuid4().hex[:8]}@example.com",
        password_hash="hash",
    )
    db.add(reviewer)

    unauth = User(
        id=str(uuid4()),
        username=f"event_unauth_{uuid4().hex[:8]}",
        email=f"eunauth_{uuid4().hex[:8]}@example.com",
        password_hash="hash",
    )
    db.add(unauth)
    db.flush()

    ensure_test_actor(db, author)
    ensure_test_actor(db, reviewer)
    ensure_test_actor(db, unauth)

    repo = RepositoryService(db).create(
        owner_id=author.id,
        name=f"event_repo_{uuid4().hex[:8]}",
        description="Event Test Repo",
        visibility="private",
    )

    agent = Agent(
        id=str(uuid4()),
        owner_id=author.id,
        name="event_agent",
        token_prefix="prefix_event_123",
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
            "Event test change",
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    feature_commit = feature_result.stdout.strip()

    change = Change(
        id=str(uuid4()),
        repository_id=repo.id,
        actor_id=actor.id,
        intent="Event Test Change",
        risk_level="low",
        resulting_commit=feature_commit,
        base_commit=base_commit,
        operation_key=(uuid4().hex * 2)[:64],
        status="proposed",
    )
    db.add(change)
    db.commit()

    return author, reviewer, unauth, repo, actor, change


def test_pr_creation_and_opening_events(db):
    author, reviewer, unauth, repo, actor, change = setup_event_fixtures(db)
    svc = PullRequestService(db)

    # Creation of open PR generates created and opened events
    pr = svc.create_pull_request(repo.id, author.id, change.id, "Event PR", "main")

    events = db.scalars(
        select(ChangeEvent)
        .where(ChangeEvent.change_id == change.id)
        .order_by(ChangeEvent.created_at.asc(), ChangeEvent.id.asc())
    ).all()

    event_types = [e.event_type for e in events]
    assert "pull_request.created" in event_types
    assert "pull_request.opened" in event_types

    created_event = next(e for e in events if e.event_type == "pull_request.created")
    assert created_event.actor_id == author.id
    assert created_event.to_status == "open"


def test_pr_approval_rejection_closing_events(db):
    author, reviewer, unauth, repo, actor, change = setup_event_fixtures(db)
    svc = PullRequestService(db)

    pr = svc.create_pull_request(repo.id, author.id, change.id, "Lifecycle Event PR", "main")
    svc.create_pull_request_review_request(pr, requester_id=author.id)
    svc.approve_pull_request(pr, approver_id=reviewer.id, reason="Approved for audit")
    assert pr.status == PullRequest.STATUS_APPROVED

    events = db.scalars(
        select(ChangeEvent)
        .where(ChangeEvent.change_id == change.id)
        .order_by(ChangeEvent.created_at.asc(), ChangeEvent.id.asc())
    ).all()

    approved_event = next(e for e in events if e.event_type == "pull_request.approved")
    assert approved_event.actor_id == reviewer.id
    assert approved_event.from_status == "open"
    assert approved_event.to_status == "approved"
    assert approved_event.reason == "Approved for audit"

    # Close PR
    svc.close_pull_request(pr, user_id=author.id, reason="Closing PR")
    db.refresh(pr)
    assert pr.status == PullRequest.STATUS_CLOSED

    events_updated = db.scalars(
        select(ChangeEvent)
        .where(ChangeEvent.change_id == change.id)
        .order_by(ChangeEvent.created_at.asc(), ChangeEvent.id.asc())
    ).all()

    closed_event = next(e for e in events_updated if e.event_type == "pull_request.closed")
    assert closed_event.actor_id == author.id
    assert closed_event.from_status == "approved"
    assert closed_event.to_status == "closed"


def test_merge_produces_pull_request_merged_event(db):
    author, reviewer, unauth, repo, actor, change = setup_event_fixtures(db)
    svc = PullRequestService(db)

    pr = svc.create_pull_request(repo.id, author.id, change.id, "Merge Event PR", "main")
    svc.create_pull_request_review_request(pr, requester_id=author.id)
    svc.approve_pull_request(pr, approver_id=reviewer.id)

    # Execute merge (returns merged status and produces pull_request.merged event)
    result = svc.merge_pull_request(pr, merger_id=author.id)
    assert result.status == "merged"

    # Verify pull_request.merged event exists
    events = db.scalars(
        select(ChangeEvent).where(
            ChangeEvent.change_id == change.id,
            ChangeEvent.event_type == "pull_request.merged",
        )
    ).all()
    assert len(events) == 1


def test_failed_transition_produces_no_event(db):
    author, reviewer, unauth, repo, actor, change = setup_event_fixtures(db)
    svc = PullRequestService(db)

    pr = svc.create_pull_request(repo.id, author.id, change.id, "Fail Event PR", "main")
    initial_event_count = len(
        db.scalars(select(ChangeEvent).where(ChangeEvent.change_id == change.id)).all()
    )

    # Attempt self-approval (must fail)
    with pytest.raises(ValueError, match="Self-review approval is strictly prohibited"):
        svc.approve_pull_request(pr, approver_id=author.id)

    new_event_count = len(
        db.scalars(select(ChangeEvent).where(ChangeEvent.change_id == change.id)).all()
    )
    assert new_event_count == initial_event_count


def test_audit_read_api_endpoint(db, client):
    author, reviewer, unauth, repo, actor, change = setup_event_fixtures(db)
    svc = PullRequestService(db)

    pr = svc.create_pull_request(repo.id, author.id, change.id, "Audit API PR", "main")

    from app.api.dependencies import get_current_user
    from app.main import app

    # Authorized user reads PR events
    app.dependency_overrides[get_current_user] = lambda: author
    res = client.get(f"/v1/pull-requests/{pr.id}/events")
    assert res.status_code == status.HTTP_200_OK
    data = res.json()
    assert len(data) >= 2
    assert data[0]["event_type"] == "pull_request.created"
    assert data[0]["pull_request_id"] == pr.id

    # Unauthorized user gets 404 (IDOR / private repo isolation)
    app.dependency_overrides[get_current_user] = lambda: unauth
    res_unauth = client.get(f"/v1/pull-requests/{pr.id}/events")
    assert res_unauth.status_code == status.HTTP_404_NOT_FOUND

    app.dependency_overrides.clear()
