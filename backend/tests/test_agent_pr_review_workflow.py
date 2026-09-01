import os
import subprocess
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import create_access_token
from app.db.session import get_db
from app.main import app
from app.models.actor import Actor
from app.models.agent import Agent
from app.models.change import Change
from app.models.change_review import ChangeReview
from app.models.pull_request import PullRequest
from app.models.repository import Repository
from app.models.user import User
from app.services.pull_request_service import PullRequestService
from app.services.repository_service import RepositoryService


def _run_git(args: list[str], *, cwd: Path, env: dict[str, str] | None = None) -> str:
    process_env = os.environ.copy()
    if env:
        process_env.update(env)
    result = subprocess.run(
        ["git", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=True,
        env=process_env,
    )
    return result.stdout.strip()


def _create_real_git_commit(storage_key: str, message: str = "Test commit") -> tuple[str, str]:
    repo_dir = (
        Path(settings.repository_storage_path).resolve() / storage_key
    ).resolve()

    base_commit = _run_git(
        ["rev-parse", "--verify", "refs/heads/main"],
        cwd=repo_dir,
    )

    tree_sha = _run_git(
        ["rev-parse", f"{base_commit}^{{tree}}"],
        cwd=repo_dir,
    )

    resulting_commit = _run_git(
        [
            "commit-tree",
            tree_sha,
            "-p",
            base_commit,
            "-m",
            message,
        ],
        cwd=repo_dir,
        env={
            "GIT_AUTHOR_NAME": "Agent Tester",
            "GIT_AUTHOR_EMAIL": "agent@sutra.dev",
            "GIT_COMMITTER_NAME": "Agent Tester",
            "GIT_COMMITTER_EMAIL": "agent@sutra.dev",
        },
    )
    return base_commit, resulting_commit


def test_agent_pr_review_workflow_end_to_end(client: TestClient, db: Session):
    # 1. Setup repository owner (human) and a delegated reviewer (human).
    owner = User(
        id=str(uuid4()),
        username=f"owner_{uuid4().hex[:6]}",
        email=f"owner_{uuid4().hex[:6]}@sutra.dev",
        password_hash="hash",
    )
    reviewer = User(
        id=str(uuid4()),
        username=f"reviewer_{uuid4().hex[:6]}",
        email=f"reviewer_{uuid4().hex[:6]}@sutra.dev",
        password_hash="hash",
    )
    db.add_all([owner, reviewer])
    db.flush()

    owner_actor = Actor(
        id=owner.id,
        owner_id=owner.id,
        type="human",
        name=owner.username,
        capabilities='["repository.read", "repository.write", "change.create", "change.review", "change.approve"]',
    )
    reviewer_actor = Actor(
        id=reviewer.id,
        owner_id=reviewer.id,
        type="human",
        name=reviewer.username,
        capabilities='["repository.read", "repository.write", "change.create", "change.review", "change.approve"]',
    )
    db.add_all([owner_actor, reviewer_actor])
    db.flush()

    # 2. Setup Repository.
    repo = RepositoryService(db).create(
        owner_id=owner.id,
        name=f"agent_wf_repo_{uuid4().hex[:6]}",
        description="Agent workflow repo",
        visibility="private",
    )

    # 3. Setup Agent owned by repo owner.
    agent = Agent(
        id=str(uuid4()),
        owner_id=owner.id,
        name="autodev_agent",
        token_prefix="agent_wf_prefix_",
        token_hash="hash",
        status="active",
        is_active=True,
    )
    db.add(agent)
    db.flush()

    agent_actor = Actor(
        id=agent.id,
        owner_id=owner.id,
        type="agent",
        name=agent.name,
        capabilities='["repository.read", "repository.write", "change.create"]',
    )
    db.add(agent_actor)
    db.flush()

    from app.models.agent_repository_access import AgentRepositoryAccess
    access = AgentRepositoryAccess(
        agent_id=agent.id,
        repository_id=repo.id,
        permissions='["repository.read", "repository.write", "change.create"]',
        enabled=True,
    )
    db.add(access)
    db.flush()

    # 4. Agent creates a Change with a real commit.
    base_commit, resulting_commit = _create_real_git_commit(repo.storage_key, "Agent fix")
    change = Change(
        id=str(uuid4()),
        repository_id=repo.id,
        actor_id=agent_actor.id,
        intent="Agent Automated PR Fix",
        base_commit=base_commit,
        resulting_commit=resulting_commit,
        operation_key=(uuid4().hex * 2)[:64],
        status="proposed",
        risk_level="low",
    )
    db.add(change)
    db.commit()

    # 5. Agent creates Pull Request via PullRequestService.
    svc = PullRequestService(db)
    pr = svc.create_pull_request(
        repository_id=repo.id,
        author_id=agent_actor.id,
        source_change_id=change.id,
        title="Agent PR Fix",
        target_branch="main",
        description="Automated fix by agent",
    )
    db.commit()

    assert pr.status == "open"
    assert pr.author_id == agent_actor.id

    # 6. Verify that an authoritative pending review request was automatically created.
    reviews = db.scalars(
        select(ChangeReview).where(ChangeReview.change_id == change.id)
    ).all()

    assert len(reviews) == 1
    review = reviews[0]
    assert review.status == "pending"
    assert review.reviewer_id is None
    assert review.requested_by == repo.owner_id
    assert "Agent PR" in (review.reason or "")

    # 7. Verify human review API (GET /v1/pull-requests/{pr_id}/reviews) returns the pending review.
    from app.models.user_session import UserSession
    from datetime import datetime, timezone, timedelta
    owner_session = UserSession(
        user_id=owner.id,
        expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        status="active",
    )
    db.add(owner_session)
    db.commit()
    owner_token = create_access_token(owner.id, owner_session.id)
    resp_reviews = client.get(
        f"/v1/pull-requests/{pr.id}/reviews",
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert resp_reviews.status_code == status.HTTP_200_OK
    rev_data = resp_reviews.json()
    assert len(rev_data) == 1
    assert rev_data[0]["id"] == review.id
    assert rev_data[0]["status"] == "pending"
    assert rev_data[0]["reviewer_id"] is None

    # 8. Human Reviewer approves the PR (POST /v1/pull-requests/{pr_id}/approve).
    resp_approve = client.post(
        f"/v1/pull-requests/{pr.id}/approve",
        json={"reason": "Verified and approved"},
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert resp_approve.status_code == status.HTTP_200_OK
    assert resp_approve.json()["status"] == "approved"

    # 9. Verify ChangeReview record was transitioned to approved with reviewer set.
    db.refresh(review)
    assert review.status == "approved"
    assert review.reviewer_id == owner.id
    assert review.reviewed_at is not None
    assert review.reason == "Verified and approved"

    # 10. Merge the PR and verify it succeeds.
    resp_merge = client.post(
        f"/v1/pull-requests/{pr.id}/merge",
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert resp_merge.status_code == status.HTTP_200_OK
    assert resp_merge.json()["status"] == "merged"

    db.refresh(pr)
    assert pr.status == "merged"
    assert pr.target_commit == resulting_commit
    assert pr.merged_at is not None
