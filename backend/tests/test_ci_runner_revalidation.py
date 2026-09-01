from uuid import uuid4

from app.models.actor import Actor
from app.models.agent import Agent
from app.models.change import Change
from app.models.ci_job import CIJob
from app.models.user import User
from app.services.ci_runner import CIRunner
from app.services.ci_service import CIService
from app.services.pull_request_service import PullRequestService
from app.services.repository_service import RepositoryService


def setup_reval_fixtures(db):
    user = User(
        id=str(uuid4()),
        username=f"reval_user_{uuid4().hex[:8]}",
        email=f"reval_{uuid4().hex[:8]}@example.com",
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
        name=f"reval_repo_{uuid4().hex[:8]}",
        description="Revalidation Repo",
        visibility="private",
    )

    agent = Agent(
        id=str(uuid4()),
        owner_id=user.id,
        name="reval_agent",
        token_prefix="prefix_reval_12",
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
        intent="Revalidation Change",
        risk_level="low",
        resulting_commit=(
            "2222222222222222222222222222222222222222"
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
        "Revalidation PR",
        "main",
    )

    db.commit()

    return user, repo, change, pr


def test_revalidation_environment_secret_stripping(db):
    user, repo, change, pr = setup_reval_fixtures(db)

    job = CIJob(
        pull_request_id=pr.id,
        repository_id=repo.id,
        change_id=change.id,
        commit_sha=change.resulting_commit,
        target_branch="main",
        status=CIJob.STATUS_QUEUED,
    )

    db.add(job)
    db.commit()

    runner = CIRunner(db)
    env = runner._build_isolated_env(job)

    assert "DATABASE_URL" not in env
    assert "SECRET_KEY" not in env
    assert "JWT_SECRET" not in env
    assert env["CI"] == "true"
    assert env["SUTRA_CI_COMMIT_SHA"] == change.resulting_commit


def test_revalidation_process_execution_safety(db):
    user, repo, change, pr = setup_reval_fixtures(db)

    ci_svc = CIService(db)

    job = ci_svc.create_job(
        pr.id,
        user.id,
    )

    executed = ci_svc.run_execution(
        job.id,
        worker_id="reval_worker",
    )

    db.commit()

    assert executed.status == CIJob.STATUS_PASSED
    assert executed.exit_code == 0
    assert "Automated Sandbox Container" in executed.output_log