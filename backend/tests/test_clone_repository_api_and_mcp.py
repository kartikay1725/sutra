"""Tests for Repository Clone API, MCP sutra_clone_repository, and sutra_create_discussion."""
from contextlib import asynccontextmanager
import json
import os
from pathlib import Path
import secrets
import shutil
import subprocess
from datetime import datetime, timedelta, timezone

import httpx
import pytest
from sqlalchemy import select

from app.core.config import settings
from app.core.security import hash_password
from app.db.session import SessionLocal
from app.main import app
from app.mcp.server import mcp_server
from app.models.actor import Actor
from app.models.agent import Agent
from app.models.agent_repository_access import AgentRepositoryAccess
from app.models.agent_session import AgentSession
from app.models.discussion import Discussion
from app.models.repository import Repository
from app.models.task import Task
from app.models.user import User
from app.services.repository_service import RepositoryService


@pytest.fixture
def db_session():
    with SessionLocal() as db:
        yield db


@pytest.fixture
def temp_source_git_repo(tmp_path):
    """Creates a local git repository with an initial commit to act as the clone source."""
    source_dir = tmp_path / "source_repo"
    source_dir.mkdir()
    subprocess.run(["git", "init", "-b", "main"], cwd=source_dir, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test Committer"], cwd=source_dir, check=True)
    subprocess.run(["git", "config", "user.email", "test@sutra.local"], cwd=source_dir, check=True)
    
    readme = source_dir / "README.md"
    readme.write_text("# Test Cloned Repo\nSample content for SUTRA clone test.")
    
    subprocess.run(["git", "add", "README.md"], cwd=source_dir, check=True)
    subprocess.run(["git", "commit", "-m", "Initial test commit"], cwd=source_dir, check=True)
    return str(source_dir)


@asynccontextmanager
async def run_mcp():
    mcp_server.session_manager._has_started = False
    async with mcp_server.session_manager.run():
        yield


def extract_tool_result(result: dict) -> dict:
    if "structuredContent" in result and result["structuredContent"]:
        sc = result["structuredContent"]
        if isinstance(sc, dict) and "result" in sc:
            return sc["result"]
        return sc
    if "content" in result and result["content"]:
        return json.loads(result["content"][0]["text"])
    return result


@pytest.fixture
def clone_test_environment(db_session):
    now = datetime.now(timezone.utc)
    uid = secrets.token_hex(8)

    owner = User(
        id=f"user_{uid}",
        username=f"clone_owner_{uid}",
        email=f"owner_{uid}@sutra.test",
        password_hash=hash_password("testpass123"),
        email_verified=True,
    )
    db_session.add(owner)

    owner_actor = Actor(
        id=owner.id,
        owner_id=owner.id,
        type="human",
        name=owner.username,
        capabilities="[]",
    )
    db_session.add(owner_actor)

    raw_agent_token = f"sutra_agent_{secrets.token_urlsafe(32)}"
    agent = Agent(
        id=f"agnt_{uid}",
        owner_id=owner.id,
        name=f"test-clone-agent-{uid}",
        token_hash=hash_password(raw_agent_token),
        token_prefix=raw_agent_token[:16],
        status="active",
        is_active=True,
    )
    db_session.add(agent)

    agent_actor = Actor(
        id=agent.id,
        owner_id=owner.id,
        type="agent",
        name=agent.name,
        capabilities=json.dumps(["repository.read", "repository.write"]),
    )
    db_session.add(agent_actor)

    raw_session_token = f"sutra_session_{secrets.token_urlsafe(32)}"
    session = AgentSession(
        id=f"sess_{uid}",
        agent_id=agent.id,
        token_hash=hash_password(raw_session_token),
        token_prefix=raw_session_token[:32],
        status="active",
        expires_at=now + timedelta(hours=1),
        last_seen_at=now,
    )
    db_session.add(session)

    db_session.commit()

    yield {
        "owner": owner,
        "agent": agent,
        "agent_token": raw_agent_token,
        "session": session,
        "session_token": raw_session_token,
    }

    # Teardown
    try:
        tasks = db_session.scalars(select(Task).where(Task.created_by == owner.id)).all()
        for t in tasks:
            db_session.delete(t)
        db_session.commit()

        repos = db_session.scalars(select(Repository).where(Repository.owner_id == owner.id)).all()
        for r in repos:
            repo_path = Path(settings.repository_storage_path) / r.storage_key
            if repo_path.exists():
                shutil.rmtree(repo_path, ignore_errors=True)
            db_session.delete(r)
        db_session.commit()

        db_session.query(AgentSession).filter(AgentSession.id == session.id).delete()
        db_session.query(AgentRepositoryAccess).filter(AgentRepositoryAccess.agent_id == agent.id).delete()
        db_session.query(Actor).filter(Actor.id.in_([owner.id, agent.id])).delete()
        db_session.query(Agent).filter(Agent.id == agent.id).delete()
        db_session.query(User).filter(User.id == owner.id).delete()
        db_session.commit()
    except Exception:
        db_session.rollback()


@pytest.mark.asyncio
async def test_api_clone_repository(clone_test_environment, temp_source_git_repo, db_session):
    """Test POST /v1/repositories/clone endpoint."""
    owner = clone_test_environment["owner"]

    # Login to get JWT bearer token
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        login_res = await client.post(
            "/v1/auth/login",
            json={"login": owner.username, "password": "testpass123"},
        )
        assert login_res.status_code == 200, login_res.text
        token = login_res.json()["access_token"]
        auth_headers = {"Authorization": f"Bearer {token}"}

        # Clone repository
        clone_res = await client.post(
            "/v1/repositories/clone",
            headers=auth_headers,
            json={
                "url": temp_source_git_repo,
                "name": f"cloned-repo-{secrets.token_hex(4)}",
                "description": "Cloned via SUTRA API",
                "visibility": "private",
            },
        )
        assert clone_res.status_code == 201, clone_res.text
        data = clone_res.json()
        assert data["name"]
        assert data["default_branch"] in ("main", "master")
        assert data["connection_type"] == "owned"

        # Verify repo in DB
        repo = db_session.scalar(select(Repository).where(Repository.id == data["id"]))
        assert repo is not None
        assert repo.owner_id == owner.id

        # Verify bare repo and pre-receive hook
        repo_dir = Path(settings.repository_storage_path) / repo.storage_key
        assert repo_dir.exists()
        hook_path = repo_dir / "hooks" / "pre-receive"
        assert hook_path.exists()


@pytest.mark.asyncio
async def test_mcp_sutra_clone_repository(clone_test_environment, temp_source_git_repo, db_session):
    """Test sutra_clone_repository tool via official MCP server transport."""
    env = clone_test_environment
    auth_header = f"Bearer {env['session_token']}"

    target_name = f"mcp-cloned-{secrets.token_hex(4)}"

    async with run_mcp():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://localhost") as client:
            # 1. Initialize MCP session
            init_res = await client.post(
                "/v1/mcp",
                json={
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "initialize",
                    "params": {"protocolVersion": "2024-11-05", "capabilities": {}, "clientInfo": {"name": "test", "version": "1"}},
                },
                headers={"Authorization": auth_header, "Accept": "application/json, text/event-stream"},
            )
            assert init_res.status_code == 200, init_res.text
            session_id = init_res.headers.get("mcp-session-id")

            # 2. Call sutra_clone_repository
            call_res = await client.post(
                "/v1/mcp",
                json={
                    "jsonrpc": "2.0",
                    "id": 2,
                    "method": "tools/call",
                    "params": {
                        "name": "sutra_clone_repository",
                        "arguments": {
                            "url": temp_source_git_repo,
                            "name": target_name,
                            "description": "Cloned via MCP tool",
                            "visibility": "private",
                        },
                    },
                },
                headers={
                    "mcp-session-id": session_id,
                    "Authorization": auth_header,
                    "Accept": "application/json, text/event-stream",
                },
            )
            assert call_res.status_code == 200, call_res.text
            lines = [line.strip() for line in call_res.text.splitlines() if line.startswith("data: ")]
            assert len(lines) >= 1
            payload = json.loads(lines[0][len("data: "):])
            structured = extract_tool_result(payload["result"])

            assert structured.get("status") == "success"
            assert structured.get("name") == target_name

            # Verify agent repository access granted
            agent = env["agent"]
            access = db_session.scalar(
                select(AgentRepositoryAccess).where(
                    AgentRepositoryAccess.agent_id == agent.id,
                    AgentRepositoryAccess.repository_id == structured["repository_id"],
                )
            )
            assert access is not None


@pytest.mark.asyncio
async def test_mcp_sutra_create_discussion(clone_test_environment, db_session):
    """Test sutra_create_discussion tool via official MCP server transport."""
    env = clone_test_environment
    owner = env["owner"]
    agent = env["agent"]
    auth_header = f"Bearer {env['session_token']}"

    # Create dummy repo and task
    repo = RepositoryService(db_session).create(
        owner_id=owner.id,
        name=f"disc-repo-{secrets.token_hex(4)}",
        description="Discussion repo",
        visibility="private",
    )
    task = Task(
        id=f"task_{secrets.token_hex(8)}",
        repository_id=repo.id,
        created_by=owner.id,
        assigned_agent_id=agent.id,
        title="RFC: Cache layer architecture",
        description="Discuss cache invalidation",
        status=Task.STATUS_IN_PROGRESS,
    )
    db_session.add(task)
    db_session.commit()

    async with run_mcp():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://localhost") as client:
            # 1. Initialize MCP session
            init_res = await client.post(
                "/v1/mcp",
                json={
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "initialize",
                    "params": {"protocolVersion": "2024-11-05", "capabilities": {}, "clientInfo": {"name": "test", "version": "1"}},
                },
                headers={"Authorization": auth_header, "Accept": "application/json, text/event-stream"},
            )
            assert init_res.status_code == 200, init_res.text
            session_id = init_res.headers.get("mcp-session-id")

            # 2. Call sutra_create_discussion
            call_res = await client.post(
                "/v1/mcp",
                json={
                    "jsonrpc": "2.0",
                    "id": 2,
                    "method": "tools/call",
                    "params": {
                        "name": "sutra_create_discussion",
                        "arguments": {
                            "task_id": task.id,
                            "title": "Architecture RFC: Redis vs SQLite Ephemeral Caching",
                            "body": "Proposing Redis as shared cache to maintain consensus across agent sessions.",
                            "category": "Architecture",
                        },
                    },
                },
                headers={
                    "mcp-session-id": session_id,
                    "Authorization": auth_header,
                    "Accept": "application/json, text/event-stream",
                },
            )
            assert call_res.status_code == 200, call_res.text
            lines = [line.strip() for line in call_res.text.splitlines() if line.startswith("data: ")]
            assert len(lines) >= 1
            payload = json.loads(lines[0][len("data: "):])
            structured = extract_tool_result(payload["result"])

            assert structured.get("status") == "created"
            assert structured.get("title") == "Architecture RFC: Redis vs SQLite Ephemeral Caching"

            # Verify discussion record in DB
            disc = db_session.scalar(select(Discussion).where(Discussion.id == structured["discussion_id"]))
            assert disc is not None
            assert disc.author_id == agent.id
            assert disc.category == "Architecture"
