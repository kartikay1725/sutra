import json
from app.models import AgentRepositoryAccess
import base64
import socket
import subprocess
import threading
import time
from pathlib import Path
from uuid import uuid4

import pytest
import uvicorn
from sqlalchemy import select

from app.api.git_http import router
from app.db.session import SessionLocal
from app.main import app
from app.models.actor import Actor
from app.models.agent import Agent
from app.models.git_push_event import GitPushEvent
from app.models.user import User
from app.models.repository import Repository
from app.core.security import hash_password
from app.services.git_push_event_processor import GitPushEventProcessor
from app.services.repository_service import RepositoryService


pytestmark = pytest.mark.integration


def free_port() -> int:
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    return port


def run_git(
    args: list[str],
    cwd: Path | None = None,
    *,
    env: dict[str, str] | None = None,
):
    command = ["git", "-c", "credential.helper="]

    if env is not None:
        auth_header = env.get(
            "GIT_CONFIG_VALUE_0"
        )

        if (
            env.get("GIT_CONFIG_KEY_0")
            == "http.extraHeader"
            and auth_header
        ):
            command.extend(
                [
                    "-c",
                    f"http.extraHeader={auth_header}",
                ]
            )

    command.extend(args)

    result = subprocess.run(
        command,
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    return result

def git_env(username: str, password: str) -> dict[str, str]:
    """
    Supply Git credentials without allowing Git to prompt.
    """

    encoded = base64.b64encode(
        f"{username}:{password}".encode()
    ).decode()

    env = dict()

    import os

    env.update(os.environ)
    env["GIT_TERMINAL_PROMPT"] = "0"
    env["GIT_CONFIG_COUNT"] = "1"
    env["GIT_CONFIG_KEY_0"] = "http.extraHeader"
    env["GIT_CONFIG_VALUE_0"] = (
        f"Authorization: Basic {encoded}"
    )

    return env


def git_env_with_token(username: str, password: str) -> dict[str, str]:
    """
    Build an isolated Git environment containing exactly one
    SUTRA agent credential.
    """
    return git_env(username, password)


@pytest.fixture(scope="module")
def git_server():
    port = free_port()

    config = uvicorn.Config(
        app,
        host="127.0.0.1",
        port=port,
        log_level="warning",
    )

    server = uvicorn.Server(config)

    thread = threading.Thread(
        target=server.run,
        daemon=True,
    )

    thread.start()

    deadline = time.time() + 15

    while time.time() < deadline:
        if server.started:
            try:
                import socket
                with socket.create_connection(("127.0.0.1", port), timeout=0.5):
                    break
            except OSError:
                pass

        time.sleep(0.1)

    if not server.started:
        server.should_exit = True
        thread.join(timeout=5)
        raise RuntimeError(
            "Uvicorn test server failed to start"
        )

    yield port

    server.should_exit = True
    thread.join(timeout=10)


def create_test_identity(db):
    from tests.conftest import ensure_test_actor
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

    ensure_test_actor(db, user)

    token = (
        "sutra_agent_"
        + uuid4().hex
        + uuid4().hex
    )

    agent = Agent(
        id=str(uuid4()),
        owner_id=user.id,
        name="Integration Agent",
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

    return user, agent, actor, token, session_token


def create_test_repository(db, user):
    repository = RepositoryService(db).create(
        owner_id=user.id,
        name=f"integration-{uuid4().hex[:8]}",
        description="Real Git HTTP integration repository",
        visibility="private",
    )

    return repository


def test_agent_git_http_push_creates_event_and_change(
    git_server,
    tmp_path,
):
    port = git_server

    with SessionLocal() as db:
        user, agent, actor, token, session_token = create_test_identity(db)

        repository = create_test_repository(
            db,
            user,
        )

        from app.models.agent_repository_access import AgentRepositoryAccess
        import json
        access = AgentRepositoryAccess(
            agent_id=agent.id,
            repository_id=repository.id,
            permissions=json.dumps([
                "repository.read",
                "repository.write",
                "change.create",
                "change.commit",
                "change.conflict.read",
            ]),
            enabled=True,
        )
        db.add(access)
        db.commit()

        repo_url = (
            f"http://127.0.0.1:{port}/git/"
            f"{user.username}/{repository.name}.git"
        )

        worktree = (
            tmp_path
            / "agent-worktree"
        )

        env = git_env(agent.token_prefix, session_token)

        run_git(
            [
                "clone",
                repo_url,
                str(worktree),
            ],
            env=env,
        )

        readme = (
            worktree
            / "README.md"
        )

        readme.write_text(
            "# SUTRA Integration Test\n",
            encoding="utf-8",
        )

        run_git(
            [
                "config",
                "user.name",
                "SUTRA Integration Agent",
            ],
            cwd=worktree,
        )

        run_git(
            [
                "config",
                "user.email",
                "agent@sutra.local",
            ],
            cwd=worktree,
        )

        run_git(
            ["add", "README.md"],
            cwd=worktree,
        )

        run_git(
            [
                "commit",
                "-m",
                "test: agent git http push",
            ],
            cwd=worktree,
        )

        run_git(
            [
                "push",
                "origin",
                "HEAD:main",
            ],
            cwd=worktree,
            env=env,
        )

        db.expire_all()

        events = db.scalars(
            select(GitPushEvent)
            .where(
                GitPushEvent.repository_id
                == repository.id
            )
        ).all()

        assert len(events) == 1

        event = events[0]

        assert event.actor_id == agent.id
        assert event.status in {"pending", "processing", "processed"}

        if event.status != "processed":
            processor = GitPushEventProcessor(db)
            processor.process_event(event.id)
            db.refresh(event)

        assert event.status == "processed"

        from app.models.change import Change

        changes = db.scalars(
            select(Change)
            .where(
                Change.repository_id
                == repository.id,
                Change.actor_id
                == agent.id,
            )
        ).all()

        assert len(changes) == 1

        change = changes[0]

        assert change.resulting_commit is not None
        assert change.actor_id == agent.id


def test_agent_force_push_is_rejected_by_receive_hook(
    git_server,
    tmp_path,
):
    port = git_server

    with SessionLocal() as db:
        user, agent, actor, token, session_token = create_test_identity(db)

        repository = create_test_repository(
            db,
            user,
        )

        from app.models.agent_repository_access import AgentRepositoryAccess
        import json
        access = AgentRepositoryAccess(
            agent_id=agent.id,
            repository_id=repository.id,
            permissions=json.dumps([
                "repository.read",
                "repository.write",
                "change.create",
                "change.commit",
                "change.conflict.read",
            ]),
            enabled=True,
        )
        db.add(access)
        db.commit()

        repo_url = (
            f"http://127.0.0.1:{port}/git/"
            f"{user.username}/{repository.name}.git"
        )

        env = git_env(agent.token_prefix, session_token)

        worktree = (
            tmp_path
            / "force-push-worktree"
        )

        run_git(
            [
                "clone",
                repo_url,
                str(worktree),
            ],
            env=env,
        )

        run_git(
            [
                "config",
                "user.name",
                "SUTRA Integration Agent",
            ],
            cwd=worktree,
        )

        run_git(
            [
                "config",
                "user.email",
                "agent@sutra.local",
            ],
            cwd=worktree,
        )

        readme = worktree / "README.md"

        readme.write_text(
            "original\n",
            encoding="utf-8",
        )

        run_git(
            ["add", "README.md"],
            cwd=worktree,
        )

        run_git(
            [
                "commit",
                "-m",
                "test: original commit",
            ],
            cwd=worktree,
        )

        run_git(
            [
                "push",
                "origin",
                "HEAD:main",
            ],
            cwd=worktree,
            env=env,
        )

        original_sha = run_git(
            [
                "rev-parse",
                "HEAD",
            ],
            cwd=worktree,
        ).stdout.strip()

        readme.write_text(
            "rewritten history\n",
            encoding="utf-8",
        )

        run_git(
            [
                "add",
                "README.md",
            ],
            cwd=worktree,
        )

        run_git(
            [
                "commit",
                "--amend",
                "--no-edit",
            ],
            cwd=worktree,
        )

        force_push = subprocess.run(
            [
                "git",
                "push",
                "--force",
                "origin",
                "HEAD:main",
            ],
            cwd=worktree,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )

        assert force_push.returncode != 0

        combined_output = (
            force_push.stdout
            + "\n"
            + force_push.stderr
        )

        assert (
            "force update is blocked"
            in combined_output.lower()
        )

        repository_path = (
            Path(repository_service_storage_path())
            / repository.storage_key
        )

        result = subprocess.run(
            [
                "git",
                "--git-dir",
                str(repository_path),
                "rev-parse",
                "refs/heads/main",
            ],
            capture_output=True,
            text=True,
            check=True,
        )

        remote_sha = result.stdout.strip()

        assert remote_sha == original_sha

        db.expire_all()

        events = db.scalars(
            select(GitPushEvent)
            .where(
                GitPushEvent.repository_id
                == repository.id
            )
        ).all()

        # The first normal push is persisted.
        # The rejected force push must not create
        # another successful transport event.
        assert len(events) == 1


def repository_service_storage_path() -> str:
    from app.core.config import settings

    return settings.repository_storage_path


def test_revoked_agent_cannot_clone(
    git_server,
    tmp_path,
):
    port = git_server

    with SessionLocal() as db:
        user, agent, actor, token, session_token = create_test_identity(db)

        repository = create_test_repository(
            db,
            user,
        )

        from app.models.agent_repository_access import AgentRepositoryAccess
        import json
        access = AgentRepositoryAccess(
            agent_id=agent.id,
            repository_id=repository.id,
            permissions=json.dumps([
                "repository.read",
                "repository.write",
                "change.create",
                "change.commit",
                "change.conflict.read",
            ]),
            enabled=True,
        )
        db.add(access)
        db.commit()

        agent.is_active = False
        agent.status = "revoked"
        db.commit()

        repo_url = (
            f"http://127.0.0.1:{port}/git/"
            f"{user.username}/{repository.name}.git"
        )

        worktree = tmp_path / "revoked-agent-clone"

        result = subprocess.run(
            [
                "git",
                "-c",
                "credential.helper=",
                "clone",
                repo_url,
                str(worktree),
            ],
            capture_output=True,
            text=True,
            env={
                **git_env_with_token(agent.token_prefix, session_token),
                "GIT_TERMINAL_PROMPT": "0",
            },
            check=False,
        )

        assert result.returncode != 0
        assert (
            "Authentication failed"
            in result.stderr
            or "401"
            in result.stderr
            or "authentication"
            in result.stderr.lower()
            or "terminal prompts disabled"
            in result.stderr.lower()
        )


def test_revoked_agent_cannot_push(
    git_server,
    tmp_path,
):
    port = git_server

    with SessionLocal() as db:
        user, agent, actor, token, session_token = create_test_identity(db)

        repository = create_test_repository(
            db,
            user,
        )

        from app.models.agent_repository_access import AgentRepositoryAccess
        import json
        access = AgentRepositoryAccess(
            agent_id=agent.id,
            repository_id=repository.id,
            permissions=json.dumps([
                "repository.read",
                "repository.write",
                "change.create",
                "change.commit",
                "change.conflict.read",
            ]),
            enabled=True,
        )
        db.add(access)
        db.commit()

        repo_url = (
            f"http://127.0.0.1:{port}/git/"
            f"{user.username}/{repository.name}.git"
        )

        worktree = tmp_path / "revoked-agent-push"

        # Clone while the agent is valid.
        run_git(
            [
                "clone",
                repo_url,
                str(worktree),
            ],
            env=git_env_with_token(agent.token_prefix, session_token),
        )

        run_git(
            [
                "config",
                "user.name",
                "SUTRA Revoked Agent",
            ],
            cwd=worktree,
        )

        run_git(
            [
                "config",
                "user.email",
                "revoked@sutra.local",
            ],
            cwd=worktree,
        )

        marker = worktree / "revoked.txt"
        marker.write_text(
            "should not be pushed\n",
            encoding="utf-8",
        )

        run_git(
            ["add", "revoked.txt"],
            cwd=worktree,
        )

        run_git(
            [
                "commit",
                "-m",
                "test: revoked agent push",
            ],
            cwd=worktree,
        )

        # Revoke after the clone.
        agent.is_active = False
        agent.status = "revoked"
        db.commit()

        result = subprocess.run(
            [
                "git",
                "-c",
                "credential.helper=",
                "push",
                "origin",
                "HEAD:refs/heads/revoked-agent-test",
            ],
            cwd=worktree,
            capture_output=True,
            text=True,
            env={
                **git_env_with_token(agent.token_prefix, session_token),
                "GIT_TERMINAL_PROMPT": "0",
            },
            check=False,
        )

        assert result.returncode != 0

        combined = (
            result.stdout
            + "\n"
            + result.stderr
        ).lower()

        assert (
            "authentication failed" in combined
            or "authentication" in combined
            or "401" in combined
            or "terminal prompts disabled" in combined
        )

        
def test_agent_cannot_access_repository_owned_by_another_user(
    git_server,
    tmp_path,
):
    port = git_server

    with SessionLocal() as db:
        owner_a, agent_a, actor_a, token_a, session_token_a = create_test_identity(db)
        owner_b, agent_b, actor_b, token_b, session_token_b = create_test_identity(db)

        repository_b = create_test_repository(
            db,
            owner_b,
        )

        repo_url = (
            f"http://{agent_a.token_prefix}:{session_token_a}@127.0.0.1:{port}/git/"
            f"{owner_b.username}/{repository_b.name}.git"
        )

        result = subprocess.run(
            [
                "git",
                "-c",
                "credential.helper=",
                "ls-remote",
                repo_url,
            ],
            capture_output=True,
            text=True,
            env={
                **git_env(agent_a.token_prefix, session_token_a),
                "GIT_TERMINAL_PROMPT": "0",
            },
            check=False,
        )

        assert result.returncode != 0

        combined = (
            result.stdout + "\n" + result.stderr
        ).lower()

        assert (
            "403" in combined
            or "repository access denied" in combined
            or "access denied" in combined
        )


def test_agent_can_access_repository_owned_by_same_user(
    git_server,
    tmp_path,
):
    port = git_server

    with SessionLocal() as db:
        user, agent, actor, token, session_token = create_test_identity(db)

        repository = create_test_repository(
            db,
            user,
        )

        from app.models.agent_repository_access import AgentRepositoryAccess
        import json
        access = AgentRepositoryAccess(
            agent_id=agent.id,
            repository_id=repository.id,
            permissions=json.dumps([
                "repository.read",
                "repository.write",
                "change.create",
                "change.commit",
                "change.conflict.read",
            ]),
            enabled=True,
        )
        db.add(access)
        db.commit()

        repo_url = (
            f"http://{agent.token_prefix}:{session_token}@127.0.0.1:{port}/git/"
            f"{user.username}/{repository.name}.git"
        )

        result = subprocess.run(
            [
                "git",
                "-c",
                "credential.helper=",
                "ls-remote",
                repo_url,
            ],
            capture_output=True,
            text=True,
            env={
                **git_env(agent.token_prefix, session_token),
                "GIT_TERMINAL_PROMPT": "0",
            },
            check=False,
        )

        assert result.returncode == 0


def test_agent_git_permissions_scoping(git_server, tmp_path):
    port = git_server

    with SessionLocal() as db:
        user, agent, actor, token, session_token = create_test_identity(db)
        repository = create_test_repository(db, user)
        repo_url = f"http://127.0.0.1:{port}/git/{user.username}/{repository.name}.git"
        worktree = tmp_path / "git-scoping-worktree"

        # Helper to grant permissions
        def update_grant(perms, enabled=True):
            from app.models.agent_repository_access import AgentRepositoryAccess
            import json
            db.execute(
                select(AgentRepositoryAccess).where(
                    AgentRepositoryAccess.agent_id == agent.id,
                    AgentRepositoryAccess.repository_id == repository.id
                )
            )
            db.query(AgentRepositoryAccess).filter(
                AgentRepositoryAccess.agent_id == agent.id,
                AgentRepositoryAccess.repository_id == repository.id
            ).delete()
            access = AgentRepositoryAccess(
                agent_id=agent.id,
                repository_id=repository.id,
                permissions=json.dumps(perms),
                enabled=enabled
            )
            db.add(access)
            db.commit()

        # 1. repository.read only -> clone allowed, push denied
        update_grant(["repository.read"])
        env = git_env(agent.token_prefix, session_token)
        clone_res = run_git(["clone", repo_url, str(worktree)], env=env)
        assert clone_res.returncode == 0

        readme = worktree / "README.md"
        readme.write_text("Hello SUTRA")
        run_git(["add", "README.md"], cwd=worktree)
        run_git(["commit", "-m", "add readme"], cwd=worktree)

        push_res = subprocess.run(
            ["git", "-c", "credential.helper=", "push", "origin", "main"],
            cwd=worktree, env=env, capture_output=True, text=True
        )
        assert push_res.returncode != 0

        # 3. repository.read + repository.write -> push allowed
        update_grant(["repository.read", "repository.write"])
        push_res = subprocess.run(
            ["git", "-c", "credential.helper=", "push", "origin", "main"],
            cwd=worktree, env=env, capture_output=True, text=True
        )
        assert push_res.returncode == 0

        # 4. repository.read + change.commit, NO repository.write -> push denied
        readme.write_text("Modified README")
        run_git(["add", "README.md"], cwd=worktree)
        run_git(["commit", "-m", "update readme"], cwd=worktree)

        update_grant(["repository.read", "change.commit"])
        push_res = subprocess.run(
            ["git", "-c", "credential.helper=", "push", "origin", "main"],
            cwd=worktree, env=env, capture_output=True, text=True
        )
        assert push_res.returncode != 0

        # 5. repository.read + repository.write + change.commit -> push allowed
        update_grant(["repository.read", "repository.write", "change.commit"])
        push_res = subprocess.run(
            ["git", "-c", "credential.helper=", "push", "origin", "main"],
            cwd=worktree, env=env, capture_output=True, text=True
        )
        assert push_res.returncode == 0

        # 6. repository.write removed after previous successful access -> push denied
        readme.write_text("Second modification")
        run_git(["add", "README.md"], cwd=worktree)
        run_git(["commit", "-m", "second update"], cwd=worktree)

        update_grant(["repository.read", "change.commit"])
        push_res = subprocess.run(
            ["git", "-c", "credential.helper=", "push", "origin", "main"],
            cwd=worktree, env=env, capture_output=True, text=True
        )
        assert push_res.returncode != 0

        # 7. repository.write restored -> push allowed
        update_grant(["repository.read", "repository.write", "change.commit"])
        push_res = subprocess.run(
            ["git", "-c", "credential.helper=", "push", "origin", "main"],
            cwd=worktree, env=env, capture_output=True, text=True
        )
        assert push_res.returncode == 0

        # 8. unauthorized repository (access disabled) -> push denied
        update_grant(["repository.read", "repository.write", "change.commit"], enabled=False)
        push_res = subprocess.run(
            ["git", "-c", "credential.helper=", "push", "origin", "main"],
            cwd=worktree, env=env, capture_output=True, text=True
        )
        assert push_res.returncode != 0
