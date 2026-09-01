from uuid import uuid4

from sqlalchemy import select

from app.models.actor import Actor
from app.models.agent import Agent
from app.models.change import Change
from app.models.ci_job import CIJob
from app.models.pull_request import PullRequest
from app.models.user import User
from app.services.pull_request_service import (
    PullRequestService,
)
from app.services.repository_service import (
    RepositoryService,
)


def setup_ci_model_fixtures(db):
    user = User(
        id=str(uuid4()),
        username=f"ci_muser_{uuid4().hex[:8]}",
        email=f"cimuser_{uuid4().hex[:8]}@example.com",
        password_hash="hash",
    )

    db.add(user)
    db.flush()

    # PullRequestService resolves the PR author through Actor.
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
        name=f"ci_mrepo_{uuid4().hex[:8]}",
        description="CI Model Repo",
        visibility="private",
    )

    agent = Agent(
        id=str(uuid4()),
        owner_id=user.id,
        name="ci_magent",
        token_prefix="prefix_cimag_12",
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
        intent="CI Model Change",
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
        "CI Model PR",
        "main",
    )

    db.commit()

    return user, repo, change, pr


def test_create_ci_job_model(db):
    user, repo, change, pr = (
        setup_ci_model_fixtures(db)
    )

    job = CIJob(
        pull_request_id=pr.id,
        repository_id=repo.id,
        change_id=change.id,
        commit_sha=change.resulting_commit,
        target_branch="main",
        status=CIJob.STATUS_QUEUED,
        trigger="pull_request",
    )

    db.add(job)
    db.commit()

    saved = db.scalar(
        select(CIJob).where(
            CIJob.id == job.id
        )
    )

    assert saved is not None
    assert saved.pull_request_id == pr.id
    assert saved.status == CIJob.STATUS_QUEUED
    assert saved.commit_sha == change.resulting_commit