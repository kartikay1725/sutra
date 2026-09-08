from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.db.session import get_db
from app.models.actor import Actor
from app.models.change import Change
from app.models.ci_job import CIJob
from app.models.deployment import Deployment
from app.models.environment import Environment
from app.models.pull_request import PullRequest
from app.models.repository import Repository
from app.models.user import User
from app.main import app


def test_repository_insights_are_derived_from_real_records(
    client: TestClient,
    db: Session,
):
    user = User(
        username="insights-user",
        email="insights@example.com",
        password_hash="dummy",
    )
    db.add(user)
    db.commit()

    repository = Repository(
        owner_id=user.id,
        name="insights-repo",
        slug="insights-repo",
        visibility="private",
        storage_key="insights-storage",
    )
    db.add(repository)
    db.commit()

    agent_actor = Actor(
        id="agent-insights-actor",
        owner_id=user.id,
        type="agent",
        name="Atlas",
        capabilities="[]",
    )
    human_actor = Actor(
        id="human-insights-actor",
        owner_id=user.id,
        type="human",
        name="insights-user",
        capabilities="[]",
    )
    db.add_all([agent_actor, human_actor])
    db.flush()

    now = datetime.now(timezone.utc)

    agent_change = Change(
        repository_id=repository.id,
        actor_id=agent_actor.id,
        intent="Agent change",
        base_commit="a" * 40,
        resulting_commit="b" * 40,
        status="recorded",
        risk_level="low",
        metadata_json="{}",
        created_at=now - timedelta(hours=2),
        updated_at=now,
    )
    human_change = Change(
        repository_id=repository.id,
        actor_id=human_actor.id,
        intent="Human change",
        base_commit="c" * 40,
        resulting_commit="d" * 40,
        status="recorded",
        risk_level="low",
        metadata_json="{}",
        created_at=now - timedelta(hours=1),
        updated_at=now,
    )
    db.add_all([agent_change, human_change])
    db.flush()

    agent_pr = PullRequest(
        repository_id=repository.id,
        author_id=user.id,
        source_change_id=agent_change.id,
        title="Agent PR",
        description=None,
        target_branch="main",
        source_commit="b" * 40,
        target_commit="a" * 40,
        status=PullRequest.STATUS_MERGED,
        created_at=now - timedelta(hours=2),
        updated_at=now,
        merged_at=now,
    )
    human_pr = PullRequest(
        repository_id=repository.id,
        author_id=user.id,
        source_change_id=human_change.id,
        title="Human PR",
        description=None,
        target_branch="main",
        source_commit="d" * 40,
        target_commit="c" * 40,
        status=PullRequest.STATUS_MERGED,
        created_at=now - timedelta(hours=1),
        updated_at=now,
        merged_at=now,
    )
    db.add_all([agent_pr, human_pr])
    db.flush()

    db.add_all(
        [
            CIJob(
                pull_request_id=agent_pr.id,
                repository_id=repository.id,
                change_id=agent_change.id,
                commit_sha="b" * 40,
                target_branch="main",
                status=CIJob.STATUS_PASSED,
                created_at=now - timedelta(days=2),
                updated_at=now - timedelta(days=2),
            ),
            CIJob(
                pull_request_id=human_pr.id,
                repository_id=repository.id,
                change_id=human_change.id,
                commit_sha="d" * 40,
                target_branch="main",
                status=CIJob.STATUS_FAILED,
                created_at=now - timedelta(days=1),
                updated_at=now - timedelta(days=1),
            ),
        ]
    )

    environment = Environment(
        repository_id=repository.id,
        name="staging",
        description="Test environment",
        type="staging",
    )
    db.add(environment)
    db.flush()

    db.add(
        Deployment(
            environment_id=environment.id,
            repository_id=repository.id,
            commit_sha="b" * 40,
            change_id=agent_change.id,
            actor_id=human_actor.id,
            status=Deployment.STATUS_SUCCESS,
            created_at=now - timedelta(days=1),
            updated_at=now - timedelta(days=1),
        )
    )
    db.commit()

    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_db] = lambda: db

    try:
        response = client.get(
            f"/v1/repositories/{user.username}/{repository.name}/insights"
        )
    finally:
        app.dependency_overrides.pop(get_current_user, None)
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 200, response.text
    payload = response.json()

    assert payload["deployments_per_week"] > 0
    assert payload["lead_time_minutes"] >= 0
    assert payload["ci_pass_rate"] == 50.0
    assert payload["agent_changes_percent"] == 50
    assert payload["human_changes_percent"] == 50
    assert payload["agent_lead_time_minutes"] >= 0
    assert payload["human_lead_time_minutes"] >= 0


def test_private_repository_insights_are_scoped_to_owner(
    client: TestClient,
    db: Session,
):
    owner = User(
        username="insights-owner",
        email="owner@example.com",
        password_hash="dummy",
    )
    other = User(
        username="insights-other",
        email="other@example.com",
        password_hash="dummy",
    )
    db.add_all([owner, other])
    db.commit()

    repository = Repository(
        owner_id=owner.id,
        name="private-insights",
        slug="private-insights",
        visibility="private",
        storage_key="private-insights-storage",
    )
    db.add(repository)
    db.commit()

    app.dependency_overrides[get_current_user] = lambda: other
    app.dependency_overrides[get_db] = lambda: db

    try:
        response = client.get(
            f"/v1/repositories/{owner.username}/{repository.name}/insights"
        )
    finally:
        app.dependency_overrides.pop(get_current_user, None)
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 404


def test_global_insights_aggregates_across_user_repositories(
    client: TestClient,
    db: Session,
):
    user = User(
        username="global-insights-user",
        email="global-insights@example.com",
        password_hash="dummy",
    )
    db.add(user)
    db.commit()

    repo1 = Repository(
        owner_id=user.id,
        name="repo-one",
        slug="repo-one",
        visibility="private",
        storage_key="repo-one-storage",
    )
    repo2 = Repository(
        owner_id=user.id,
        name="repo-two",
        slug="repo-two",
        visibility="private",
        storage_key="repo-two-storage",
    )
    db.add_all([repo1, repo2])
    db.commit()

    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_db] = lambda: db

    try:
        response = client.get("/v1/insights")
    finally:
        app.dependency_overrides.pop(get_current_user, None)
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 200, response.text
    payload = response.json()
    assert "deployments_per_week" in payload
    assert "ci_pass_rate" in payload
    assert "agent_changes_percent" in payload
    assert "actionable_signal" in payload

