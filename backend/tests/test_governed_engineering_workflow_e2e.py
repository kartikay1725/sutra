"""Comprehensive Deterministic End-to-End Governed Engineering Workflow Integration Test.

Tests the full canonical lifecycle of an AI coding agent operating under SUTRA governance:
Task -> AgentSession -> Context -> Start Task -> Work (Terminal Git Commit) ->
Submit Change -> PR -> CI & Governance -> Human Approval -> Governed Merge ->
Task Completion -> Audit & Provenance Verification.

Strictly verifies:
1. SUTRA remains the authoritative governance control plane.
2. Agents cannot approve or merge (fails closed with 403 Forbidden).
3. The canonical LifecycleStatusService accurately reflects each stage progression.
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
import subprocess
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
def workflow_environment(db_session):
    now = datetime.now(timezone.utc)
    uid = secrets.token_hex(8)

    # 1. Human Owner
    owner = User(
        id=str(uuid4()),
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

    # 2. Independent Human Reviewer
    reviewer = User(
        id=str(uuid4()),
        username=f"reviewer_{uid}",
        email=f"reviewer_{uid}@example.com",
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
        name=f"governed-repo-{uid}",
        description="Repository for E2E governed workflow test",
        visibility="private",
    )

    # 4. Agent
    raw_agent_token = f"sutra_agent_{secrets.token_urlsafe(32)}"
    agent = Agent(
        id=f"agent_{uid}",
        owner_id=owner.id,
        name=f"WorkflowAgent-{uid}",
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

    # Grant Agent Repository Access
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
    db_session.commit()

    # 5. Agent Session
    from app.api.agent_dependencies import create_agent_session
    agent_session, raw_session_token = create_agent_session(agent, db_session)

    # 6. Task Assigned to Agent
    task = Task(
        id=f"task_{uid}",
        repository_id=repo.id,
        created_by=owner.id,
        assigned_agent_id=agent.id,
        title="Implement Governed Authentication Module",
        description="End-to-end governed engineering task for auth module",
        status=Task.STATUS_ASSIGNED,
        priority=Task.PRIORITY_HIGH,
        task_type=Task.TYPE_FEATURE,
        source="user",
    )
    db_session.add(task)
    db_session.commit()

    # Create JWT access tokens for owner and reviewer
    owner_jwt = create_access_token(owner.id)
    reviewer_jwt = create_access_token(reviewer.id)

    yield {
        "owner": owner,
        "owner_jwt": owner_jwt,
        "reviewer": reviewer,
        "reviewer_jwt": reviewer_jwt,
        "repo": repo,
        "agent": agent,
        "session": agent_session,
        "session_token": raw_session_token,
        "task": task,
    }

    # Teardown
    try:
        db_session.rollback()
        repo_path = (Path(settings.repository_storage_path).resolve() / repo.storage_key).resolve()
        if repo_path.exists():
            shutil.rmtree(repo_path, ignore_errors=True)

        db_session.query(ChangeReview).filter(ChangeReview.change_id.in_(
            select(Change.id).where(Change.repository_id == repo.id)
        )).delete(synchronize_session=False)
        db_session.query(PullRequest).filter(PullRequest.repository_id == repo.id).delete(synchronize_session=False)
        db_session.query(Change).filter(Change.repository_id == repo.id).delete(synchronize_session=False)
        db_session.query(Task).filter(Task.repository_id == repo.id).delete(synchronize_session=False)
        db_session.query(AgentRepositoryAccess).filter(AgentRepositoryAccess.repository_id == repo.id).delete(synchronize_session=False)
        db_session.query(AgentSession).filter(AgentSession.agent_id == agent.id).delete(synchronize_session=False)
        db_session.query(Agent).filter(Agent.id == agent.id).delete(synchronize_session=False)
        db_session.query(Actor).filter(Actor.id.in_([agent.id, owner.id, reviewer.id])).delete(synchronize_session=False)
        db_session.query(Repository).filter(Repository.id == repo.id).delete(synchronize_session=False)
        db_session.query(User).filter(User.id.in_([owner.id, reviewer.id])).delete(synchronize_session=False)
        db_session.commit()
    except Exception:
        db_session.rollback()


@pytest.mark.asyncio
async def test_canonical_end_to_end_governed_engineering_workflow(workflow_environment, db_session):
    """
    Executes the full 12-step canonical engineering lifecycle:
    1. Agent Context Discovery (sutra_get_context)
    2. Task Claim & Lease Binding (sutra_start_task)
    3. Lifecycle Status Check (Pre-work verification)
    4. Terminal Git Commit & Change Reconciliation (sutra_submit_change)
    5. Lifecycle Status Check (PR opened, awaiting human review)
    6. Agent Self-Merge Prevention (sutra_request_merge fails closed)
    7. Direct Agent API Merge Prevention (POST /v1/pull-requests/{id}/merge -> 401/403)
    8. Independent Human Review & Approval (POST /v1/pull-requests/{id}/approve)
    9. Lifecycle Status Check (Ready for Merge)
    10. Governed Substrate Merge (POST /v1/pull-requests/{id}/merge by Human Owner)
    11. Task Completion & Final Timeline Verification
    12. Code Provenance Verification (sutra_get_provenance)
    """
    env = workflow_environment
    agent_headers = {
        "Authorization": f"Bearer {env['session_token']}",
        "Accept": "application/json, text/event-stream",
        "MCP-Protocol-Version": "2026-07-28",
    }
    owner_headers = {
        "Authorization": f"Bearer {env['owner_jwt']}",
        "Content-Type": "application/json",
    }
    reviewer_headers = {
        "Authorization": f"Bearer {env['reviewer_jwt']}",
        "Content-Type": "application/json",
    }

    async with run_mcp():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://localhost") as client:
            # Initialize MCP Streamable HTTP session
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
            assert init_res.status_code == 200, f"MCP initialize failed: {init_res.text}"
            mcp_session_id = init_res.headers.get("mcp-session-id")

            # Initialized notification
            await client.post(
                "/v1/mcp",
                json={"jsonrpc": "2.0", "method": "notifications/initialized"},
                headers={"mcp-session-id": mcp_session_id, "Authorization": f"Bearer {env['session_token']}", "Accept": "application/json, text/event-stream"},
            )

            async def call_mcp_tool(name: str, arguments: dict):
                res = await client.post(
                    "/v1/mcp",
                    json={
                        "jsonrpc": "2.0",
                        "id": secrets.randbelow(10000),
                        "method": "tools/call",
                        "params": {"name": name, "arguments": arguments},
                    },
                    headers={
                        "mcp-session-id": mcp_session_id,
                        "Authorization": f"Bearer {env['session_token']}",
                        "Accept": "application/json, text/event-stream",
                    },
                )
                assert res.status_code == 200, f"MCP call failed ({res.status_code}): {res.text}"
                lines = [line.strip() for line in res.text.splitlines() if line.startswith("data: ")]
                payload = json.loads(lines[0][len("data: "):]) if lines else res.json()
                return extract_tool_result(payload["result"])

            # -----------------------------------------------------------------
            # STEP 1: Agent Context Discovery
            # -----------------------------------------------------------------
            ctx = await call_mcp_tool("sutra_get_context", {})
            assert ctx["identity"]["agent_id"] == env["agent"].id
            assert ctx["session"]["session_id"] == env["session"].id
            assert len(ctx["repository_access"]) >= 1
            repo_entry = next(r for r in ctx["repository_access"] if r["repository_id"] == env["repo"].id)
            assert repo_entry["repository_id"] == env["repo"].id
            assert repo_entry["slug"] == env["repo"].slug

            # -----------------------------------------------------------------
            # STEP 2: Task Claim & Lease Binding
            # -----------------------------------------------------------------
            start_data = await call_mcp_tool("sutra_start_task", {"task_id": env["task"].id})
            assert start_data["status"] == "claimed"
            assert start_data["task_id"] == env["task"].id
            assert start_data["session_id"] == env["session"].id
            assert start_data["repository"]["id"] == env["repo"].id
            assert start_data["branch"]["name"].startswith("agent/")

            db_session.expire_all()
            db_task = db_session.scalar(select(Task).where(Task.id == env["task"].id))
            assert db_task.status == Task.STATUS_IN_PROGRESS
            assert db_task.claimed_by_session_id == env["session"].id

            # -----------------------------------------------------------------
            # STEP 3: Initial Lifecycle Status Query (Pre-work verification)
            # -----------------------------------------------------------------
            status_pre = await call_mcp_tool("sutra_get_status", {"task_id": env["task"].id})
            assert status_pre["status"] == "success"
            assert status_pre["current_stage"] == LifecycleStage.TASK_CLAIMED
            assert status_pre["overall_state"] == LifecycleOverallState.IN_PROGRESS
            assert status_pre["next_action"] == "submit_change"
            assert status_pre["next_actor"] == LifecycleNextActor.AGENT

            # REST lifecycle endpoint should return identical authoritative state
            rest_pre = await client.get(
                "/v1/lifecycle/status",
                params={"task_id": env["task"].id},
                headers={"Authorization": f"Bearer {env['session_token']}"},
            )
            assert rest_pre.status_code == 200
            assert rest_pre.json()["current_stage"] == LifecycleStage.TASK_CLAIMED

            # -----------------------------------------------------------------
            # STEP 4: Terminal Git Work & Change Reconciliation
            # -----------------------------------------------------------------
            base_commit, child_commit = _create_real_child_commit(env["repo"].storage_key)
            branch_name = "agent/feature-auth"

            submit_data = await call_mcp_tool(
                "sutra_submit_change",
                {
                    "task_id": env["task"].id,
                    "commit_sha": child_commit,
                    "base_commit": base_commit,
                    "branch": branch_name,
                    "intent": "Implemented secure password authentication module",
                    "pr_title": "feat(auth): implement secure password authentication",
                    "pr_description": "Initial agent implementation verified via unit tests.",
                },
            )
            assert submit_data["status"] == "reconciled_and_submitted"
            change_id = submit_data["change_id"]
            pr_id = submit_data["pull_request_id"]
            assert change_id is not None
            assert pr_id is not None
            assert submit_data["repository"]["id"] == env["repo"].id

            db_session.expire_all()
            db_change = db_session.scalar(select(Change).where(Change.id == change_id))
            db_pr = db_session.scalar(select(PullRequest).where(PullRequest.id == pr_id))
            assert db_change.resulting_commit == child_commit
            assert db_change.status in ("proposed", "recorded")
            assert db_pr.source_commit == child_commit
            assert db_pr.status == PullRequest.STATUS_OPEN

            # -----------------------------------------------------------------
            # STEP 5: Lifecycle Status Query (PR Opened, Awaiting Review)
            # -----------------------------------------------------------------
            status_post_submit = await call_mcp_tool("sutra_get_status", {"pull_request_id": pr_id})
            assert status_post_submit["status"] == "success"
            assert status_post_submit["pull_request_id"] == pr_id
            assert status_post_submit["approval"]["is_approved"] is False
            assert status_post_submit["next_actor"] == LifecycleNextActor.HUMAN
            assert status_post_submit["next_action"] == "human_approve"
            assert len(status_post_submit["blocked_reasons"]) > 0

            # -----------------------------------------------------------------
            # STEP 6: Agent Self-Merge Prevention Boundary (Agent cannot merge)
            # -----------------------------------------------------------------
            merge_request = await call_mcp_tool(
                "sutra_request_merge",
                {
                    "pull_request_id": pr_id,
                    "completion_summary": "Auth module is ready for production merge.",
                },
            )
            assert merge_request["status"] in ("awaiting_human_approval", "blocked")
            assert merge_request["ready_for_merge"] is False

            # -----------------------------------------------------------------
            # STEP 7: Direct Agent REST API Merge Attempt (Must fail with 401/403)
            # -----------------------------------------------------------------
            direct_agent_merge = await client.post(
                f"/v1/pull-requests/{pr_id}/merge",
                headers={"Authorization": f"Bearer {env['session_token']}"},
            )
            assert direct_agent_merge.status_code in (401, 403), (
                f"Agent token was able to invoke merge endpoint! Status: {direct_agent_merge.status_code}"
            )

            # -----------------------------------------------------------------
            # STEP 8: Independent Human Review & Approval
            # -----------------------------------------------------------------
            # The independent human reviewer approves the PR
            approve_res = await client.post(
                f"/v1/pull-requests/{pr_id}/approve",
                json={"reason": "Code inspected and approved for merge."},
                headers=reviewer_headers,
            )
            assert approve_res.status_code == 200, f"Approve failed: {approve_res.text}"
            assert approve_res.json()["status"] == PullRequest.STATUS_APPROVED

            # -----------------------------------------------------------------
            # STEP 9: Lifecycle Status Query (Approved & Ready for Merge)
            # -----------------------------------------------------------------
            status_approved = await call_mcp_tool("sutra_get_status", {"pull_request_id": pr_id})
            assert status_approved["approval"]["is_approved"] is True
            assert status_approved["approval"]["head_changed_after_approval"] is False
            assert status_approved["current_stage"] == LifecycleStage.READY_FOR_MERGE
            assert status_approved["overall_state"] == LifecycleOverallState.READY_FOR_MERGE
            assert status_approved["next_actor"] == LifecycleNextActor.HUMAN
            assert status_approved["next_action"] == "human_merge"

            # -----------------------------------------------------------------
            # STEP 10: Governed Substrate Merge by Human Repository Owner
            # -----------------------------------------------------------------
            merge_res = await client.post(
                f"/v1/pull-requests/{pr_id}/merge",
                headers=owner_headers,
            )
            assert merge_res.status_code == 200, f"Merge failed: {merge_res.text}"
            merge_payload = merge_res.json()
            assert merge_payload["status"] == "merged"

            db_session.expire_all()
            db_pr_merged = db_session.scalar(select(PullRequest).where(PullRequest.id == pr_id))
            assert db_pr_merged.status == PullRequest.STATUS_MERGED

            db_change_merged = db_session.scalar(select(Change).where(Change.id == change_id))
            assert db_change_merged.status in ("recorded", "merged")

            # Task automatically completes upon governed merge
            db_task_completed = db_session.scalar(select(Task).where(Task.id == env["task"].id))
            assert db_task_completed.status == Task.STATUS_COMPLETED

            # -----------------------------------------------------------------
            # STEP 11: Final Canonical Lifecycle Status & Complete Timeline
            # -----------------------------------------------------------------
            # Query via authoritative REST lifecycle API
            rest_final = await client.get(
                "/v1/lifecycle/status",
                params={"task_id": env["task"].id},
                headers=owner_headers,
            )
            assert rest_final.status_code == 200
            status_final = rest_final.json()
            assert status_final["current_stage"] == LifecycleStage.TASK_COMPLETED
            assert status_final["overall_state"] == LifecycleOverallState.COMPLETED
            assert status_final["merge"]["is_merged"] is True
            assert status_final["next_actor"] == LifecycleNextActor.NONE
            assert status_final["next_action"] == "none"

            # Verify complete historical timeline contains all expected milestone stages
            timeline_stages = [node["stage"] for node in status_final["timeline"]]
            assert LifecycleStage.TASK_CREATED in timeline_stages
            assert LifecycleStage.TASK_CLAIMED in timeline_stages
            assert LifecycleStage.WORK_SUBMITTED in timeline_stages
            assert LifecycleStage.PULL_REQUEST_OPENED in timeline_stages
            assert LifecycleStage.AWAITING_HUMAN_APPROVAL in timeline_stages
            assert LifecycleStage.MERGED in timeline_stages
            assert LifecycleStage.TASK_COMPLETED in timeline_stages

            # Re-issue active session for agent post-task verification (security lifecycle)
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

            # -----------------------------------------------------------------
            # STEP 12: Cryptographic Code Provenance Verification
            # -----------------------------------------------------------------
            prov_call = await client.post(
                "/v1/mcp",
                json={
                    "jsonrpc": "2.0",
                    "id": 101,
                    "method": "tools/call",
                    "params": {
                        "name": "sutra_get_provenance",
                        "arguments": {
                            "repository_id": env["repo"].id,
                            "commit_sha": child_commit,
                        },
                    },
                },
                headers={
                    "mcp-session-id": fresh_session_id,
                    "Authorization": f"Bearer {fresh_token}",
                    "Accept": "application/json, text/event-stream",
                },
            )
            assert prov_call.status_code == 200
            lines = [line.strip() for line in prov_call.text.splitlines() if line.startswith("data: ")]
            prov_payload = json.loads(lines[0][len("data: "):]) if lines else prov_call.json()
            prov_res = extract_tool_result(prov_payload["result"])
            assert prov_res["status"] == "success"
            provenance = prov_res["provenance"]
            assert provenance["tracked"] is True
            assert provenance["identity_type"] == "agent"
            assert provenance["agent"]["id"] == env["agent"].id
            assert provenance["session"]["id"] == env["session"].id
            assert provenance["task"]["id"] == env["task"].id
            assert provenance["change_id"] == change_id
