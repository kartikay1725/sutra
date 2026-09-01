from uuid import uuid4
import pytest
from fastapi import status

from app.models.ci_job import CIJob
from app.models.deployment import Deployment
from app.models.environment import Environment
from app.models.artifact import Artifact
from app.models.actor import Actor
from app.models.change import Change
from app.models.pull_request import PullRequest
from app.models.repository import Repository
from app.models.user import User
from app.services.repository_service import RepositoryService
from app.services.pull_request_service import PullRequestService
from tests.conftest import ensure_test_actor


def setup_automation_fixtures(db):
    user_a = User(
        id=str(uuid4()),
        username=f"auto_user_{uuid4().hex[:8]}",
        email=f"auto_{uuid4().hex[:8]}@example.com",
        password_hash="hash",
    )
    db.add(user_a)
    db.flush()
    ensure_test_actor(db, user_a)

    repo = RepositoryService(db).create(
        owner_id=user_a.id,
        name=f"auto_repo_{uuid4().hex[:8]}",
        description="Automation Repo",
        visibility="private",
    )

    from app.models.agent import Agent
    agent = Agent(
        id=str(uuid4()),
        owner_id=user_a.id,
        name="auto_agent",
        token_prefix="prfx",
        token_hash="hash",
        is_active=True,
        status="active"
    )
    db.add(agent)

    actor = Actor(
        id=agent.id,
        owner_id=user_a.id,
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
        intent="Auto Change",
        risk_level="low",
        resulting_commit="1111111111111111111111111111111111111111",
        base_commit="0000000000000000000000000000000000000000",
        operation_key=(uuid4().hex * 2)[:64],
        status="proposed",
    )
    db.add(change)
    db.commit()

    pr_svc = PullRequestService(db)
    pr = pr_svc.create_pull_request(repo.id, user_a.id, change.id, "Auto PR", "main")
    db.commit()

    return user_a, repo, change, pr


def test_automation_lifecycle(client, db):
    user_a, repo, change, pr = setup_automation_fixtures(db)

    from app.api.dependencies import get_current_user
    from app.main import app

    app.dependency_overrides[get_current_user] = lambda: user_a

    # 1. Ensure we have a CI Job
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
    db.refresh(job)

    # 2. Test Artifacts API
    artifact_data = {
        "name": "build-output.tar.gz",
        "storage_key": "s3://sutra-artifacts/123/build-output.tar.gz",
        "size_bytes": 1024500,
        "mime_type": "application/gzip",
    }
    resp = client.post(f"/v1/ci-jobs/{job.id}/artifacts", json=artifact_data)
    assert resp.status_code == status.HTTP_201_CREATED
    assert resp.json()["name"] == "build-output.tar.gz"

    resp = client.get(f"/v1/ci-jobs/{job.id}/artifacts")
    assert resp.status_code == status.HTTP_200_OK
    assert len(resp.json()) == 1

    # 3. Test Environments API
    env_data = {
        "name": "staging",
        "description": "Staging environment for pre-prod tests",
        "type": "staging",
    }
    resp = client.post(f"/v1/repositories/{user_a.username}/{repo.name}/environments", json=env_data)
    assert resp.status_code == status.HTTP_201_CREATED
    env_id = resp.json()["id"]

    resp = client.get(f"/v1/repositories/{user_a.username}/{repo.name}/environments")
    assert resp.status_code == status.HTTP_200_OK
    assert len(resp.json()) == 1

    # 4. Test Deployments API
    dep_data = {
        "commit_sha": change.resulting_commit,
        "change_id": change.id,
    }
    resp = client.post(f"/v1/environments/{env_id}/deployments", json=dep_data)
    assert resp.status_code == status.HTTP_201_CREATED
    dep_id = resp.json()["id"]

    update_data = {
        "status": Deployment.STATUS_SUCCESS,
        "log_output": "Deployment succeeded in 45s",
    }
    resp = client.post(f"/v1/deployments/{dep_id}/status", json=update_data)
    assert resp.status_code == status.HTTP_200_OK
    assert resp.json()["status"] == Deployment.STATUS_SUCCESS

    resp = client.get(f"/v1/environments/{env_id}/deployments")
    assert resp.status_code == status.HTTP_200_OK
    assert len(resp.json()) == 1
    assert resp.json()[0]["status"] == Deployment.STATUS_SUCCESS

    app.dependency_overrides.clear()
