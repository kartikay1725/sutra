from uuid import uuid4

from fastapi import status

from app.models.actor import Actor
from app.models.agent import Agent
from app.models.change import Change
from app.models.ci_job import CIJob
from app.models.user import User
from app.services.ci_service import CIService
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


def setup_ci_service_fixtures(db):
    user_a = User(
        id=str(uuid4()),
        username=f"ci_suser_a_{uuid4().hex[:8]}",
        email=f"cisusera_{uuid4().hex[:8]}@example.com",
        password_hash="hash",
    )

    user_b = User(
        id=str(uuid4()),
        username=f"ci_suser_b_{uuid4().hex[:8]}",
        email=f"cisuserb_{uuid4().hex[:8]}@example.com",
        password_hash="hash",
    )

    db.add_all(
        [
            user_a,
            user_b,
        ]
    )
    db.flush()

    # PullRequestService resolves human authors through Actor.
    # Both users are also used in authorization scenarios.
    _create_human_actor(
        db,
        user_a,
    )

    _create_human_actor(
        db,
        user_b,
    )

    repo = RepositoryService(db).create(
        owner_id=user_a.id,
        name=f"ci_srepo_{uuid4().hex[:8]}",
        description="CI Service Repo",
        visibility="private",
    )

    agent = Agent(
        id=str(uuid4()),
        owner_id=user_a.id,
        name="ci_sagent",
        token_prefix="prefix_cisag_12",
        token_hash="hash",
        is_active=True,
        status="active",
    )

    db.add(agent)

    actor = Actor(
        id=agent.id,
        owner_id=user_a.id,
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
        intent="CI Service Change",
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
        user_a.id,
        change.id,
        "CI Service PR",
        "main",
    )

    db.commit()

    return (
        user_a,
        user_b,
        repo,
        change,
        pr,
    )


def test_ci_job_creation_and_runner_execution(db):
    (
        user_a,
        user_b,
        repo,
        change,
        pr,
    ) = setup_ci_service_fixtures(db)

    svc = CIService(db)

    # 1. Create CI job.
    job = svc.create_job(
        pull_request_id=pr.id,
        actor_id=user_a.id,
    )

    assert job.status == CIJob.STATUS_QUEUED

    # 2. Execute via the isolated runner.
    executed = svc.run_execution(
        job.id,
        worker_id="test_worker_1",
    )

    db.commit()

    assert executed.status == CIJob.STATUS_PASSED
    assert executed.exit_code == 0
    assert "Automated" in executed.output_log


def test_ci_job_cancellation(db):
    (
        user_a,
        user_b,
        repo,
        change,
        pr,
    ) = setup_ci_service_fixtures(db)

    svc = CIService(db)

    job = svc.create_job(
        pull_request_id=pr.id,
        actor_id=user_a.id,
    )

    cancelled = svc.cancel_job(
        job.id,
        user_a.id,
    )

    db.commit()

    assert (
        cancelled.status
        == CIJob.STATUS_CANCELLED
    )
    assert cancelled.cancelled_at is not None


def test_ci_api_flow(db, client):
    (
        user_a,
        user_b,
        repo,
        change,
        pr,
    ) = setup_ci_service_fixtures(db)

    from app.api.dependencies import get_current_user
    from app.main import app

    # 1. Trigger CI via API.
    app.dependency_overrides[
        get_current_user
    ] = lambda: user_a

    res_create = client.post(
        f"/v1/pull-requests/{pr.id}/ci"
    )

    assert (
        res_create.status_code
        == status.HTTP_201_CREATED
    )

    job_data = res_create.json()

    assert job_data["status"] == "passed"

    job_id = job_data["id"]

    # 2. Get CI logs via API.
    res_logs = client.get(
        f"/v1/pull-requests/{pr.id}/ci/{job_id}/logs"
    )

    assert (
        res_logs.status_code
        == status.HTTP_200_OK
    )

    assert "Automated" in (
        res_logs.json()["output_log"]
    )

    # 3. Unauthorized user attempts to read CI logs.
    app.dependency_overrides[
        get_current_user
    ] = lambda: user_b

    res_unauth = client.get(
        f"/v1/pull-requests/{pr.id}/ci/{job_id}/logs"
    )

    assert (
        res_unauth.status_code
        == status.HTTP_404_NOT_FOUND
    )

    app.dependency_overrides.clear()