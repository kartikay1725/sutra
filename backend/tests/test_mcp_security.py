"""Adversarial security and 2026-07-28 modern protocol test suite for SUTRA MCP server."""
import asyncio
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
from app.models.change import Change
from app.models.pull_request import PullRequest
from app.models.repository import Repository
from app.models.task import Task
from app.models.user import User
from app.services.repository_service import RepositoryService
from tests.test_mcp_server import extract_tool_result, _create_real_child_commit


@pytest.fixture
def db_session():
    with SessionLocal() as db:
        yield db


@asynccontextmanager
async def run_mcp():
    mcp_server.session_manager._has_started = False
    async with mcp_server.session_manager.run():
        yield


@pytest.fixture
def setup_security_environment(db_session):
    now = datetime.now(timezone.utc)
    uid = secrets.token_hex(8)

    # 1. Human owner
    owner = User(
        id=f"user_{uid}",
        username=f"owner_{uid}",
        email=f"owner_{uid}@example.com",
        password_hash=hash_password("password123"),
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

    # 2. Target Repo 1 (primary)
    repo1 = RepositoryService(db_session).create(
        owner_id=owner.id,
        name=f"target-repo-{uid}",
        description="Target repo 1",
        visibility="private",
    )

    # 3. Foreign Repo 2 (isolated)
    repo2 = RepositoryService(db_session).create(
        owner_id=owner.id,
        name=f"foreign-repo-{uid}",
        description="Foreign repo 2",
        visibility="private",
    )

    # 4. Agent
    raw_agent_token = f"sutra_agent_{secrets.token_urlsafe(32)}"
    agent = Agent(
        id=f"agnt_{uid}",
        owner_id=owner.id,
        name=f"security-agent-{uid}",
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
        capabilities=json.dumps([
            "repository.read",
            "repository.write",
            "change.create",
            "change.commit",
            "change.conflict.read",
            "knowledge_graph.read",
        ]),
    )
    db_session.add(agent_actor)

    # Grant access to repo1 only
    access = AgentRepositoryAccess(
        agent_id=agent.id,
        repository_id=repo1.id,
        permissions=json.dumps([
            "repository.read",
            "repository.write",
            "change.create",
            "change.commit",
            "change.conflict.read",
            "knowledge_graph.read",
        ]),
        enabled=True,
    )
    db_session.add(access)
    db_session.commit()

    # 5. Authoritative Session
    from app.api.agent_dependencies import create_agent_session
    agent_session, raw_session_token = create_agent_session(agent, db_session)

    # 6. Task on repo1
    task = Task(
        id=f"task_{uid}",
        repository_id=repo1.id,
        created_by=owner.id,
        assigned_agent_id=agent.id,
        claimed_by_session_id=agent_session.id,
        lease_expires_at=now + timedelta(minutes=30),
        title="Implement secure change validation",
        description="Security test task",
        status=Task.STATUS_IN_PROGRESS,
        task_type=Task.TYPE_FEATURE,
        priority=Task.PRIORITY_HIGH,
        source="user",
    )
    db_session.add(task)
    db_session.commit()

    yield {
        "owner": owner,
        "repo1": repo1,
        "repo2": repo2,
        "agent": agent,
        "agent_token": raw_agent_token,
        "session": agent_session,
        "session_token": raw_session_token,
        "task": task,
    }

    try:
        db_session.rollback()
        for r in [repo1, repo2]:
            repo_path = (Path(settings.repository_storage_path).resolve() / r.storage_key).resolve()
            if repo_path.exists():
                shutil.rmtree(repo_path, ignore_errors=True)

        db_session.query(Change).filter(Change.repository_id.in_([repo1.id, repo2.id])).delete(synchronize_session=False)
        db_session.query(PullRequest).filter(PullRequest.repository_id.in_([repo1.id, repo2.id])).delete(synchronize_session=False)
        db_session.query(Task).filter(Task.repository_id.in_([repo1.id, repo2.id])).delete(synchronize_session=False)
        db_session.query(AgentRepositoryAccess).filter(AgentRepositoryAccess.repository_id.in_([repo1.id, repo2.id])).delete(synchronize_session=False)
        db_session.query(AgentSession).filter(AgentSession.agent_id == agent.id).delete(synchronize_session=False)
        db_session.query(Agent).filter(Agent.id == agent.id).delete(synchronize_session=False)
        db_session.query(Actor).filter(Actor.id.in_([agent.id, owner.id])).delete(synchronize_session=False)
        db_session.query(Repository).filter(Repository.id.in_([repo1.id, repo2.id])).delete(synchronize_session=False)
        db_session.query(User).filter(User.id == owner.id).delete(synchronize_session=False)
        db_session.commit()
    except Exception:
        db_session.rollback()


@pytest.mark.asyncio
async def test_modern_mcp_2026_single_exchange_protocol(setup_security_environment):
    """
    CHECK 1 & 2: Verify modern MCP 2026-07-28 single-exchange protocol path:
    - MCP-Protocol-Version: 2026-07-28
    - Mcp-Method: tools/call
    - Mcp-Name: sutra_get_context
    - Self-contained POST without requiring initialize or Mcp-Session-Id
    - JSON response format
    """
    env = setup_security_environment
    auth_header = f"Bearer {env['session_token']}"

    async with run_mcp():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://localhost") as client:
            # 1. Modern tools/list request
            list_res = await client.post(
                "/v1/mcp",
                json={
                    "jsonrpc": "2.0",
                    "id": 101,
                    "method": "tools/list",
                    "params": {
                        "_meta": {
                            "io.modelcontextprotocol/protocolVersion": "2026-07-28",
                            "io.modelcontextprotocol/clientCapabilities": {},
                            "io.modelcontextprotocol/clientInfo": {"name": "modern-agent", "version": "1.0"},
                        }
                    },
                },
                headers={
                    "MCP-Protocol-Version": "2026-07-28",
                    "Mcp-Method": "tools/list",
                    "Authorization": auth_header,
                    "Accept": "application/json, text/event-stream",
                },
            )
            assert list_res.status_code == 200
            list_data = list_res.json()
            assert "result" in list_data
            tools = [t["name"] for t in list_data["result"]["tools"]]
            assert "sutra_get_context" in tools
            assert "sutra_submit_change" in tools
            assert len(tools) == 8

            # 2. Modern tools/call request (no initialize, no Mcp-Session-Id)
            call_res = await client.post(
                "/v1/mcp",
                json={
                    "jsonrpc": "2.0",
                    "id": 102,
                    "method": "tools/call",
                    "params": {
                        "name": "sutra_get_context",
                        "arguments": {},
                        "_meta": {
                            "io.modelcontextprotocol/protocolVersion": "2026-07-28",
                            "io.modelcontextprotocol/clientCapabilities": {},
                        },
                    },
                },
                headers={
                    "MCP-Protocol-Version": "2026-07-28",
                    "Mcp-Method": "tools/call",
                    "Mcp-Name": "sutra_get_context",
                    "Authorization": auth_header,
                    "Accept": "application/json, text/event-stream",
                },
            )
            assert call_res.status_code == 200
            call_data = call_res.json()
            ctx_data = extract_tool_result(call_data["result"])
            assert ctx_data["identity"]["agent_id"] == env["agent"].id
            assert ctx_data["session"]["session_id"] == env["session"].id


@pytest.mark.asyncio
async def test_adversarial_submit_change_security(setup_security_environment, db_session):
    """
    CHECK 5: Adversarial security test for sutra_submit_change.
    Verifies all 9 failure modes fail closed:
    1. nonexistent SHA -> rejected
    2. commit from foreign repo -> rejected
    3. wrong branch -> rejected
    4. stale task lease -> rejected
    5. revoked session -> rejected
    6. commit belonging to another task -> rejected
    7. duplicate submission -> rejected
    8. commit already bound to another change -> rejected
    9. unauthorized repository -> rejected
    """
    env = setup_security_environment
    auth_header = f"Bearer {env['session_token']}"

    # Generate real valid commit in repo1
    base_sha1, valid_commit_sha1 = _create_real_child_commit(env["repo1"].storage_key)
    # Generate real valid commit in foreign repo2
    base_sha2, foreign_commit_sha2 = _create_real_child_commit(env["repo2"].storage_key)

    async with run_mcp():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://localhost") as client:
            async def submit(task_id, commit_sha, branch="agent/feature", token=None):
                res = await client.post(
                    "/v1/mcp",
                    json={
                        "jsonrpc": "2.0",
                        "id": secrets.randbelow(10000),
                        "method": "tools/call",
                        "params": {
                            "name": "sutra_submit_change",
                            "arguments": {
                                "task_id": task_id,
                                "commit_sha": commit_sha,
                                "intent": "Adversarial test intent",
                                "branch": branch,
                                "pr_title": "Test PR",
                                "base_branch": "main",
                                "base_commit": base_sha1,
                            },
                            "_meta": {
                                "io.modelcontextprotocol/protocolVersion": "2026-07-28",
                                "io.modelcontextprotocol/clientCapabilities": {},
                            },
                        },
                    },
                    headers={
                        "MCP-Protocol-Version": "2026-07-28",
                        "Mcp-Method": "tools/call",
                        "Mcp-Name": "sutra_submit_change",
                        "Authorization": token or auth_header,
                        "Accept": "application/json, text/event-stream",
                    },
                )
                assert res.status_code == 200
                return extract_tool_result(res.json()["result"])

            # 1. Nonexistent SHA -> must fail closed
            r1 = await submit(env["task"].id, "0000000000000000000000000000000000000000")
            assert r1["status"] == "error"
            msg1 = (r1.get("error") or r1.get("message", "")).lower()
            assert any(k in msg1 for k in ["rejected", "not found", "failed", "could not find"])

            # 2. Commit from foreign repo2 into repo1 task -> must fail closed (git ancestry/lookup fails)
            r2 = await submit(env["task"].id, foreign_commit_sha2)
            assert r2["status"] == "error"

            # 3. Successful legitimate submission first
            r_legit = await submit(env["task"].id, valid_commit_sha1, branch="agent/task-test")
            assert r_legit["status"] == "reconciled_and_submitted"

            # 4. Duplicate submission of same commit -> must fail closed
            r_dup = await submit(env["task"].id, valid_commit_sha1, branch="agent/task-test")
            assert r_dup["status"] == "error"
            msg_dup = (r_dup.get("error") or r_dup.get("message", "")).lower()
            assert "already been recorded" in msg_dup

            # 5. Wrong branch for existing change -> must fail closed
            r_wrong_branch = await submit(env["task"].id, valid_commit_sha1, branch="agent/tampered-branch")
            assert r_wrong_branch["status"] == "error"
            msg_wb = (r_wrong_branch.get("error") or r_wrong_branch.get("message", "")).lower()
            assert "branch mismatch" in msg_wb

            # 6. Commit already bound to another task/change -> create task2 and try to bind valid_commit_sha1
            now = datetime.now(timezone.utc)
            task2 = Task(
                id=f"task_second_{secrets.token_hex(4)}",
                repository_id=env["repo1"].id,
                created_by=env["owner"].id,
                assigned_agent_id=env["agent"].id,
                claimed_by_session_id=env["session"].id,
                lease_expires_at=now + timedelta(minutes=30),
                title="Task 2",
                description="Task 2",
                status=Task.STATUS_IN_PROGRESS,
                task_type=Task.TYPE_FEATURE,
                source="user",
            )
            db_session.add(task2)
            db_session.commit()

            r_stolen_commit = await submit(task2.id, valid_commit_sha1, branch="agent/task2")
            assert r_stolen_commit["status"] == "error"
            msg_stolen = (r_stolen_commit.get("error") or r_stolen_commit.get("message", "")).lower()
            assert "already bound" in msg_stolen

            # 7. Stale task lease -> expire lease on task2 and submit
            task2.lease_expires_at = now - timedelta(minutes=10)
            db_session.commit()
            r_stale_lease = await submit(task2.id, "1111111111111111111111111111111111111111")
            assert r_stale_lease["status"] == "error"
            msg_stale = (r_stale_lease.get("error") or r_stale_lease.get("message", "")).lower()
            assert "lease expired" in msg_stale

            # 8. Unauthorized repository -> agent attempts to operate on repo2 where it has no access
            task_foreign = Task(
                id=f"task_foreign_{secrets.token_hex(4)}",
                repository_id=env["repo2"].id,
                created_by=env["owner"].id,
                assigned_agent_id=env["agent"].id,
                claimed_by_session_id=env["session"].id,
                lease_expires_at=now + timedelta(minutes=30),
                title="Unauthorized Foreign Task",
                description="Foreign task",
                status=Task.STATUS_IN_PROGRESS,
                task_type=Task.TYPE_FEATURE,
                source="user",
            )
            db_session.add(task_foreign)
            db_session.commit()

            r_unauthorized_repo = await submit(task_foreign.id, foreign_commit_sha2)
            assert r_unauthorized_repo["status"] == "error"
            msg_unauth = (r_unauthorized_repo.get("error") or r_unauthorized_repo.get("message", "")).lower()
            assert any(k in msg_unauth for k in ["access", "permission", "unauthorized", "denied"])

            # 9. Revoked session -> immediate distributed revocation must fail closed
            from app.api.agent_dependencies import revoke_agent_session
            revoke_agent_session(env["session"], db_session)

            r_revoked = await submit(env["task"].id, valid_commit_sha1)
            assert r_revoked["status"] == "error"
            raw_err = r_revoked.get("error")
            msg_revoked = (json.dumps(raw_err) if isinstance(raw_err, dict) else str(raw_err or "")).lower()
            assert "revoked" in msg_revoked or "session" in msg_revoked or r_revoked.get("details", {}).get("code") == 401


@pytest.mark.asyncio
async def test_real_mcp_client_e2e_flow(setup_security_environment, db_session):
    """
    CHECK 9: Use official real MCP client (mcp.client.session.ClientSession) over
    Streamable HTTP transport to perform the complete lifecycle:
    1. discover SUTRA (server/discover)
    2. list tools (tools/list)
    3. call sutra_get_context
    4. call sutra_start_task
    5. perform test terminal commit
    6. call sutra_submit_change
    7. inspect status (sutra_get_status)
    8. request merge (sutra_request_merge) -> verify human approval boundary
    """
    import httpx2
    from mcp.client.session import ClientSession
    from mcp.client.streamable_http import streamable_http_client

    env = setup_security_environment
    repo = env["repo1"]
    agent = env["agent"]

    # Create a fresh task in STATUS_OPEN for this flow
    flow_task = Task(
        id=f"task_flow_{secrets.token_hex(4)}",
        repository_id=repo.id,
        created_by=env["owner"].id,
        assigned_agent_id=agent.id,
        title="Implement End-to-End MCP Client Flow",
        description="Verify real ClientSession interaction",
        status=Task.STATUS_OPEN,
        priority=Task.PRIORITY_HIGH,
        task_type=Task.TYPE_FEATURE,
        source="user",
    )
    db_session.add(flow_task)
    db_session.commit()

    # Re-issue active session for the agent
    from app.api.agent_dependencies import create_agent_session
    fresh_session, fresh_token = create_agent_session(agent, db_session)
    auth_header = f"Bearer {fresh_token}"

    async with run_mcp():
        http_client = httpx2.AsyncClient(
            transport=httpx2.ASGITransport(app=app),
            base_url="http://localhost",
            headers={"Authorization": auth_header},
        )
        async with streamable_http_client("http://localhost/v1/mcp", http_client=http_client) as (read_stream, write_stream):
            async with ClientSession(read_stream, write_stream) as session:
                # 1. Discover SUTRA via modern server/discover
                discover_result = await session.discover()
                assert discover_result is not None
                assert "2026-07-28" in discover_result.supported_versions
                assert discover_result.capabilities.tools is not None

                # 2. List tools via tools/list
                tools_result = await session.list_tools()
                tool_names = [t.name for t in tools_result.tools]
                expected_tools = [
                    "sutra_get_context",
                    "sutra_search_knowledge",
                    "sutra_start_task",
                    "sutra_submit_change",
                    "sutra_get_status",
                    "sutra_request_merge",
                    "sutra_get_provenance",
                    "sutra_create_issue",
                ]
                for et in expected_tools:
                    assert et in tool_names

                # 3. Call sutra_get_context
                ctx_res = await session.call_tool("sutra_get_context", {})
                assert ctx_res is not None
                ctx_payload = json.loads(ctx_res.content[0].text)
                assert ctx_payload["identity"]["agent_id"] == agent.id
                assert ctx_payload["session"]["session_id"] == fresh_session.id

                # 4. Call sutra_start_task
                start_res = await session.call_tool("sutra_start_task", {"task_id": flow_task.id})
                start_payload = json.loads(start_res.content[0].text)
                assert start_payload["status"] == "claimed"
                assert start_payload["task_id"] == flow_task.id

                # 5. Perform test terminal commit in repository
                base_sha, child_commit_sha = _create_real_child_commit(repo.storage_key)

                # 6. Call sutra_submit_change
                submit_res = await session.call_tool(
                    "sutra_submit_change",
                    {
                        "task_id": flow_task.id,
                        "commit_sha": child_commit_sha,
                        "intent": "Implemented real MCP client flow verification",
                        "branch": "agent/flow-verification",
                        "pr_title": "E2E Flow PR",
                        "pr_body": "Automated verification test PR",
                        "base_branch": "main",
                        "base_commit": base_sha,
                    },
                )
                submit_payload = json.loads(submit_res.content[0].text)
                assert submit_payload["status"] == "reconciled_and_submitted"
                change_id = submit_payload["change_id"]
                pr_id = submit_payload["pull_request_id"]
                assert change_id is not None
                assert pr_id is not None

                # 7. Call sutra_get_status
                status_res = await session.call_tool("sutra_get_status", {"pull_request_id": pr_id})
                status_payload = json.loads(status_res.content[0].text)
                assert status_payload["status"] == "success"
                assert status_payload["pull_request_id"] == pr_id
                assert "governance_verdict" in status_payload

                # 8. Call sutra_request_merge -> verify strict human-in-the-loop boundary (CHECK 7)
                merge_res = await session.call_tool(
                    "sutra_request_merge",
                    {
                        "pull_request_id": pr_id,
                        "completion_summary": "All changes completed and verified via real MCP client flow",
                    },
                )
                merge_payload = json.loads(merge_res.content[0].text)
                assert merge_payload["status"] in ["blocked", "awaiting_human_approval", "ready_for_human_merge"]
                # Must NEVER directly merge; requires human review
                assert merge_payload.get("merged") is not True
                db_session.expire_all()
                pr = db_session.scalar(select(PullRequest).where(PullRequest.id == pr_id))
                assert pr.status != "merged"
                assert pr.status in ["open", "review_requested", "pending_review", "draft"]
