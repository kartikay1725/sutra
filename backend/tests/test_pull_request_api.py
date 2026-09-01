import os
import subprocess
from pathlib import Path
from uuid import uuid4

from fastapi import status

from app.core.config import settings
from app.models.actor import Actor
from app.models.agent import Agent
from app.models.change import Change
from app.models.change_review import ChangeReview
from app.models.pull_request import PullRequest
from app.models.user import User
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


def _run_git(
    args: list[str],
    *,
    cwd: Path,
    env: dict[str, str] | None = None,
) -> str:
    process_env = os.environ.copy()

    if env:
        process_env.update(env)

    result = subprocess.run(
        ["git", *args],
        cwd=cwd,
        env=process_env,
        capture_output=True,
        text=True,
        check=True,
    )

    return result.stdout.strip()


def _create_real_child_commit(
    repository_storage_key: str,
) -> tuple[str, str]:
    """
    Return a real (base_commit, resulting_commit) pair.

    The resulting commit is a child of the repository's existing main
    commit and therefore exists in the actual Git object database.
    """
    repo_dir = (
        Path(
            settings.repository_storage_path
        ).resolve()
        / repository_storage_key
    ).resolve()

    if not repo_dir.exists():
        raise RuntimeError(
            f"Repository storage path does not exist: {repo_dir}"
        )

    base_commit = _run_git(
        [
            "rev-parse",
            "--verify",
            "refs/heads/main",
        ],
        cwd=repo_dir,
    )

    if not base_commit:
        raise RuntimeError(
            "Repository does not contain a main commit"
        )

    tree_sha = _run_git(
        [
            "rev-parse",
            f"{base_commit}^{{tree}}",
        ],
        cwd=repo_dir,
    )

    if not tree_sha:
        raise RuntimeError(
            "Unable to resolve main tree"
        )

    resulting_commit = _run_git(
        [
            "commit-tree",
            tree_sha,
            "-p",
            base_commit,
            "-m",
            "Pull request API test change",
        ],
        cwd=repo_dir,
        env={
            "GIT_AUTHOR_NAME": "SUTRA Test",
            "GIT_AUTHOR_EMAIL": "test@sutra.local",
            "GIT_COMMITTER_NAME": "SUTRA Test",
            "GIT_COMMITTER_EMAIL": "test@sutra.local",
        },
    )

    if not resulting_commit:
        raise RuntimeError(
            "Unable to create resulting test commit"
        )

    return (
        base_commit,
        resulting_commit,
    )


def setup_api_fixtures(db, client):
    user = User(
        id=str(uuid4()),
        username=f"api_user_{uuid4().hex[:8]}",
        email=f"api_{uuid4().hex[:8]}@example.com",
        password_hash="hash",
    )

    other_user = User(
        id=str(uuid4()),
        username=f"other_api_user_{uuid4().hex[:8]}",
        email=f"other_api_{uuid4().hex[:8]}@example.com",
        password_hash="hash",
    )

    db.add_all(
        [
            user,
            other_user,
        ]
    )
    db.flush()

    _create_human_actor(
        db,
        user,
    )

    _create_human_actor(
        db,
        other_user,
    )

    repo = RepositoryService(db).create(
        owner_id=user.id,
        name=f"api_repo_{uuid4().hex[:8]}",
        description="API test repo",
        visibility="private",
    )

    agent = Agent(
        id=str(uuid4()),
        owner_id=user.id,
        name="api_agent",
        token_prefix="api_prefix_12345",
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
            '"change.create", '
            '"change.propose", '
            '"change.review"]'
        ),
    )

    db.add(actor)
    db.commit()

    change = Change(
        id=str(uuid4()),
        repository_id=repo.id,
        actor_id=actor.id,
        intent="API Test Change",
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

    return (
        user,
        other_user,
        repo,
        actor,
        change,
    )


def test_pr_api_unauthenticated_access(client):
    res = client.post(
        "/v1/pull-requests",
        json={},
    )

    assert (
        res.status_code
        == status.HTTP_401_UNAUTHORIZED
    )

    res_get = client.get(
        f"/v1/pull-requests/{uuid4()}"
    )

    assert (
        res_get.status_code
        == status.HTTP_401_UNAUTHORIZED
    )


def test_pr_api_creation_and_authorization(
    db,
    client,
):
    (
        user,
        other_user,
        repo,
        actor,
        change,
    ) = setup_api_fixtures(
        db,
        client,
    )

    from app.api.dependencies import get_current_user
    from app.main import app

    app.dependency_overrides[
        get_current_user
    ] = lambda: user

    res = client.post(
        "/v1/pull-requests",
        json={
            "repository_id": repo.id,
            "source_change_id": change.id,
            "title": "API PR Title",
            "description": "API PR Description",
            "target_branch": "main",
        },
    )

    assert (
        res.status_code
        == status.HTTP_201_CREATED
    )

    data = res.json()

    assert data["title"] == "API PR Title"
    assert data["status"] == "open"
    assert data["source_change_id"] == change.id

    res_dup = client.post(
        "/v1/pull-requests",
        json={
            "repository_id": repo.id,
            "source_change_id": change.id,
            "title": "Duplicate Title",
            "target_branch": "main",
        },
    )

    assert (
        res_dup.status_code
        == status.HTTP_201_CREATED
    )

    assert (
        res_dup.json()["id"]
        == data["id"]
    )

    app.dependency_overrides[
        get_current_user
    ] = lambda: other_user

    change2 = Change(
        id=str(uuid4()),
        repository_id=repo.id,
        actor_id=actor.id,
        intent="Change 2",
        resulting_commit=(
            "2222222222222222222222222222222222222222"
        ),
        operation_key=(uuid4().hex * 2)[:64],
        status="proposed",
    )

    db.add(change2)
    db.commit()

    res_unauth = client.post(
        "/v1/pull-requests",
        json={
            "repository_id": repo.id,
            "source_change_id": change2.id,
            "title": "Unauthorized PR",
            "target_branch": "main",
        },
    )

    assert (
        res_unauth.status_code
        == status.HTTP_403_FORBIDDEN
    )

    app.dependency_overrides.clear()


def test_pr_api_read_and_private_isolation(
    db,
    client,
):
    (
        user,
        other_user,
        repo,
        actor,
        change,
    ) = setup_api_fixtures(
        db,
        client,
    )

    from app.api.dependencies import get_current_user
    from app.main import app

    app.dependency_overrides[
        get_current_user
    ] = lambda: user

    res_create = client.post(
        "/v1/pull-requests",
        json={
            "repository_id": repo.id,
            "source_change_id": change.id,
            "title": "Read Test PR",
            "target_branch": "main",
        },
    )

    assert (
        res_create.status_code
        == status.HTTP_201_CREATED
    )

    pr_id = res_create.json()["id"]

    res_get = client.get(
        f"/v1/pull-requests/{pr_id}"
    )

    assert (
        res_get.status_code
        == status.HTTP_200_OK
    )

    assert (
        res_get.json()["id"]
        == pr_id
    )

    res_list = client.get(
        f"/v1/repositories/{repo.id}/pull-requests"
    )

    assert (
        res_list.status_code
        == status.HTTP_200_OK
    )

    assert len(
        res_list.json()
    ) == 1

    app.dependency_overrides[
        get_current_user
    ] = lambda: other_user

    res_other_get = client.get(
        f"/v1/pull-requests/{pr_id}"
    )

    assert (
        res_other_get.status_code
        == status.HTTP_404_NOT_FOUND
    )

    res_other_list = client.get(
        f"/v1/repositories/{repo.id}/pull-requests"
    )

    assert (
        res_other_list.status_code
        == status.HTTP_403_FORBIDDEN
    )

    app.dependency_overrides.clear()


def test_pr_api_approve_merge_close_reject_endpoints(
    db,
    client,
):
    (
        user,
        other_user,
        repo,
        actor,
        change,
    ) = setup_api_fixtures(
        db,
        client,
    )

    from app.api.dependencies import get_current_user
    from app.main import app

    app.dependency_overrides[
        get_current_user
    ] = lambda: user

    svc = PullRequestService(db)

    # 1. Create PR authored by the repository owner.
    pr = svc.create_pull_request(
        repo.id,
        user.id,
        change.id,
        "Full Flow PR",
        "main",
    )

    pr_id = pr.id

    # 2. Approval without ChangeReview must fail.
    res_app_fail = client.post(
        f"/v1/pull-requests/{pr_id}/approve"
    )

    assert (
        res_app_fail.status_code
        == status.HTTP_409_CONFLICT
    )

    # 3. Add approved review by other_user.
    review = ChangeReview(
        change_id=change.id,
        requested_by=user.id,
        reviewer_id=other_user.id,
        status="approved",
    )

    db.add(review)
    db.commit()

    # 4. Self-approval by the PR author must fail.
    res_app_self = client.post(
        f"/v1/pull-requests/{pr_id}/approve"
    )

    assert (
        res_app_self.status_code
        == status.HTTP_409_CONFLICT
    )

    # ---------------------------------------------------------
    # 5. Create a real Git commit for the mergeable PR.
    # ---------------------------------------------------------
    base_commit, resulting_commit = (
        _create_real_child_commit(
            repo.storage_key
        )
    )

    change2 = Change(
        id=str(uuid4()),
        repository_id=repo.id,
        actor_id=actor.id,
        intent="Agent Change",
        resulting_commit=resulting_commit,
        base_commit=base_commit,
        operation_key=(uuid4().hex * 2)[:64],
        status="proposed",
    )

    db.add(change2)

    review2 = ChangeReview(
        change_id=change2.id,
        requested_by=other_user.id,
        reviewer_id=user.id,
        status="approved",
    )

    db.add(review2)

    pr_agent = PullRequest(
        repository_id=repo.id,
        author_id=other_user.id,
        source_change_id=change2.id,
        source_commit=resulting_commit,
        title="Agent PR",
        target_branch="main",
        status="open",
    )

    db.add(pr_agent)
    db.commit()

    # 6. Repository owner approves the second PR.
    res_app_ok = client.post(
        f"/v1/pull-requests/{pr_agent.id}/approve",
        json={
            "reason": "Looks good"
        },
    )

    assert (
        res_app_ok.status_code
        == status.HTTP_200_OK
    )

    assert (
        res_app_ok.json()["status"]
        == "approved"
    )

    # 7. The real Git merge should now succeed.
    res_merge = client.post(
        f"/v1/pull-requests/{pr_agent.id}/merge"
    )

    assert (
        res_merge.status_code
        == status.HTTP_200_OK
    )

    assert res_merge.json()["status"] in {
        "merged",
        "merge_ready",
    }

    app.dependency_overrides.clear()


def test_pr_api_input_validation_and_malformed_requests(
    client,
):
    from app.api.dependencies import get_current_user
    from app.main import app

    dummy_user = User(
        id=str(uuid4()),
        username="dummy",
        email="dummy@ex.com",
        password_hash="h",
    )

    app.dependency_overrides[
        get_current_user
    ] = lambda: dummy_user

    res_bad_uuid = client.get(
        "/v1/pull-requests/invalid-uuid-format"
    )

    assert (
        res_bad_uuid.status_code
        == status.HTTP_404_NOT_FOUND
    )

    res_long_title = client.post(
        "/v1/pull-requests",
        json={
            "repository_id": str(uuid4()),
            "source_change_id": str(uuid4()),
            "title": "A" * 300,
            "target_branch": "main",
        },
    )

    assert (
        res_long_title.status_code
        == status.HTTP_422_UNPROCESSABLE_ENTITY
    )

    app.dependency_overrides.clear()