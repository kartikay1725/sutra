from uuid import uuid4

from fastapi import status

from app.models.actor import Actor
from app.models.agent import Agent
from app.models.change import Change
from app.models.ci_job import CIJob
from app.models.user import User
from app.services.ci_runner import CIRunner
from app.services.ci_service import CIService
from app.services.pull_request_service import PullRequestService
from app.services.repository_service import RepositoryService


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


def setup_sec_ci_fixtures(db):
    user_a = User(
        id=str(uuid4()),
        username=f"sec_ci_user_a_{uuid4().hex[:8]}",
        email=f"seccia_{uuid4().hex[:8]}@example.com",
        password_hash="hash",
    )

    user_b = User(
        id=str(uuid4()),
        username=f"sec_ci_user_b_{uuid4().hex[:8]}",
        email=f"seccib_{uuid4().hex[:8]}@example.com",
        password_hash="hash",
    )

    db.add_all(
        [
            user_a,
            user_b,
        ]
    )
    db.flush()

    # Both users participate in the authorization flow.
    # User A is also the PullRequest author.
    _create_human_actor(
        db,
        user_a,
    )

    _create_human_actor(
        db,
        user_b,
    )

    repo_a = RepositoryService(db).create(
        owner_id=user_a.id,
        name=f"sec_ci_repo_a_{uuid4().hex[:8]}",
        description="Sec CI Repo A",
        visibility="private",
    )

    agent = Agent(
        id=str(uuid4()),
        owner_id=user_a.id,
        name="sec_ci_agent",
        token_prefix="prefix_secci_12",
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

    change_a = Change(
        id=str(uuid4()),
        repository_id=repo_a.id,
        actor_id=actor.id,
        intent="Sec CI Change A",
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

    db.add(change_a)
    db.commit()

    pr_svc = PullRequestService(db)

    pr_a = pr_svc.create_pull_request(
        repo_a.id,
        user_a.id,
        change_a.id,
        "Sec CI PR A",
        "main",
    )

    db.commit()

    return (
        user_a,
        user_b,
        repo_a,
        change_a,
        pr_a,
    )


def test_ci_runner_secret_and_environment_stripping(db):
    (
        user_a,
        user_b,
        repo_a,
        change_a,
        pr_a,
    ) = setup_sec_ci_fixtures(db)

    ci_svc = CIService(db)

    job = ci_svc.create_job(
        pr_a.id,
        user_a.id,
    )

    runner = CIRunner(db)

    env = runner._build_isolated_env(
        job
    )

    # Verify host secrets are stripped.
    assert "DATABASE_URL" not in env
    assert "SECRET_KEY" not in env
    assert "JWT_SECRET" not in env

    assert env["CI"] == "true"
    assert (
        env["SUTRA_CI_COMMIT_SHA"]
        == change_a.resulting_commit
    )


def test_ci_api_private_repository_isolation(
    db,
    client,
):
    (
        user_a,
        user_b,
        repo_a,
        change_a,
        pr_a,
    ) = setup_sec_ci_fixtures(db)

    from app.api.dependencies import get_current_user
    from app.main import app

    # User A creates the CI job.
    app.dependency_overrides[
        get_current_user
    ] = lambda: user_a

    res_job = client.post(
        f"/v1/pull-requests/{pr_a.id}/ci"
    )

    assert (
        res_job.status_code
        == status.HTTP_201_CREATED
    )

    job_id = res_job.json()["id"]

    # User B must not be able to read or cancel
    # User A's private-repository CI job.
    app.dependency_overrides[
        get_current_user
    ] = lambda: user_b

    res_get = client.get(
        f"/v1/pull-requests/{pr_a.id}/ci/{job_id}"
    )

    assert (
        res_get.status_code
        == status.HTTP_404_NOT_FOUND
    )

    res_cancel = client.post(
        f"/v1/pull-requests/{pr_a.id}/ci/{job_id}/cancel"
    )

    assert (
        res_cancel.status_code
        == status.HTTP_404_NOT_FOUND
    )

    app.dependency_overrides.clear()