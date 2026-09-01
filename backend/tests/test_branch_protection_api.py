from pathlib import Path
import subprocess
from uuid import uuid4

from fastapi import status

from app.core.config import settings
from app.models.actor import Actor
from app.models.agent import Agent
from app.models.change import Change
from app.models.change_review import ChangeReview
from app.models.user import User
from app.services.branch_protection_service import (
    BranchProtectionService,
)
from app.services.pull_request_service import (
    PullRequestService,
)
from app.services.repository_service import (
    RepositoryService,
)


def _git_output(
    args: list[str],
    *,
    cwd: Path,
    env: dict[str, str] | None = None,
) -> str:
    process_env = None

    if env is not None:
        import os

        process_env = os.environ.copy()
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


def _create_real_change_commits(
    repo_storage_key: str,
) -> tuple[str, str]:
    """
    Create a real child commit from the repository's initial main commit.

    Returns:
        (base_commit, resulting_commit)
    """
    repo_dir = (
        Path(
            settings.repository_storage_path
        ).resolve()
        / repo_storage_key
    ).resolve()

    if not repo_dir.exists():
        raise RuntimeError(
            f"Repository storage path does not exist: {repo_dir}"
        )

    base_commit = _git_output(
        [
            "rev-parse",
            "--verify",
            "refs/heads/main",
        ],
        cwd=repo_dir,
    )

    if not base_commit:
        raise RuntimeError(
            "Repository does not contain an initial main commit"
        )

    tree_sha = _git_output(
        [
            "rev-parse",
            f"{base_commit}^{{tree}}",
        ],
        cwd=repo_dir,
    )

    if not tree_sha:
        raise RuntimeError(
            "Unable to resolve the repository tree"
        )

    import os

    commit_env = os.environ.copy()
    commit_env.update(
        {
            "GIT_AUTHOR_NAME": "SUTRA Test",
            "GIT_AUTHOR_EMAIL": "test@sutra.local",
            "GIT_COMMITTER_NAME": "SUTRA Test",
            "GIT_COMMITTER_EMAIL": "test@sutra.local",
        }
    )

    resulting_commit = _git_output(
        [
            "commit-tree",
            tree_sha,
            "-p",
            base_commit,
            "-m",
            "Branch protection API test change",
        ],
        cwd=repo_dir,
        env=commit_env,
    )

    if not resulting_commit:
        raise RuntimeError(
            "Unable to create the test change commit"
        )

    return base_commit, resulting_commit


def setup_bp_api_fixtures(db):
    user_owner = User(
        id=str(uuid4()),
        username=f"bp_api_owner_{uuid4().hex[:8]}",
        email=f"bpapiowner_{uuid4().hex[:8]}@example.com",
        password_hash="hash",
    )

    user_other = User(
        id=str(uuid4()),
        username=f"bp_api_other_{uuid4().hex[:8]}",
        email=f"bpapiother_{uuid4().hex[:8]}@example.com",
        password_hash="hash",
    )

    db.add_all(
        [
            user_owner,
            user_other,
        ]
    )
    db.flush()

    # PullRequestService requires human authors to exist as Actors.
    user_owner_actor = Actor(
        id=user_owner.id,
        owner_id=user_owner.id,
        type="human",
        name=user_owner.username,
        capabilities=(
            '["repository.read", '
            '"repository.write", '
            '"change.create", '
            '"change.review", '
            '"change.approve"]'
        ),
    )

    user_other_actor = Actor(
        id=user_other.id,
        owner_id=user_other.id,
        type="human",
        name=user_other.username,
        capabilities=(
            '["repository.read", '
            '"repository.write", '
            '"change.create", '
            '"change.review", '
            '"change.approve"]'
        ),
    )

    db.add_all(
        [
            user_owner_actor,
            user_other_actor,
        ]
    )
    db.flush()

    repo = RepositoryService(db).create(
        owner_id=user_owner.id,
        name=f"bp_apirepo_{uuid4().hex[:8]}",
        description="BP API Repo",
        visibility="private",
    )

    agent = Agent(
        id=str(uuid4()),
        owner_id=user_owner.id,
        name="bp_api_agent",
        token_prefix="prefix_bpapi_12",
        token_hash="hash",
        is_active=True,
        status="active",
    )
    db.add(agent)

    actor = Actor(
        id=agent.id,
        owner_id=user_owner.id,
        type="agent",
        name=agent.name,
        capabilities=(
            '["repository.read", '
            '"repository.write", '
            '"change.create", '
            '"change.review", '
            '"change.approve"]'
        ),
    )
    db.add(actor)
    db.commit()

    base_commit, resulting_commit = _create_real_change_commits(
        repo.storage_key
    )

    change = Change(
        id=str(uuid4()),
        repository_id=repo.id,
        actor_id=actor.id,
        intent="BP API Change",
        risk_level="low",
        resulting_commit=resulting_commit,
        base_commit=base_commit,
        operation_key=(uuid4().hex * 2)[:64],
        status="proposed",
    )

    db.add(change)
    db.commit()

    pr_svc = PullRequestService(db)

    pr = pr_svc.create_pull_request(
        repo.id,
        user_owner.id,
        change.id,
        "BP API PR",
        "main",
    )

    db.commit()

    return (
        user_owner,
        user_other,
        repo,
        change,
        pr,
    )


def test_branch_protection_api_management(db, client):
    (
        user_owner,
        user_other,
        repo,
        change,
        pr,
    ) = setup_bp_api_fixtures(db)

    from app.api.dependencies import get_current_user
    from app.main import app

    app.dependency_overrides[get_current_user] = (
        lambda: user_owner
    )

    payload = {
        "branch_pattern": "main",
        "required_approvals": 1,
        "require_change_review": True,
        "require_resolved_threads": True,
    }

    res_create = client.post(
        f"/v1/repositories/{repo.id}/branch-protection",
        json=payload,
    )

    assert (
        res_create.status_code
        == status.HTTP_201_CREATED
    )

    rule_id = res_create.json()["id"]

    app.dependency_overrides[get_current_user] = (
        lambda: user_other
    )

    res_unauth = client.patch(
        f"/v1/repositories/{repo.id}/branch-protection/{rule_id}",
        json={"required_approvals": 2},
    )

    assert (
        res_unauth.status_code
        == status.HTTP_403_FORBIDDEN
    )

    app.dependency_overrides[get_current_user] = (
        lambda: user_owner
    )

    res_update = client.patch(
        f"/v1/repositories/{repo.id}/branch-protection/{rule_id}",
        json={"required_approvals": 2},
    )

    assert (
        res_update.status_code
        == status.HTTP_200_OK
    )

    assert (
        res_update.json()["required_approvals"]
        == 2
    )

    res_delete = client.delete(
        f"/v1/repositories/{repo.id}/branch-protection/{rule_id}"
    )

    assert (
        res_delete.status_code
        == status.HTTP_204_NO_CONTENT
    )

    app.dependency_overrides.clear()


def test_branch_protection_merge_gate_enforcement(
    db,
    client,
):
    (
        user_owner,
        user_other,
        repo,
        change,
        pr,
    ) = setup_bp_api_fixtures(db)

    from app.api.dependencies import get_current_user
    from app.main import app

    bp_svc = BranchProtectionService(db)

    bp_svc.create_rule(
        repository_id=repo.id,
        actor_user_id=user_owner.id,
        branch_pattern="main",
        required_approvals=1,
        require_change_review=True,
        require_resolved_threads=True,
    )

    app.dependency_overrides[get_current_user] = (
        lambda: user_owner
    )

    res_merge_fail = client.post(
        f"/v1/pull-requests/{pr.id}/merge"
    )

    assert (
        res_merge_fail.status_code
        == status.HTTP_409_CONFLICT
    )

    assert (
        "Merge rejected by branch protection"
        in res_merge_fail.json()["detail"]
    )

    review = ChangeReview(
        id=str(uuid4()),
        change_id=change.id,
        requested_by=user_owner.id,
        reviewer_id=user_other.id,
        status="approved",
    )

    db.add(review)
    db.commit()

    res_merge_success = client.post(
        f"/v1/pull-requests/{pr.id}/merge"
    )

    assert (
        res_merge_success.status_code
        == status.HTTP_200_OK
    )

    assert res_merge_success.json()["status"] in {
        "merged",
        "merge_ready",
    }

    app.dependency_overrides.clear()