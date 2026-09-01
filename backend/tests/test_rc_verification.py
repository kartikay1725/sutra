import base64
import os
import socket
import subprocess
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

import pytest
import uvicorn
from sqlalchemy import select, text
from sqlalchemy.orm import sessionmaker

from app.core.security import hash_password
from app.db.session import SessionLocal
from app.main import app
from app.models.actor import Actor
from app.models.agent import Agent
from app.models.change import Change
from app.models.git_push_event import GitPushEvent
from app.models.repository import Repository
from app.models.user import User
from app.services.git_push_event_processor import GitPushEventProcessor
from app.services.git_push_event_service import GitPushEventService, LeaseLostError
from app.services.git_push_event_worker import GitPushEventWorker
from app.services.repository_service import RepositoryService


def free_port() -> int:
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    return port


def run_git(args: list[str], cwd: Path | None = None, env: dict[str, str] | None = None):
    result = subprocess.run(
        ["git", "-c", "credential.helper=", *args],
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise AssertionError(
            f"Git command failed (exit {result.returncode}): git {' '.join(args)}\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )
    return result


def git_env(token: str) -> dict[str, str]:
    encoded = base64.b64encode(f"{token[:16]}:{token}".encode()).decode()
    env = dict(os.environ)
    env["GIT_TERMINAL_PROMPT"] = "0"
    env["GIT_CONFIG_COUNT"] = "1"
    env["GIT_CONFIG_KEY_0"] = "http.extraHeader"
    env["GIT_CONFIG_VALUE_0"] = f"Authorization: Basic {encoded}"
    return env


def get_pg_db():
    from app.db.session import SessionLocal
    return SessionLocal()


def cleanup_db(db):
    cleanup_statements = [
        # Leaf records
        "DELETE FROM assistant_messages",
        "DELETE FROM discussion_comments",
        "DELETE FROM issue_comments",
        "DELETE FROM change_files",
        "DELETE FROM change_events",
        "DELETE FROM change_dependencies",
        "DELETE FROM inline_review_comments",
        "DELETE FROM task_events",

        # Records depending on higher-level entities
        "DELETE FROM change_reviews",
        "DELETE FROM ci_jobs",
        "DELETE FROM deployments",
        "DELETE FROM artifacts",
        "DELETE FROM environments",
        "DELETE FROM pull_requests",
        "DELETE FROM tasks",

        # User/auth state
        "DELETE FROM agent_repository_access",
        "DELETE FROM agent_sessions",
        "DELETE FROM agent_messages",
        "DELETE FROM user_sessions",
        "DELETE FROM webauthn_credentials",
        "DELETE FROM notifications",
        "DELETE FROM assistant_threads",
        "DELETE FROM agent_registration_requests",
        "DELETE FROM organization_members",

        # Repository / agent / branch protection
        "DELETE FROM git_push_events",
        "DELETE FROM branch_protection_rules",
        "DELETE FROM changes",
        "DELETE FROM repositories",
        "DELETE FROM agents",

        # Other repository-related state
        "DELETE FROM repository_stars",
        "DELETE FROM knowledge_edges",
        "DELETE FROM knowledge_nodes",

        # Root identities
        "DELETE FROM users",
        "DELETE FROM actors",
    ]

    for sql in cleanup_statements:
        db.execute(text(sql))

    db.commit()
def test_rc_real_git_e2e_and_idempotency(tmp_path):
    """
    Step 3: Real Git Push E2E Test (No Mocks).
    """
    db = get_pg_db()
    cleanup_db(db)
    port = free_port()
    config = uvicorn.Config(app=app, host="127.0.0.1", port=port, log_level="error")
    server = uvicorn.Server(config=config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()

    deadline = time.time() + 15
    while time.time() < deadline:
        if server.started:
            break
        time.sleep(0.1)

    if not server.started:
        server.should_exit = True
        thread.join(timeout=5)
        raise RuntimeError("Uvicorn test server failed to start")

    try:
        from tests.test_git_http_agent_integration import create_test_identity, create_test_repository, git_env

        user, agent, actor, token, session_token = create_test_identity(db)
        repo = create_test_repository(db, user)

        repo_url = f"http://127.0.0.1:{port}/git/{user.username}/{repo.name}.git"
        work_dir = tmp_path / "work"
        env = git_env(agent.token_prefix, session_token)

        run_git(["clone", repo_url, str(work_dir)], env=env)
        run_git(["config", "user.email", "rc@example.com"], cwd=work_dir, env=env)
        run_git(["config", "user.name", "RC Agent"], cwd=work_dir, env=env)

        test_file = work_dir / "file.txt"
        test_file.write_text("RC verification content\n", encoding="utf-8")

        run_git(["add", "file.txt"], cwd=work_dir, env=env)
        run_git(["commit", "-m", "Initial RC commit"], cwd=work_dir, env=env)

        # Push through Git HTTP backend
        run_git(["push", "origin", "main"], cwd=work_dir, env=env)

        # Verify GitPushEvent is persisted
        db.expire_all()
        events = db.scalars(
            select(GitPushEvent).where(GitPushEvent.repository_id == repo.id)
        ).all()
        assert len(events) == 1, "GitPushEvent must be persisted"
        event = events[0]
        assert event.status == GitPushEvent.STATUS_PENDING

        # Start/run actual worker cycle
        worker = GitPushEventWorker(batch_size=10, interval_seconds=1.0)
        claimed_count = worker.run_once()
        assert claimed_count >= 1, "Worker should claim events"

        # Verify event reaches processed status
        db.expire_all()
        event = db.get(GitPushEvent, event.id)
        assert event.status == GitPushEvent.STATUS_PROCESSED

        # Verify exactly one Change exists
        changes = db.scalars(
            select(Change).where(Change.repository_id == repo.id)
        ).all()
        assert len(changes) == 1, "Exactly one Change must exist"
        change = changes[0]

        # Verify operation_key exists and is 64 characters
        assert change.operation_key is not None
        assert len(change.operation_key) == 64

        # Repeat identical semantic operation (process claimed event again / repeat worker on same push event)
        processor = GitPushEventProcessor(db)
        # Attempting to process the same event payload / operation again
        processor.process_claimed_event(event, worker_id="repeat-worker")

        # Verify Change count remains exactly one
        changes_after = db.scalars(
            select(Change).where(Change.repository_id == repo.id)
        ).all()
        assert len(changes_after) == 1, "Change count must remain exactly one (idempotent)"

    finally:
        db.close()
        server.should_exit = True


def test_rc_real_worker_crash_recovery():
    """
    Step 4: Real Worker Crash & Recovery Test.
    """
    db = get_pg_db()
    cleanup_db(db)
    user = User(
        id=str(uuid4()),
        username=f"crash_user_{uuid4().hex[:8]}",
        email=f"crash_user_{uuid4().hex[:8]}@example.com",
        password_hash=hash_password("password123"),
    )
    db.add(user)
    db.flush()

    repo_svc = RepositoryService(db)
    repo = repo_svc.create(
        owner_id=user.id,
        name="crash_repo",
        description="Crash test repo",
        visibility="private",
    )

    agent = Agent(
        id=str(uuid4()),
        owner_id=user.id,
        name="crash_agent",
        token_prefix="crash_prefix_123",
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
            '["repository.read",'
            '"repository.write",'
            '"change.create",'
            '"change.commit",'
            '"change.conflict.read"]'
        ),
    )
    db.add(actor)
    db.commit()

    service = GitPushEventService(db)

    # Create event
    event = service.create_event(
        repository=repo,
        actor=actor,
        before_refs={"refs/heads/main": "0000000000000000000000000000000000000000"},
        after_refs={"refs/heads/main": "1111111111111111111111111111111111111111"},
    )
    db.commit()
    event_id = event.id

    # Worker A claims event
    worker_a_id = "worker-A-crash"
    claimed = service.claim_pending(limit=1, worker_id=worker_a_id)
    assert len(claimed) == 1
    db.commit()

    # Simulate Worker A crashing before finalization, lease expires
    event_db = db.get(GitPushEvent, event_id)
    now = datetime.now(timezone.utc)
    event_db.lease_expires_at = now - timedelta(seconds=10)
    event_db.updated_at = now - timedelta(seconds=10)
    db.commit()

    # Worker B starts, recovers stale event
    service.recover_stale_processing(timeout_seconds=1)
    db.commit()

    event_db = db.get(GitPushEvent, event_id)
    event_db.next_attempt_at = now - timedelta(seconds=10)
    db.commit()

    # Worker B claims event
    worker_b_id = "worker-B-recovery"
    claimed_b = service.claim_pending(limit=1, worker_id=worker_b_id)
    assert len(claimed_b) == 1
    db.commit()

    # Worker B processes event
    processor_b = GitPushEventProcessor(db)
    # Stub resolve commit to bypass filesystem git lookup for dummy commits
    processor_b.changes.resolve_commit = lambda r, c: c
    processor_b.changes._classify_ref_update = lambda r, b, a: "update"
    processor_b.changes.get_changed_files = lambda r, b, a: []

    result_b = processor_b.process_claimed_event(claimed_b[0], worker_id=worker_b_id)
    db.commit()

    # Verify event is processed
    assert result_b.status == GitPushEvent.STATUS_PROCESSED

    # Verify Worker A cannot finalize afterward
    processor_a = GitPushEventProcessor(db)
    with pytest.raises((ValueError, LeaseLostError)):
        service.mark_processed(event_db, expected_worker_id=worker_a_id)

    # Verify exactly one Change exists
    changes = db.scalars(
        select(Change).where(Change.repository_id == repo.id)
    ).all()
    assert len(changes) == 1, "Exactly one Change must exist after crash recovery"
    db.close()
