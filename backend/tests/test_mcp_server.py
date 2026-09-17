"""Test Suite for SUTRA MCP Server, Streamable HTTP Transport, and the Initial 8 Tools."""
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
from app.models.change_file import ChangeFile
from app.models.change_review import ChangeReview
from app.models.pull_request import PullRequest
from app.models.repository import Repository
from app.models.task import Task
from app.models.user import User
from app.services.repository_service import RepositoryService


@pytest.fixture
def db_session():
    with SessionLocal() as db:
        yield db


def _create_real_child_commit(repository_storage_key: str) -> tuple[str, str]:
    repo_dir = (Path(settings.repository_storage_path).resolve() / repository_storage_key).resolve()
    base_commit = subprocess.run(
        ["git", "rev-parse", "--verify", "refs/heads/main"],
        cwd=repo_dir, capture_output=True, text=True, check=True,
    ).stdout.strip()

    tree_sha = subprocess.run(
        ["git", "rev-parse", f"{base_commit}^{{tree}}"],
        cwd=repo_dir, capture_output=True, text=True, check=True,
    ).stdout.strip()

    env = {
        **os.environ,
        "GIT_AUTHOR_NAME": "SUTRA Test Agent",
        "GIT_AUTHOR_EMAIL": "agent@sutra.local",
        "GIT_COMMITTER_NAME": "SUTRA Test Agent",
        "GIT_COMMITTER_EMAIL": "agent@sutra.local",
    }
    resulting_commit = subprocess.run(
        ["git", "commit-tree", tree_sha, "-p", base_commit, "-m", "MCP agent feature alpha commit"],
        cwd=repo_dir, env=env, capture_output=True, text=True, check=True,
    ).stdout.strip()

    return base_commit, resulting_commit


@pytest.fixture
def setup_mcp_environment(db_session):
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

    # 2. Repository (backed by real bare git repo)
    repo = RepositoryService(db_session).create(
        owner_id=owner.id,
        name=f"test-repo-{uid}",
        description="MCP test repo",
        visibility="private",
    )

    # 3. Agent
    raw_agent_token = f"sutra_agent_{secrets.token_urlsafe(32)}"
    agent = Agent(
        id=f"agnt_{uid}",
        owner_id=owner.id,
        name=f"test-agent-{uid}",
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
    db_session.commit()

    # 4. Agent Repository Access
    access = AgentRepositoryAccess(
        agent_id=agent.id,
        repository_id=repo.id,
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

    # 5. Agent Session
    raw_session_token = f"sutra_session_{secrets.token_urlsafe(32)}"
    session = AgentSession(
        id=f"sess_{uid}",
        agent_id=agent.id,
        token_hash=hash_password(raw_session_token),
        token_prefix=raw_session_token[:32],
        status="active",
        expires_at=now + timedelta(minutes=15),
        last_seen_at=now,
    )
    db_session.add(session)

    # 6. Open Task
    task = Task(
        id=f"task_{uid}",
        repository_id=repo.id,
        created_by=owner.id,
        assigned_agent_id=agent.id,
        title="Implement feature alpha",
        description="Add alpha testing module",
        status=Task.STATUS_OPEN,
        priority=Task.PRIORITY_HIGH,
        task_type=Task.TYPE_FEATURE,
        source="user",
    )
    db_session.add(task)

    db_session.commit()

    yield {
        "owner": owner,
        "repo": repo,
        "agent": agent,
        "agent_token": raw_agent_token,
        "session": session,
        "session_token": raw_session_token,
        "task": task,
    }

    # Cleanup
    try:
        db_session.query(Task).filter(Task.id == task.id).delete()
        db_session.query(AgentSession).filter(AgentSession.id == session.id).delete()
        db_session.query(AgentRepositoryAccess).filter(AgentRepositoryAccess.id == access.id).delete()
        db_session.commit()
        db_session.query(Actor).filter(Actor.id.in_([owner.id, agent.id])).delete()
        db_session.query(Agent).filter(Agent.id == agent.id).delete()
        db_session.query(Repository).filter(Repository.id == repo.id).delete()
        db_session.query(User).filter(User.id == owner.id).delete()
        db_session.commit()
        repo_dir = (Path(settings.repository_storage_path).resolve() / repo.storage_key).resolve()
        if repo_dir.exists():
            shutil.rmtree(repo_dir, ignore_errors=True)
    except Exception:
        db_session.rollback()


@asynccontextmanager
async def run_mcp():
    mcp_server.session_manager._has_started = False
    async with mcp_server.session_manager.run():
        yield


@pytest.mark.asyncio
async def test_mcp_streamable_initialize_and_tool_discovery(setup_mcp_environment):
    """Verify Streamable HTTP initialization and exposure of the curated 8 tools."""
    env = setup_mcp_environment
    auth_header = f"Bearer {env['session_token']}"
    async with run_mcp():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://localhost") as client:
            init_res = await client.post(
                "/v1/mcp",
                json={
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "initialize",
                    "params": {
                        "protocolVersion": "2024-11-05",
                        "capabilities": {},
                        "clientInfo": {"name": "test-suite", "version": "1.0.0"},
                    },
                },
                headers={"Authorization": auth_header, "Accept": "application/json, text/event-stream"},
            )
            assert init_res.status_code == 200
            session_id = init_res.headers.get("mcp-session-id")
            assert session_id is not None

            # Initialized notification
            await client.post(
                "/v1/mcp",
                json={"jsonrpc": "2.0", "method": "notifications/initialized"},
                headers={"mcp-session-id": session_id, "Authorization": auth_header, "Accept": "application/json, text/event-stream"},
            )

            # List tools
            list_res = await client.post(
                "/v1/mcp",
                json={"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
                headers={"mcp-session-id": session_id, "Authorization": auth_header, "Accept": "application/json, text/event-stream"},
            )
            assert list_res.status_code == 200
            # Parse SSE data
            lines = [line.strip() for line in list_res.text.splitlines() if line.startswith("data: ")]
            assert len(lines) >= 1
            payload = json.loads(lines[0][len("data: "):])
            tools = payload["result"]["tools"]
            tool_names = {t["name"] for t in tools}

            expected_tools = {
                "sutra_get_context",
                "sutra_search_knowledge",
                "sutra_start_task",
                "sutra_declare_change",
                "sutra_push_commit",
                "sutra_open_pull_request",
                "sutra_import_external_change",
                "sutra_submit_change",
                "sutra_get_status",
                "sutra_request_merge",
                "sutra_get_provenance",
                "sutra_get_governance",
                "sutra_create_issue",
                "sutra_complete_task",
                "sutra_clone_repository",
                "sutra_create_discussion",
            }
            assert tool_names == expected_tools, f"Tool mismatch: expected {expected_tools}, got {tool_names}"
            assert len(tools) == 16

            # Verify every tool has a description and properties have descriptions
            for tool in tools:
                assert tool.get("description"), f"Tool {tool['name']} missing description"
                props = tool.get("inputSchema", {}).get("properties", {})
                for prop_name, prop_info in props.items():
                    assert "description" in prop_info and prop_info["description"], (
                        f"Tool {tool['name']} parameter '{prop_name}' missing description"
                    )


def extract_tool_result(result: dict) -> dict:
    if "structuredContent" in result and result["structuredContent"]:
        sc = result["structuredContent"]
        if isinstance(sc, dict) and "result" in sc:
            return sc["result"]
        return sc
    if "content" in result and result["content"]:
        return json.loads(result["content"][0]["text"])
    return result


@pytest.mark.asyncio
async def test_mcp_unauthenticated_call_fails():
    """Verify tool calls without Bearer token fail at HTTP layer with 401 and WWW-Authenticate."""
    async with run_mcp():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://localhost") as client:
            init_res = await client.post(
                "/v1/mcp",
                json={
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "initialize",
                    "params": {"protocolVersion": "2024-11-05", "capabilities": {}, "clientInfo": {"name": "test", "version": "1"}},
                },
                headers={"Accept": "application/json, text/event-stream"},
            )
            assert init_res.status_code == 401
            auth_header = init_res.headers.get("www-authenticate", "")
            assert "Bearer" in auth_header
            assert "resource_metadata=" in auth_header


@pytest.mark.asyncio
async def test_mcp_e2e_agent_workflow(setup_mcp_environment, db_session):
    """
    Test the full agent workflow through the official MCP server:
    1. sutra_get_context
    2. sutra_start_task
    3. sutra_submit_change (registering & reconciling terminal commit)
    4. sutra_get_status
    5. sutra_request_merge (verifies agent cannot self-merge)
    6. sutra_get_provenance
    """
    env = setup_mcp_environment
    auth_header = f"Bearer {env['session_token']}"

    async with run_mcp():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://localhost") as client:
            # 1. Initialize
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
            session_id = init_res.headers.get("mcp-session-id")

            # Helper to execute tool
            async def call_tool(tool_id: int, name: str, arguments: dict):
                res = await client.post(
                    "/v1/mcp",
                    json={
                        "jsonrpc": "2.0",
                        "id": tool_id,
                        "method": "tools/call",
                        "params": {"name": name, "arguments": arguments},
                    },
                    headers={
                        "mcp-session-id": session_id,
                        "Authorization": auth_header,
                        "Accept": "application/json, text/event-stream",
                    },
                )
                assert res.status_code == 200
                lines = [line.strip() for line in res.text.splitlines() if line.startswith("data: ")]
                payload = json.loads(lines[0][len("data: "):])
                result = payload["result"]
                return extract_tool_result(result)

            # 2. Call sutra_get_context
            ctx_data = await call_tool(2, "sutra_get_context", {})
            assert ctx_data["identity"]["agent_id"] == env["agent"].id
            assert len(ctx_data["repository_access"]) >= 1
            assert ctx_data["repository_access"][0]["repository_id"] == env["repo"].id

            # 3. Call sutra_start_task
            start_data = await call_tool(3, "sutra_start_task", {"task_id": env["task"].id})
            assert start_data["status"] == "claimed"
            assert start_data["task_id"] == env["task"].id

            # Verify in DB that lease is bound to AgentSession
            db_session.expire_all()
            db_task = db_session.scalar(select(Task).where(Task.id == env["task"].id))
            assert db_task.claimed_by_session_id == env["session"].id
            assert db_task.status == Task.STATUS_IN_PROGRESS

            # 4. Call sutra_submit_change (reconciling terminal commit)
            base_commit, real_commit_sha = _create_real_child_commit(env["repo"].storage_key)
            submit_data = await call_tool(
                4,
                "sutra_submit_change",
                {
                    "task_id": env["task"].id,
                    "commit_sha": real_commit_sha,
                    "base_commit": base_commit,
                    "intent": "Implemented feature alpha in terminal git",
                    "branch": "agent/task-alpha",
                    "pr_title": "feat: add feature alpha",
                    "pr_description": "Reconciled commit from terminal",
                },
            )
            assert submit_data["status"] == "reconciled_and_submitted", f"submit_data error: {submit_data}"
            pr_id = submit_data["pull_request_id"]
            change_id = submit_data["change_id"]
            assert pr_id is not None
            assert change_id is not None

            # Verify in DB that commit is bound to Change
            db_session.expire_all()
            db_change = db_session.scalar(select(Change).where(Change.id == change_id))
            assert db_change.resulting_commit == real_commit_sha
            assert db_change.status in ("proposed", "recorded")

            # 5. Call sutra_get_status
            status_data = await call_tool(5, "sutra_get_status", {"pull_request_id": pr_id})
            assert status_data["status"] == "success"
            assert status_data["pull_request_id"] == pr_id
            assert "governance_verdict" in status_data

            # 6. Call sutra_request_merge (verifies agent handover boundary)
            merge_data = await call_tool(
                6,
                "sutra_request_merge",
                {
                    "pull_request_id": pr_id,
                    "completion_summary": "Feature alpha implemented and ready for review",
                },
            )
            # PR is not yet approved by a human, so it MUST NOT execute merge
            assert merge_data["status"] in ("awaiting_human_approval", "blocked")
            assert merge_data.get("ready_for_merge") is False

            # 7. Call sutra_get_provenance
            prov_data = await call_tool(
                7,
                "sutra_get_provenance",
                {
                    "repository_id": env["repo"].id,
                    "commit_sha": real_commit_sha,
                },
            )
            assert prov_data["status"] == "success"
            prov = prov_data["provenance"]
            assert prov["tracked"] is True
            assert prov["identity_type"] == "agent"
            assert prov["agent"]["id"] == env["agent"].id
            assert prov["session"]["id"] == env["session"].id
            assert prov["task"]["id"] == env["task"].id


@pytest.mark.asyncio
async def test_mcp_permanent_token_auto_creates_session(setup_mcp_environment, db_session):
    """Verify an agent authenticating with its permanent token automatically negotiates an AgentSession."""
    env = setup_mcp_environment
    permanent_auth_header = f"Bearer {env['agent_token']}"

    async with run_mcp():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://localhost") as client:
            init_res = await client.post(
                "/v1/mcp",
                json={
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "initialize",
                    "params": {"protocolVersion": "2024-11-05", "capabilities": {}, "clientInfo": {"name": "test", "version": "1"}},
                },
                headers={"Authorization": permanent_auth_header, "Accept": "application/json, text/event-stream"},
            )
            session_id = init_res.headers.get("mcp-session-id")

            call_res = await client.post(
                "/v1/mcp",
                json={
                    "jsonrpc": "2.0",
                    "id": 2,
                    "method": "tools/call",
                    "params": {"name": "sutra_get_context", "arguments": {}},
                },
                headers={
                    "mcp-session-id": session_id,
                    "Authorization": permanent_auth_header,
                    "Accept": "application/json, text/event-stream",
                },
            )
            assert call_res.status_code == 200
            lines = [line.strip() for line in call_res.text.splitlines() if line.startswith("data: ")]
            payload = json.loads(lines[0][len("data: "):])
            result = payload["result"]
            ctx_data = extract_tool_result(result)
            assert ctx_data["identity"]["agent_id"] == env["agent"].id
            # A valid session should have been issued
            assert ctx_data["session"]["session_id"] is not None


@pytest.mark.asyncio
async def test_mcp_governed_commit_flow(setup_mcp_environment, db_session, monkeypatch):
    """Verify the new SUTRA-governed commit tools: declare_change, push_commit, open_pull_request."""
    env = setup_mcp_environment
    auth_header = f"Bearer {env['session_token']}"

    # Setup repo as a GitHub-type repo so push_governed_commit accepts it
    repo = env["repo"]
    repo.provider_type = "github"
    repo.provider_owner = "test-org"
    db_session.commit()

    from app.providers.github.repository import GitHubRepositoryProvider
    fake_commit_sha = "abcde1234567890abcdef1234567890abcdef12"

    def mock_create_governed_commit(*args, **kwargs):
        return {
            "commit_sha": fake_commit_sha,
            "branch": kwargs.get("branch", "agent/governed-task"),
            "tree_sha": "tree123",
            "parent_sha": "parent123",
            "html_url": f"https://github.com/test-org/{repo.name}/commit/{fake_commit_sha}",
        }

    from app.providers.base import ProviderBranch, ProviderPullRequest
    def mock_get_branch(*args, **kwargs):
        return ProviderBranch(
            name=kwargs.get("branch", "agent/governed-task"),
            commit_sha=fake_commit_sha,
        )

    def mock_create_pull_request(*args, **kwargs):
        return ProviderPullRequest(
            number=42,
            title=kwargs.get("title", "Governed PR"),
            body=kwargs.get("description", "PR Description"),
            head_ref=kwargs.get("head_branch", "agent/governed-task"),
            head_sha=fake_commit_sha,
            base_ref=kwargs.get("base_branch", "main"),
            base_sha="parent123",
            html_url=f"https://github.com/test-org/{repo.name}/pull/42",
            is_merged=False,
            mergeable=True,
        )

    monkeypatch.setattr(GitHubRepositoryProvider, "create_governed_commit", mock_create_governed_commit)
    monkeypatch.setattr(GitHubRepositoryProvider, "get_branch", mock_get_branch)
    monkeypatch.setattr(GitHubRepositoryProvider, "create_pull_request", mock_create_pull_request)

    async with run_mcp():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://localhost") as client:
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
            session_id = init_res.headers.get("mcp-session-id")

            async def call_tool(tool_id: int, name: str, arguments: dict):
                res = await client.post(
                    "/v1/mcp",
                    json={
                        "jsonrpc": "2.0",
                        "id": tool_id,
                        "method": "tools/call",
                        "params": {"name": name, "arguments": arguments},
                    },
                    headers={
                        "mcp-session-id": session_id,
                        "Authorization": auth_header,
                        "Accept": "application/json, text/event-stream",
                    },
                )
                assert res.status_code == 200
                lines = [line.strip() for line in res.text.splitlines() if line.startswith("data: ")]
                payload = json.loads(lines[0][len("data: "):])
                result = payload["result"]
                return extract_tool_result(result)

            # 1. Start task
            start_data = await call_tool(10, "sutra_start_task", {"task_id": env["task"].id})
            assert start_data["status"] == "claimed"
            assert "sutra_declare_change" in start_data["instructions"]
            assert "sutra_push_commit" in start_data["instructions"]

            # 2. Declare change
            dec_data = await call_tool(
                11,
                "sutra_declare_change",
                {
                    "task_id": env["task"].id,
                    "intent": "Governed test change intent",
                    "branch": "agent/governed-task",
                    "base_branch": "main",
                },
            )
            assert dec_data["status"] == "declared"
            change_id = dec_data["change_id"]
            assert change_id is not None

            # 3. Push governed commit
            push_data = await call_tool(
                12,
                "sutra_push_commit",
                {
                    "change_id": change_id,
                    "commit_message": "feat: implement governed feature",
                    "file_patches": [
                        {"path": "src/governed.py", "content": "print('SUTRA governed')\n"}
                    ],
                },
            )
            assert push_data["status"] == "committed"
            assert push_data["commit_origin"] == "sutra_governed"
            assert push_data["commit_sha"] == fake_commit_sha

            # 4. Open PR
            pr_data = await call_tool(
                13,
                "sutra_open_pull_request",
                {
                    "change_id": change_id,
                    "pr_title": "feat: governed PR",
                    "pr_description": "Pull request opened via sutra_open_pull_request",
                    "base_branch": "main",
                },
            )
            assert pr_data["status"] == "opened"
            pr_id = pr_data["pull_request_id"]
            assert pr_id is not None

            # 5. Check provenance
            prov_data = await call_tool(
                14,
                "sutra_get_provenance",
                {
                    "repository_id": repo.id,
                    "commit_sha": fake_commit_sha,
                },
            )
            prov = prov_data["provenance"]
            assert prov["governed"] is True
            assert prov["commit_origin"] == "sutra_governed"

            # 6. Check governance evaluation
            gov_data = await call_tool(
                15,
                "sutra_get_governance",
                {
                    "pull_request_id": pr_id,
                },
            )
            assert gov_data["status"] == "success"
            assert "governance" in gov_data
            gov_eval = gov_data["governance"]
            assert "verdict" in gov_eval
            assert "passed" in gov_eval
            assert any("Commit origin verified as SUTRA-governed." in p for p in gov_eval.get("passed", []))

            # 7. Attempt to complete task while PR is unmerged/unapproved -> should block
            complete_res = await call_tool(
                16,
                "sutra_complete_task",
                {
                    "task_id": env["task"].id,
                    "execution_summary": "Pushed commit and opened PR.",
                    "validation_summary": "All tests passed.",
                },
            )
            assert complete_res.get("error") or "human" in str(complete_res).lower()

            # 8. Start task Mode B (auto-create from prompt without task_id)
            mode_b_data = await call_tool(
                17,
                "sutra_start_task",
                {
                    "title": "Autonomous Feature Request",
                    "description": "Please implement feature X and add tests.",
                    "repository": repo.name,
                },
            )
            assert mode_b_data["status"] == "claimed"
            new_task_id = mode_b_data["task_id"]
            assert new_task_id is not None
            assert mode_b_data["title"] == "Autonomous Feature Request"
            assert mode_b_data["source"] == "agent"

            # 9. Complete autonomous task without linked PR -> succeeds
            complete_mode_b = await call_tool(
                18,
                "sutra_complete_task",
                {
                    "task_id": new_task_id,
                    "execution_summary": "Implemented feature X successfully.",
                    "validation_summary": "12 tests passed.",
                },
            )
            assert complete_mode_b["status"] == "success"
            assert complete_mode_b["task_status"] == "completed"
            assert complete_mode_b["execution_summary"] == "Implemented feature X successfully."
            assert complete_mode_b["validation_summary"] == "12 tests passed."


@pytest.mark.asyncio
async def test_mcp_tool_metadata_semantic_discoverability():
    """Verify semantic discoverability, intent mappings, boundary definition, and parameter schemas for all 14 tools."""
    # 1. Verify server instructions
    instructions = mcp_server.instructions
    assert instructions is not None
    # Boundary definitions
    assert "Terminal/local tools are appropriate for" in instructions
    assert "reading files" in instructions
    assert "editing files" in instructions
    assert "running tests" in instructions
    assert "git inspection" in instructions
    assert "SUTRA MCP tools MUST be used for governed" in instructions
    assert "SUTRA does not replace GitHub" in instructions

    # Intent mappings
    assert "sutra_start_task" in instructions
    assert "sutra_declare_change" in instructions
    assert "sutra_push_commit" in instructions
    assert "sutra_open_pull_request" in instructions
    assert "sutra_get_status" in instructions
    assert "sutra_get_governance" in instructions
    assert "sutra_request_merge" in instructions
    assert "sutra_complete_task" in instructions

    # Natural language phrases mapped
    assert "fix this bug" in instructions
    assert "commit this" in instructions
    assert "push this change" in instructions
    assert "open a PR" in instructions
    assert "can this merge?" in instructions
    assert "what's the status?" in instructions
    assert "finish the task" in instructions

    # 2. Inspect tools from mcp_server
    tools = await mcp_server.list_tools()
    tool_map = {t.name: t for t in tools}
    assert len(tool_map) == 16

    # 3. Verify canonical vs legacy descriptions
    # sutra_push_commit
    push_desc = tool_map["sutra_push_commit"].description
    assert "Git commit" in push_desc
    assert "push" in push_desc.lower()
    assert "governed" in push_desc.lower()
    assert "terminal" in push_desc.lower()
    assert "sutra_governed" in push_desc

    # sutra_open_pull_request
    pr_desc = tool_map["sutra_open_pull_request"].description
    assert "Pull Request" in pr_desc
    assert "gh pr create" in pr_desc
    assert "CI" in pr_desc

    # sutra_declare_change
    declare_desc = tool_map["sutra_declare_change"].description
    assert "code change" in declare_desc.lower()
    assert "feature" in declare_desc.lower()
    assert "bug fix" in declare_desc.lower()
    assert "branch" in declare_desc.lower()

    # sutra_start_task
    start_desc = tool_map["sutra_start_task"].description
    assert "engineering task" in start_desc.lower()
    assert "coding request" in start_desc.lower()
    assert "bug fix" in start_desc.lower()
    assert "do NOT ask the user for a Task ID" in start_desc

    # sutra_get_governance
    gov_desc = tool_map["sutra_get_governance"].description
    assert "governance" in gov_desc.lower()
    assert "merge" in gov_desc.lower()
    assert "CI" in gov_desc

    # sutra_get_status
    status_desc = tool_map["sutra_get_status"].description
    assert "lifecycle" in status_desc.lower()
    assert "status" in status_desc.lower()
    assert "pipeline" in status_desc.lower()

    # sutra_complete_task
    complete_desc = tool_map["sutra_complete_task"].description
    assert "outcome" in complete_desc.lower()
    assert "validation" in complete_desc.lower()

    # Legacy tools
    submit_desc = tool_map["sutra_submit_change"].description
    assert "DEPRECATED" in submit_desc
    assert "LEGACY" in submit_desc

    import_desc = tool_map["sutra_import_external_change"].description
    assert "EXTERNAL" in import_desc
    assert "external_unverified" in import_desc

    # 4. Verify all parameter descriptions across all 14 tools
    for name, tool in tool_map.items():
        props = tool.input_schema.get("properties", {})
        for prop_name, prop_info in props.items():
            assert "description" in prop_info, f"Tool '{name}' property '{prop_name}' missing description"
            assert len(prop_info["description"]) > 5, f"Tool '{name}' property '{prop_name}' description too short"



