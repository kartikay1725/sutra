import base64
import json
import socket
import subprocess
import threading
import time
from pathlib import Path
from uuid import uuid4

import pytest
import requests
import uvicorn
from sqlalchemy import select

from app.db.session import SessionLocal
from app.main import app
from app.models.actor import Actor
from app.models.user import User
from app.core.security import hash_password


pytestmark = pytest.mark.integration


def free_port() -> int:
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    return port


@pytest.fixture(scope="module")
def api_server():
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
        raise RuntimeError("Uvicorn test server failed to start")

    yield port

    server.should_exit = True
    thread.join(timeout=10)


def run_git(
    args: list[str],
    cwd: Path | None = None,
    *,
    env: dict[str, str] | None = None,
):
    command = ["git", "-c", "credential.helper="]
    if env is not None:
        auth_header = env.get("GIT_CONFIG_VALUE_0")
        if env.get("GIT_CONFIG_KEY_0") == "http.extraHeader" and auth_header:
            command.extend(["-c", f"http.extraHeader={auth_header}"])

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
    encoded = base64.b64encode(f"{username}:{password}".encode()).decode()
    import os
    env = dict()
    env.update(os.environ)
    env["GIT_TERMINAL_PROMPT"] = "0"
    env["GIT_CONFIG_COUNT"] = "1"
    env["GIT_CONFIG_KEY_0"] = "http.extraHeader"
    env["GIT_CONFIG_VALUE_0"] = f"Authorization: Basic {encoded}"
    return env


def create_test_user(db):
    from tests.conftest import ensure_test_actor
    suffix = uuid4().hex[:10]
    username = f"integration-{suffix}"
    password = "integration-password"

    user = User(
        id=str(uuid4()),
        username=username,
        email=f"integration-{suffix}@example.com",
        password_hash=hash_password(password),
        email_verified=True,
    )
    db.add(user)
    db.flush()
    ensure_test_actor(db, user)
    db.commit()
    return user, username, password


def test_external_agent_lifecycle(api_server, tmp_path):
    port = api_server
    base_url = f"http://127.0.0.1:{port}"

    with SessionLocal() as db:
        user, username, password = create_test_user(db)
        # We need a repository
        from app.services.repository_service import RepositoryService
        repository = RepositoryService(db).create(
            owner_id=user.id,
            name=f"agent-test-{uuid4().hex[:8]}",
            description="Agent test repository",
            visibility="private",
        )
        db.commit()
        repo_id = repository.id
        repo_name = repository.name

    # 1. Login Human
    r = requests.post(
        f"{base_url}/v1/auth/login",
        json={"login": username, "password": password},
    )
    assert r.status_code == 200
    human_token = r.json()["access_token"]
    human_headers = {"Authorization": f"Bearer {human_token}"}

    # 2. External Agent Hits Info/Handshake
    r = requests.get(f"{base_url}/v1/agent-info")
    assert r.status_code == 200

    r = requests.post(
        f"{base_url}/v1/agent-protocol/handshake",
        json={
            "protocol": "sutra-agent",
            "protocol_version": "1",
            "client_name": "test-agent",
            "client_type": "external"
        }
    )
    assert r.status_code == 200
    handshake = r.json()
    assert "git_instructions" in handshake

    # 3. Agent Registers
    agent_name = f"test-agent-{uuid4().hex[:6]}"
    r = requests.post(
        f"{base_url}/v1/agents/register",
        json={
            "agent_name": agent_name,
            "agent_description": "Integration test agent",
            "repo_name": repo_name,
            "owner_username": username,
            "requested_capabilities": [
                "repository.read",
                "repository.write",
                "change.create",
                "change.commit",
                "change.conflict.read"
            ]
        }
    )
    assert r.status_code == 201
    reg_id = r.json()["id"]
    polling_token = r.json()["polling_token"]

    # 4. Human Approves Registration
    r = requests.post(
        f"{base_url}/v1/agents/registrations/{reg_id}/approve",
        headers=human_headers
    )
    assert r.status_code == 200

    # 5. Agent Polls Status and Gets Token
    r = requests.get(f"{base_url}/v1/agents/register/{reg_id}/status?polling_token={polling_token}")
    assert r.status_code == 200
    status_data = r.json()
    assert status_data["status"] == "approved"
    permanent_token = status_data["permanent_token"]

    # 6. Agent Creates Session
    r = requests.post(
        f"{base_url}/v1/agents/session",
        json={"token": permanent_token}
    )
    assert r.status_code == 201
    session_data = r.json()
    session_token = session_data["token"]
    agent_headers = {"Authorization": f"Bearer {session_token}"}

    # Agent Polls Protocol (discovery)
    r = requests.post(
        f"{base_url}/v1/agent-protocol/poll",
        headers=agent_headers
    )
    assert r.status_code == 200

    # 9. Agent Git Clone & Push
    repo_url = f"{base_url}/git/{username}/{repo_name}.git"
    worktree = tmp_path / "worktree"
    
    agent_token_prefix = permanent_token[:16]
    env = git_env(agent_token_prefix, session_token)
    
    res = run_git(["clone", repo_url, str(worktree)], env=env)
    assert res.returncode == 0

    readme = worktree / "README.md"
    readme.write_text("Hello World", encoding="utf-8")
    run_git(["config", "user.name", "Agent"], cwd=worktree)
    run_git(["config", "user.email", "agent@sutra.dev"], cwd=worktree)
    run_git(["add", "README.md"], cwd=worktree)
    run_git(["commit", "-m", "Initial commit"], cwd=worktree)
    
    res = run_git(["push", "origin", "main"], cwd=worktree, env=env)
    assert res.returncode == 0
    
    # Get resulting commit
    res = run_git(["rev-parse", "HEAD"], cwd=worktree)
    head_commit = res.stdout.strip()

    # Process push event
    with SessionLocal() as worker_db:
        from app.models.git_push_event import GitPushEvent
        from app.services.git_push_event_processor import GitPushEventProcessor
        from app.models.change import Change

        events = worker_db.scalars(
            select(GitPushEvent).where(GitPushEvent.repository_id == repo_id)
        ).all()
        for ev in events:
            if ev.status != "processed":
                GitPushEventProcessor(worker_db).process_event(ev.id)

        changes = worker_db.scalars(
            select(Change).where(Change.repository_id == repo_id)
        ).all()
        assert len(changes) >= 1
        change = changes[0]
        change_id = change.id

    # 10. Agent Creates PR from the recorded Change
    with SessionLocal() as debug_db:
        from app.models.repository import Repository
        from app.models.actor import Actor
        from app.models.change import Change

        debug_repo = debug_db.get(Repository, repo_id)
        debug_change = debug_db.get(Change, change_id)

        debug_actor = None
        if debug_change is not None:
            debug_actor = debug_db.get(Actor, debug_change.actor_id)

        print("\n========== PR FK DEBUG ==========")
        print("repo_id:", repo_id)
        print("repo_exists:", debug_repo is not None)

        print("change_id:", change_id)
        print("change_exists:", debug_change is not None)

        if debug_change is not None:
            print("change.repository_id:", debug_change.repository_id)
            print("change.actor_id:", debug_change.actor_id)
            print("change.resulting_commit:", debug_change.resulting_commit)

        print(
            "actor_exists:",
            debug_actor is not None,
        )

        if debug_actor is not None:
            print("actor.id:", debug_actor.id)
            print("actor.type:", debug_actor.type)

        print("================================\n")
    r = requests.post(
        f"{base_url}/v1/pull-requests/agent",
        headers=agent_headers,
        json={
            "repository_id": repo_id,
            "source_change_id": change_id,
            "title": "Add README",
            "target_branch": "main",
            "is_draft": False
        }
    )
    assert r.status_code == 201
    pr_id = r.json()["id"]
    
    # 11. Validate the PR exists and is accessible
    r = requests.get(f"{base_url}/v1/pull-requests/{pr_id}", headers=human_headers)
    assert r.status_code == 200
    assert r.json()["title"] == "Add README"
