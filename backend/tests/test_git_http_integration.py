import base64
import os
import subprocess
import time
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import select

from app.core.config import settings
from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models.actor import Actor
from app.models.agent import Agent
from app.models.git_push_event import GitPushEvent
from app.models.user import User
from app.models.repository import Repository
from app.services.repository_service import RepositoryService
from app.services.git_push_event_processor import GitPushEventProcessor


import sys

pytestmark = pytest.mark.integration


BASE_URL = os.environ.get(
    "SUTRA_TEST_BASE_URL",
    "http://127.0.0.1:8001",
)

@pytest.fixture(scope="session", autouse=True)
def test_server():
    """Start a real Uvicorn server in a subprocess for Git integration tests."""
    if "SUTRA_TEST_BASE_URL" in os.environ:
        yield
        return

    env = os.environ.copy()
    env["DATABASE_URL"] = settings.database_url
    env["REPOSITORY_STORAGE_PATH"] = settings.repository_storage_path
    env["EVENT_INTEGRITY_KEY"] = settings.event_integrity_key
    env["JWT_SECRET"] = settings.jwt_secret
    
    log_file = open("uvicorn_test.log", "w")

    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8001"],
        env=env,
        stdout=log_file,
        stderr=subprocess.STDOUT,
        cwd=str(Path(__file__).resolve().parents[1])
    )

    import urllib.request
    for _ in range(50):
        try:
            urllib.request.urlopen("http://127.0.0.1:8001/docs")
            break
        except Exception:
            time.sleep(0.1)
    else:
        proc.terminate()
        raise RuntimeError("Failed to start test server")

    yield

    proc.terminate()
    proc.wait(timeout=5)



def run_git(
    *args: str,
    cwd: Path | None = None,
    check: bool = True,
    env: dict[str, str] | None = None,
):
    process_env = os.environ.copy()

    process_env["GIT_TERMINAL_PROMPT"] = "0"

    if env:
        process_env.update(env)

    result = subprocess.run(
        ["git", *args],
        cwd=cwd,
        text=True,
        capture_output=True,
        env=process_env,
        check=False,
    )

    if check and result.returncode != 0:
        raise AssertionError(
            "Git command failed\n\n"
            f"command: git {' '.join(args)}\n"
            f"returncode: {result.returncode}\n"
            f"stdout:\n{result.stdout}\n"
            f"stderr:\n{result.stderr}"
        )

    return result


def git_env(username: str, password: str) -> dict[str, str]:
    """
    Configure Git HTTP Basic authentication without
    allowing Git to prompt.
    """
    encoded = base64.b64encode(
        f"{username}:{password}".encode()
    ).decode()

    return {
        "GIT_TERMINAL_PROMPT": "0",
        "GIT_CONFIG_COUNT": "1",
        "GIT_CONFIG_KEY_0": "http.extraHeader",
        "GIT_CONFIG_VALUE_0": (
            f"Authorization: Basic {encoded}"
        ),
    }


def create_test_identity(db):
    suffix = uuid4().hex[:10]

    user = User(
        id=str(uuid4()),
        username=f"integration-{suffix}",
        email=f"integration-{suffix}@example.com",
        password_hash=hash_password(
            "integration-password"
        ),
    )

    db.add(user)
    db.flush()

    token = (
        "sutra_agent_"
        + uuid4().hex
        + uuid4().hex
    )

    agent = Agent(
        id=str(uuid4()),
        owner_id=user.id,
        name=f"Integration Agent {suffix}",
        description="Real Git HTTP integration agent",
        provider="integration",
        model="integration",
        token_hash=hash_password(token),
        token_prefix=token[:16],
        status="active",
        is_active=True,
    )

    db.add(agent)
    db.flush()

    actor = Actor(
        id=agent.id,
        type="agent",
        name=agent.name,
        owner_id=user.id,
        capabilities=(
            '["repository.read",'
            '"repository.write",'
            '"change.create",'
            '"change.commit",'
            '"change.conflict.read"]'
        ),
    )

    db.add(actor)
    db.commit()

    from app.api.agent_dependencies import create_agent_session
    session, session_token = create_agent_session(agent, db)

    return user, agent, session_token


def create_test_repository(db, user: User) -> Repository:
    service = RepositoryService(db)

    repository = service.create(
        owner_id=user.id,
        name=f"integration-{uuid4().hex[:8]}",
        description="Real Git HTTP integration repository",
        visibility="private",
    )

    db.commit()
    db.refresh(repository)

    return repository


def authenticated_url(
    user: User,
    repository: Repository,
) -> str:
    return (
        f"{BASE_URL}/git/"
        f"{user.username}/"
        f"{repository.name}.git"
    )


@pytest.fixture()
def git_workspace(tmp_path):
    with SessionLocal() as db:
        user, agent, token = create_test_identity(db)
        repository = create_test_repository(
            db,
            user,
        )

    workspace = tmp_path / "workspace"

    # Retry clone a few times to allow SQLite cross-process visibility on Windows
    for attempt in range(5):
        try:
            run_git(
                "clone",
                authenticated_url(
                    user,
                    repository,
                ),
                str(workspace),
                env=git_env(agent.token_prefix, token),
            )
            break
        except AssertionError:
            if attempt == 4:
                raise
            import time
            time.sleep(0.5)

    run_git(
        "config",
        "user.name",
        "SUTRA Integration Agent",
        cwd=workspace,
    )

    run_git(
        "config",
        "user.email",
        "integration@sutra.local",
        cwd=workspace,
    )

    return {
        "workspace": workspace,
        "user": user,
        "agent": agent,
        "token": token,
        "repository": repository,
    }


def test_real_agent_git_clone_works(git_workspace):
    workspace = git_workspace["workspace"]

    result = run_git(
        "branch",
        "--show-current",
        cwd=workspace,
    )

    assert result.stdout.strip() == "main"


def test_real_agent_git_push_creates_branch(
    git_workspace,
):
    workspace = git_workspace["workspace"]

    marker = (
        workspace
        / "integration-test.txt"
    )

    marker.write_text(
        "real SUTRA Git integration test\n",
        encoding="utf-8",
    )

    run_git(
        "add",
        "integration-test.txt",
        cwd=workspace,
    )

    run_git(
        "commit",
        "-m",
        "test: real agent git integration",
        cwd=workspace,
    )

    branch_name = (
        f"integration-live-"
        f"{int(time.time() * 1000)}"
    )

    result = run_git(
        "push",
        "origin",
        f"HEAD:refs/heads/{branch_name}",
        cwd=workspace,
        check=False,
        env=git_env(git_workspace["agent"].token_prefix, git_workspace["token"]),
    )

    assert result.returncode == 0, (
        result.stdout
        + "\n"
        + result.stderr
    )

    refs = run_git(
        "ls-remote",
        authenticated_url(
            git_workspace["user"],
            git_workspace["repository"],
        ),
        env=git_env(git_workspace["agent"].token_prefix, git_workspace["token"]),
    )

    assert (
        f"refs/heads/{branch_name}"
        in refs.stdout
    )


def test_real_agent_git_push_creates_event(
    git_workspace,
):
    workspace = git_workspace["workspace"]

    marker = (
        workspace
        / "event-test.txt"
    )

    marker.write_text(
        "event integration test\n",
        encoding="utf-8",
    )

    run_git(
        "add",
        "event-test.txt",
        cwd=workspace,
    )

    run_git(
        "commit",
        "-m",
        "test: git push event",
        cwd=workspace,
    )

    run_git(
        "push",
        "origin",
        "HEAD:main",
        cwd=workspace,
        env=git_env(git_workspace["agent"].token_prefix, git_workspace["token"]),
    )

    with SessionLocal() as db:
        repository_id = (
            git_workspace["repository"].id
        )

        events = db.scalars(
            select(GitPushEvent)
            .where(
                GitPushEvent.repository_id
                == repository_id
            )
        ).all()

        assert len(events) >= 1

        event = events[-1]

        if event.status != "processed":
            processor = GitPushEventProcessor(db)
            processor.process_event(
                event.id
            )
            db.refresh(event)

        assert event.status == "processed"