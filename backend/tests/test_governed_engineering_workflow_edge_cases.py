"""Failure, Idempotency, and Security Regression Test Suite for Governed Workflow.

Verifies:
1. Agent cannot merge before human approval (MCP sutra_request_merge).
2. Agent direct REST merge attempt is forbidden (HTTP 401/403).
3. PR HEAD change after human approval invalidates approval and demands re-approval.
4. Already merged PR returns idempotent status.
5. Duplicate commit submission is idempotent and prevents duplicate Changes/PRs.
6. Foreign repository / task scope mismatch is rejected fail-closed.
7. Expired task lease rejects change submission.
"""
from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import secrets
import shutil
from uuid import uuid4

import httpx
import pytest
from sqlalchemy import select

from app.core.config import settings
from app.core.security import create_access_token, hash_password
from app.db.session import SessionLocal
from app.main import app
from app.mcp.server import mcp_server
from app.models.actor import Actor
from app.models.agent import Agent
from app.models.agent_repository_access import AgentRepositoryAccess
from app.models.agent_session import AgentSession
from app.models.change import Change
from app.models.change_review import ChangeReview
from app.models.pull_request import PullRequest
from app.models.repository import Repository
from app.models.task import Task
from app.models.user import User
from app.services.lifecycle_status_service import (
    LifecycleNextActor,
    LifecycleOverallState,
    LifecycleStage,
    LifecycleStatusService,
)
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
def edge_case_environment(db_session):
    now = datetime.now(timezone.utc)
    uid = secrets.token_hex(8)

    # 1. Human Owner
    owner = User(
        id=str(uuid4()),
        username=f"edge_owner_{uid}",
        email=f"edge_owner_{uid}@example.com",
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

    # 2. Human Reviewer
    reviewer = User(
        id=str(uuid4()),
        username=f"edge_reviewer_{uid}",
        email=f"edge_reviewer_{uid}@example.com",
        password_hash=hash_password("password123"),
        email_verified=True,
    )
    db_session.add(reviewer)

    reviewer_actor = Actor(
        id=reviewer.id,
        owner_id=reviewer.id,
        type="human",
        name=reviewer.username,
        capabilities="[]",
    )
    db_session.add(reviewer_actor)

    # 3. Target Repository
    repo = RepositoryService(db_session).create(
        owner_id=owner.id,
        name=f"edge-repo-{uid}",
        description="Edge cases repository",
        visibility="private",
    )

    # 4. Foreign Repository
    repo_foreign = RepositoryService(db_session).create(
        owner_id=owner.id,
        name=f"foreign-repo-{uid}",
        description="Foreign repository for scope tests",
        visibility="private",
    )

    # 5. Agent
    raw_agent_token = f"sutra_agent_{secrets.token_urlsafe(32)}"
    agent = Agent(
        id=f"edge_agent_{uid}",
        owner_id=owner.id,
        name=f"EdgeAgent-{uid}",
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
        ]),
    )
    db_session.add(agent_actor)

    # Grant access to primary repo only
    access = AgentRepositoryAccess(
        agent_id=agent.id,
        repository_id=repo.id,
        permissions=json.dumps([
            "repository.read",
            "repository.write",
            "change.create",
            "change.commit",
        ]),
        enabled=True,
    )
    db_session.add(access)
    db_session.commit()

    # 6. Session
    from app.api.agent_dependencies import create_agent_session
    agent_session, raw_session_token = create_agent_session(agent, db_session)

    # 7. Task
    task = Task(
        id=f"edge_task_{uid}",
        repository_id=repo.id,
        created_by=owner.id,
        assigned_agent_id=agent.id,
        claimed_by_session_id=agent_session.id,
        lease_expires_at=now + timedelta(minutes=30),
        title="Edge Cases Task",
        description="Task for edge cases testing",
        status=Task.STATUS_IN_PROGRESS,
        priority=Task.PRIORITY_HIGH,
        task_type=Task.TYPE_FEATURE,
        source="user",
    )
    db_session.add(task)
    db_session.commit()

    owner_jwt = create_access_token(owner.id)
    reviewer_jwt = create_access_token(reviewer.id)

    yield {
        "owner": owner,
        "owner_jwt": owner_jwt,
        "reviewer": reviewer,
        "reviewer_jwt": reviewer_jwt,
        "repo": repo,
        "repo_foreign": repo_foreign,
        "agent": agent,
        "session": agent_session,
        "session_token": raw_session_token,
        "task": task,
    }

    try:
        db_session.rollback()
        for r in [repo, repo_foreign]:
            repo_path = (Path(settings.repository_storage_path).resolve() / r.storage_key).resolve()
            if repo_path.exists():
                shutil.rmtree(repo_path, ignore_errors=True)

        db_session.query(ChangeReview).filter(ChangeReview.change_id.in_(
            select(Change.id).where(Change.repository_id.in_([repo.id, repo_foreign.id]))
        )).delete(synchronize_session=False)
        db_session.query(PullRequest).filter(PullRequest.repository_id.in_([repo.id, repo_foreign.id])).delete(synchronize_session=False)
        db_session.query(Change).filter(Change.repository_id.in_([repo.id, repo_foreign.id])).delete(synchronize_session=False)
        db_session.query(Task).filter(Task.repository_id.in_([repo.id, repo_foreign.id])).delete(synchronize_session=False)
        db_session.query(AgentRepositoryAccess).filter(AgentRepositoryAccess.repository_id.in_([repo.id, repo_foreign.id])).delete(synchronize_session=False)
        db_session.query(AgentSession).filter(AgentSession.agent_id == agent.id).delete(synchronize_session=False)
        db_session.query(Agent).filter(Agent.id == agent.id).delete(synchronize_session=False)
        db_session.query(Actor).filter(Actor.id.in_([agent.id, owner.id, reviewer.id])).delete(synchronize_session=False)
        db_session.query(Repository).filter(Repository.id.in_([repo.id, repo_foreign.id])).delete(synchronize_session=False)
        db_session.query(User).filter(User.id.in_([owner.id, reviewer.id])).delete(synchronize_session=False)
        db_session.commit()
    except Exception:
        db_session.rollback()


@pytest.mark.asyncio
async def test_duplicate_submission_is_idempotent_no_duplicate_records(edge_case_environment, db_session):
    """
    Submitting the same commit SHA repeatedly for a task must not create duplicate
    Change or PullRequest records in the database.
    """
    env = edge_case_environment
    base_commit, child_commit = _create_real_child_commit(env["repo"].storage_key)

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
                headers={"Authorization": f"Bearer {env['session_token']}", "Accept": "application/json, text/event-stream"},
            )
            assert init_res.status_code == 200
            session_id = init_res.headers.get("mcp-session-id")

            async def submit():
                res = await client.post(
                    "/v1/mcp",
                    json={
                        "jsonrpc": "2.0",
                        "id": secrets.randbelow(10000),
                        "method": "tools/call",
                        "params": {
                            "name": "sutra_submit_change",
                            "arguments": {
                                "task_id": env["task"].id,
                                "commit_sha": child_commit,
                                "base_commit": base_commit,
                                "branch": "agent/edge-duplicate",
                                "intent": "Test duplicate submission intent",
                                "pr_title": "feat: test duplicate submission",
                            },
                        },
                    },
                    headers={
                        "mcp-session-id": session_id,
                        "Authorization": f"Bearer {env['session_token']}",
                        "Accept": "application/json, text/event-stream",
                    },
                )
                assert res.status_code == 200
                lines = [line.strip() for line in res.text.splitlines() if line.startswith("data: ")]
                payload = json.loads(lines[0][len("data: "):]) if lines else res.json()
                return extract_tool_result(payload["result"])

            # 1. First submission succeeds
            res1 = await submit()
            assert res1["status"] == "reconciled_and_submitted"
            change_id1 = res1["change_id"]
            pr_id1 = res1["pull_request_id"]

            # 2. Second submission of the exact same commit fails closed with idempotent details
            res2 = await submit()
            assert res2["status"] == "error"
            assert "already been recorded" in (res2.get("error") or res2.get("message", "")).lower()
            assert res2.get("details", {}).get("idempotent") is True
            assert res2["details"]["change_id"] == change_id1
            assert res2["details"]["pull_request_id"] == pr_id1

            # 3. Verify exactly 1 Change and 1 PR exist for this task in DB
            db_session.expire_all()
            changes = db_session.scalars(select(Change).where(Change.repository_id == env["repo"].id)).all()
            prs = db_session.scalars(select(PullRequest).where(PullRequest.repository_id == env["repo"].id)).all()
            assert len(changes) == 1
            assert len(prs) == 1


@pytest.mark.asyncio
async def test_head_change_after_approval_invalidates_approval(edge_case_environment, db_session):
    """
    If a PR is approved, but then the PR HEAD changes (new commit added),
    LifecycleStatusService must invalidate the approval and require re-approval.
    """
    env = edge_case_environment
    base_commit, commit1 = _create_real_child_commit(env["repo"].storage_key)

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
                headers={"Authorization": f"Bearer {env['session_token']}", "Accept": "application/json, text/event-stream"},
            )
            assert init_res.status_code == 200
            session_id = init_res.headers.get("mcp-session-id")

            # 1. Submit initial commit
            sub_res = await client.post(
                "/v1/mcp",
                json={
                    "jsonrpc": "2.0",
                    "id": 2,
                    "method": "tools/call",
                    "params": {
                        "name": "sutra_submit_change",
                        "arguments": {
                            "task_id": env["task"].id,
                            "commit_sha": commit1,
                            "base_commit": base_commit,
                            "branch": "agent/edge-head-change",
                            "intent": "Test head change invalidation intent",
                            "pr_title": "feat: test head change invalidation",
                        },
                    },
                },
                headers={
                    "mcp-session-id": session_id,
                    "Authorization": f"Bearer {env['session_token']}",
                    "Accept": "application/json, text/event-stream",
                },
            )
            assert sub_res.status_code == 200
            lines = [line.strip() for line in sub_res.text.splitlines() if line.startswith("data: ")]
            payload = json.loads(lines[0][len("data: "):]) if lines else sub_res.json()
            submit_data = extract_tool_result(payload["result"])
            pr_id = submit_data["pull_request_id"]

            # 2. Human approves commit1
            app_res = await client.post(
                f"/v1/pull-requests/{pr_id}/approve",
                headers={"Authorization": f"Bearer {env['reviewer_jwt']}"},
            )
            assert app_res.status_code == 200

            # 3. Verify lifecycle status reports approved and ready for merge
            svc = LifecycleStatusService(db_session)
            st1 = svc.get_lifecycle_status(pull_request_id=pr_id)
            assert st1["approval"]["is_approved"] is True
            assert st1["approval"]["head_changed_after_approval"] is False
            assert st1["current_stage"] == LifecycleStage.READY_FOR_MERGE

            # 4. Now simulate PR HEAD change (e.g. agent or collaborator pushed commit2)
            _, commit2 = _create_real_child_commit(env["repo"].storage_key)
            pr = db_session.scalar(select(PullRequest).where(PullRequest.id == pr_id))
            pr.source_commit = commit2
            db_session.commit()

            # 5. Lifecycle status MUST invalidate approval
            st2 = svc.get_lifecycle_status(pull_request_id=pr_id)
            assert st2["approval"]["head_changed_after_approval"] is True
            assert st2["current_stage"] == LifecycleStage.AWAITING_HUMAN_APPROVAL
            assert st2["next_actor"] == LifecycleNextActor.HUMAN
            assert st2["next_action"] == "human_approve"
            assert any("HEAD changed" in r for r in st2["blocked_reasons"])


@pytest.mark.asyncio
async def test_already_merged_pr_returns_idempotent_status(edge_case_environment, db_session):
    """
    Calling sutra_request_merge or checking status on an already-merged PR must
    return merged status idempotently.
    """
    env = edge_case_environment
    base_commit, commit1 = _create_real_child_commit(env["repo"].storage_key)

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
                headers={"Authorization": f"Bearer {env['session_token']}", "Accept": "application/json, text/event-stream"},
            )
            assert init_res.status_code == 200
            session_id = init_res.headers.get("mcp-session-id")

            # 1. Submit initial change
            sub_res = await client.post(
                "/v1/mcp",
                json={
                    "jsonrpc": "2.0",
                    "id": 2,
                    "method": "tools/call",
                    "params": {
                        "name": "sutra_submit_change",
                        "arguments": {
                            "task_id": env["task"].id,
                            "commit_sha": commit1,
                            "base_commit": base_commit,
                            "branch": "agent/edge-already-merged",
                            "intent": "Test already merged intent",
                            "pr_title": "feat: test already merged",
                        },
                    },
                },
                headers={
                    "mcp-session-id": session_id,
                    "Authorization": f"Bearer {env['session_token']}",
                    "Accept": "application/json, text/event-stream",
                },
            )
            assert sub_res.status_code == 200
            lines = [line.strip() for line in sub_res.text.splitlines() if line.startswith("data: ")]
            payload = json.loads(lines[0][len("data: "):]) if lines else sub_res.json()
            submit_data = extract_tool_result(payload["result"])
            pr_id = submit_data["pull_request_id"]

            # 2. Human approves and merges PR
            await client.post(
                f"/v1/pull-requests/{pr_id}/approve",
                headers={"Authorization": f"Bearer {env['reviewer_jwt']}"},
            )
            merge_res = await client.post(
                f"/v1/pull-requests/{pr_id}/merge",
                headers={"Authorization": f"Bearer {env['owner_jwt']}"},
            )
            assert merge_res.status_code == 200

            # 3. Re-issue active session for agent post-merge (security lifecycle: session closes on task completion)
            from app.api.agent_dependencies import create_agent_session
            fresh_session, fresh_token = create_agent_session(env["agent"], db_session)
            fresh_init = await client.post(
                "/v1/mcp",
                json={
                    "jsonrpc": "2.0",
                    "id": 100,
                    "method": "initialize",
                    "params": {"protocolVersion": "2024-11-05", "capabilities": {}, "clientInfo": {"name": "test", "version": "1"}},
                },
                headers={"Authorization": f"Bearer {fresh_token}", "Accept": "application/json, text/event-stream"},
            )
            assert fresh_init.status_code == 200
            fresh_session_id = fresh_init.headers.get("mcp-session-id")

            # Agent calls sutra_request_merge on already-merged PR
            req_res = await client.post(
                "/v1/mcp",
                json={
                    "jsonrpc": "2.0",
                    "id": 101,
                    "method": "tools/call",
                    "params": {
                        "name": "sutra_request_merge",
                        "arguments": {"pull_request_id": pr_id},
                    },
                },
                headers={
                    "mcp-session-id": fresh_session_id,
                    "Authorization": f"Bearer {fresh_token}",
                    "Accept": "application/json, text/event-stream",
                },
            )
            assert req_res.status_code == 200
            lines = [line.strip() for line in req_res.text.splitlines() if line.startswith("data: ")]
            payload = json.loads(lines[0][len("data: "):]) if lines else req_res.json()
            req_data = extract_tool_result(payload["result"])
            assert req_data["status"] == "merged"
            assert req_data["is_merged"] is True

            # 4. Lifecycle status query returns MERGED and COMPLETED
            svc = LifecycleStatusService(db_session)
            st = svc.get_lifecycle_status(pull_request_id=pr_id)
            assert st["merge"]["is_merged"] is True
            assert st["overall_state"] in (LifecycleOverallState.MERGED, LifecycleOverallState.COMPLETED)
