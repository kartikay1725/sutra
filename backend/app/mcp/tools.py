"""Curated 8-Tool SUTRA MCP Interface.

Implements high-signal agent workflows and inspection primitives as an
adapter layer over existing SUTRA domain services.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
import logging
from typing import Any, Dict, List, Optional
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.agent_tasks import _get_provider_for_repository
from app.api.agents import get_agent_context
from app.db.session import SessionLocal
from app.mcp.auth import MCPAuthError, resolve_mcp_agent_session
from app.models.actor import Actor
from app.models.change import Change
from app.models.issue import Issue
from app.models.pull_request import PullRequest
from app.models.repository import Repository
from app.models.task import Task
from app.services.agent_change_service import AgentChangeService
from app.services.authorization_service import AuthorizationService
from app.services.ci_service import CIService
from app.services.code_provenance_service import CodeProvenanceService
from app.services.governance_service import GovernanceService
from app.services import knowledge_graph_service
from app.services.pull_request_service import PullRequestService
from app.services.task_service import TaskService
from mcp.server.mcpserver import Context

logger = logging.getLogger("sutra.mcp.tools")


def _format_error(message: str, details: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    return {
        "status": "error",
        "error": message,
        "details": details or {},
    }


def register_sutra_tools(server: Any) -> None:
    """Register the curated 8 tools on the MCP server instance."""

    # =========================================================================
    # TOOL 1: sutra_get_context
    # =========================================================================
    @server.tool()
    async def sutra_get_context(ctx: Context) -> Dict[str, Any]:
        """CRITICAL FIRST STEP: Returns your authoritative SUTRA engineering context.

Call this immediately when starting work to discover your identity, active task
assignment, repository permissions, blocked operations, and legal next step.
SUTRA is the engineering control plane; code cannot be merged without satisfying
SUTRA governance. Do NOT attempt to merge or self-approve.
        """
        with SessionLocal() as db:
            try:
                session, agent = resolve_mcp_agent_session(ctx, db)
                resp = get_agent_context(session, agent, db)
                return resp.model_dump(mode="json")
            except MCPAuthError as e:
                return _format_error(e.message, {"code": e.code})
            except Exception as e:
                logger.error(f"sutra_get_context failed: {e}", exc_info=True)
                return _format_error(f"Failed to retrieve agent context: {str(e)}")

    # =========================================================================
    # TOOL 2: sutra_search_knowledge
    # =========================================================================
    @server.tool()
    async def sutra_search_knowledge(
        ctx: Context,
        repository_id: str,
        query: str,
        limit: int = 10,
    ) -> Dict[str, Any]:
        """Searches the SUTRA Knowledge Graph for repository code architecture, function definitions, dependencies, and engineering decisions.

Use this before modifying code to understand existing contracts and conventions.
Read-only.
        """
        with SessionLocal() as db:
            try:
                session, agent = resolve_mcp_agent_session(ctx, db)

                repo = db.scalar(
                    select(Repository).where(
                        Repository.id == repository_id,
                        Repository.deleted_at.is_(None),
                    )
                )
                if not repo:
                    return _format_error(f"Repository '{repository_id}' not found")

                actor = db.scalar(select(Actor).where(Actor.id == agent.id))
                if not actor:
                    return _format_error("Agent actor identity not found")

                auth_decision = AuthorizationService.check(
                    actor=actor,
                    repository=repo,
                    capability=AuthorizationService.KNOWLEDGE_GRAPH_READ,
                    db=db,
                )
                if not auth_decision.allowed:
                    return _format_error(f"Forbidden: {auth_decision.reason}")

                nodes = knowledge_graph_service.search_nodes(db, repository_id, query, limit=min(limit, 25))
                return {
                    "status": "success",
                    "repository_id": repository_id,
                    "query": query,
                    "count": len(nodes),
                    "results": [
                        {
                            "id": n.id,
                            "entity_type": n.entity_type,
                            "name": n.name,
                            "summary": n.summary,
                            "content_hash": n.content_hash,
                        }
                        for n in nodes
                    ],
                }
            except MCPAuthError as e:
                return _format_error(e.message, {"code": e.code})
            except Exception as e:
                logger.error(f"sutra_search_knowledge failed: {e}", exc_info=True)
                return _format_error(f"Knowledge search failed: {str(e)}")

    # =========================================================================
    # TOOL 3: sutra_start_task
    # =========================================================================
    @server.tool()
    async def sutra_start_task(
        ctx: Context,
        task_id: str,
    ) -> Dict[str, Any]:
        """Claims an assigned or open engineering task and locks an exclusive execution lease for your session.

You must call this before writing code or pushing branches. Once claimed, you own
this task until completion or release. Returns task requirements, target branch name,
and repository details.
        """
        with SessionLocal() as db:
            try:
                session, agent = resolve_mcp_agent_session(ctx, db)
                task_svc = TaskService(db)
                task = task_svc.claim_agent_task(task_id, session)
                db.commit()
                db.refresh(task)

                repo = db.scalar(select(Repository).where(Repository.id == task.repository_id))
                repo_slug = repo.slug if repo else "unknown"

                recommended_branch = f"agent/task-{task.id[:8]}"
                return {
                    "status": "claimed",
                    "task_id": task.id,
                    "title": task.title,
                    "description": task.description,
                    "priority": task.priority,
                    "task_type": task.task_type,
                    "repository_id": task.repository_id,
                    "repository_slug": repo_slug,
                    "lease_expires_at": task.lease_expires_at.isoformat() if task.lease_expires_at else None,
                    "recommended_branch": recommended_branch,
                    "instructions": (
                        f"Task '{task.title}' claimed. Check out feature branch '{recommended_branch}', "
                        "make code changes, commit and push using your terminal git, then call "
                        "sutra_submit_change with your commit SHA."
                    ),
                }
            except MCPAuthError as e:
                return _format_error(e.message, {"code": e.code})
            except PermissionError as e:
                db.rollback()
                return _format_error(f"Permission denied: {str(e)}")
            except ValueError as e:
                db.rollback()
                return _format_error(f"Task claim rejected: {str(e)}")
            except Exception as e:
                db.rollback()
                logger.error(f"sutra_start_task failed: {e}", exc_info=True)
                return _format_error(f"Failed to claim task: {str(e)}")

    # =========================================================================
    # TOOL 4: sutra_submit_change
    # =========================================================================
    @server.tool()
    async def sutra_submit_change(
        ctx: Context,
        task_id: str,
        commit_sha: str,
        intent: str,
        branch: str,
        pr_title: str,
        pr_description: Optional[str] = None,
        base_branch: str = "main",
        base_commit: Optional[str] = None,
    ) -> Dict[str, Any]:
        """PRIMARY SUBMISSION WORKFLOW: Call this after pushing your code commits to the remote feature branch.

Atomically records your engineering intent, reconciles and registers your terminal-pushed
commit SHA into SUTRA's change ledger, records cryptographic provenance under your active
session, and opens/updates the linked Pull Request on the substrate (GitHub).

IMPORTANT: This registers your already-pushed commit; SUTRA does not run git commit for you.
This does NOT merge the code. All changes require CI verification and human approval.
        """
        with SessionLocal() as db:
            try:
                session, agent = resolve_mcp_agent_session(ctx, db)

                task = db.scalar(select(Task).where(Task.id == task_id))
                if not task:
                    return _format_error(f"Task '{task_id}' not found")

                if task.assigned_agent_id != session.agent_id:
                    return _format_error("Agent is not assigned to this task")

                if task.claimed_by_session_id != session.id:
                    return _format_error("Agent session does not hold the active task lease")

                repo = db.scalar(select(Repository).where(Repository.id == task.repository_id))
                if not repo:
                    return _format_error(f"Repository '{task.repository_id}' not found")

                provider = _get_provider_for_repository(repo)
                agent_svc = AgentChangeService(db=db, provider=provider)

                # 1. Create or load existing Change for this task
                change = None
                if task.resulting_change_id:
                    change = db.scalar(select(Change).where(Change.id == task.resulting_change_id))

                if change:
                    # Enforce branch consistency: cannot switch branch on an existing change
                    change_meta = {}
                    try:
                        change_meta = json.loads(change.metadata_json or "{}")
                    except Exception:
                        pass
                    declared_branch = change_meta.get("branch")
                    if branch and declared_branch and branch.strip() != declared_branch.strip():
                        return _format_error(
                            f"Branch mismatch: Change was declared on branch '{declared_branch}', but submit received '{branch}'"
                        )
                    # Enforce duplicate submission prevention
                    if change.status == "recorded" and change.resulting_commit == commit_sha.strip():
                        return _format_error(
                            f"Commit '{commit_sha[:8]}' has already been recorded for this task/change"
                        )
                else:
                    change = agent_svc.create_change(
                        session=session,
                        task=task,
                        intent=intent,
                        branch=branch,
                        base_branch=base_branch,
                        base_commit=base_commit,
                    )

                # Enforce commit not already bound to another change/session
                bound_change = db.scalar(
                    select(Change).where(
                        Change.resulting_commit == commit_sha.strip(),
                        Change.id != change.id,
                    )
                )
                if bound_change:
                    return _format_error(
                        f"Commit '{commit_sha[:8]}' is already bound to another change ({bound_change.id[:8]})"
                    )

                change.intent = intent
                try:
                    c_meta = json.loads(change.metadata_json or "{}")
                except Exception:
                    c_meta = {}
                if branch:
                    c_meta["branch"] = branch
                change.metadata_json = json.dumps(c_meta, sort_keys=True)
                if base_commit and not change.base_commit:
                    change.base_commit = base_commit

                # 2. Reconcile and record terminal commit SHA
                change = agent_svc.record_commit(
                    session=session,
                    task=task,
                    resulting_commit=commit_sha.strip(),
                )

                # 3. Create or update Pull Request
                pr = None
                if task.resulting_pull_request_id:
                    pr = db.scalar(select(PullRequest).where(PullRequest.id == task.resulting_pull_request_id))

                if not pr:
                    pr = agent_svc.create_pull_request(
                        session=session,
                        task=task,
                        title=pr_title,
                        target_branch=base_branch,
                        description=pr_description or intent,
                    )

                db.commit()
                db.refresh(change)
                db.refresh(pr)

                return {
                    "status": "reconciled_and_submitted",
                    "task_id": task.id,
                    "change_id": change.id,
                    "pull_request_id": pr.id,
                    "commit_sha": commit_sha.strip(),
                    "branch": branch,
                    "base_branch": base_branch,
                    "pr_status": pr.status,
                    "message": (
                        f"Commit {commit_sha[:8]} registered and reconciled into SUTRA Change {change.id[:8]}. "
                        f"Pull Request {pr.id[:8]} opened. Next step: Call sutra_get_status to monitor "
                        "CI checks and governance verdict."
                    ),
                }
            except MCPAuthError as e:
                return _format_error(e.message, {"code": e.code})
            except PermissionError as e:
                db.rollback()
                return _format_error(f"Permission denied: {str(e)}")
            except ValueError as e:
                db.rollback()
                return _format_error(f"Validation rejected: {str(e)}")
            except Exception as e:
                db.rollback()
                logger.error(f"sutra_submit_change failed: {e}", exc_info=True)
                return _format_error(f"Failed to submit change: {str(e)}")

    # =========================================================================
    # TOOL 5: sutra_get_status
    # =========================================================================
    @server.tool()
    async def sutra_get_status(
        ctx: Context,
        pull_request_id: str,
    ) -> Dict[str, Any]:
        """Returns consolidated engineering status for your Pull Request or Change.

Includes current PR state (open/approved/merged), all automated CI check results with
failure logs, and the authoritative 4-pillar SUTRA governance verdict. If status is
BLOCKED or CI_FAILED, inspect the returned 'blocking_reasons' to plan fixes.
        """
        with SessionLocal() as db:
            try:
                session, agent = resolve_mcp_agent_session(ctx, db)

                pr = db.scalar(select(PullRequest).where(PullRequest.id == pull_request_id))
                if not pr:
                    return _format_error(f"Pull Request '{pull_request_id}' not found")

                # 1. CI Checks
                ci_svc = CIService(db)
                ci_data = ci_svc.get_pr_checks(pr.id, agent.id)

                # 2. Governance Verdict
                gov_svc = GovernanceService(db)
                gov_eval = gov_svc.evaluate_pull_request(pr.id, actor_id=agent.id, record_audit=False)

                return {
                    "status": "success",
                    "pull_request_id": pr.id,
                    "pr_status": pr.status,
                    "target_branch": pr.target_branch,
                    "head_commit": pr.source_commit,
                    "governance_verdict": gov_eval.get("verdict"),
                    "ready_for_approval": gov_eval.get("ready_for_approval", False),
                    "ready_for_merge": gov_eval.get("ready_for_merge", False),
                    "passed_gates": gov_eval.get("passed", []),
                    "blocking_reasons": gov_eval.get("failed", []),
                    "warnings": gov_eval.get("warnings", []),
                    "ci_summary": ci_data.get("summary", {}),
                    "checks": [
                        {
                            "name": c.get("name"),
                            "status": c.get("status"),
                            "conclusion": c.get("conclusion"),
                            "sutra_state": c.get("sutra_state"),
                            "details_url": c.get("details_url") or c.get("html_url"),
                        }
                        for c in ci_data.get("checks", [])
                    ],
                }
            except MCPAuthError as e:
                return _format_error(e.message, {"code": e.code})
            except Exception as e:
                logger.error(f"sutra_get_status failed: {e}", exc_info=True)
                return _format_error(f"Failed to get PR status: {str(e)}")

    # =========================================================================
    # TOOL 6: sutra_request_merge
    # =========================================================================
    @server.tool()
    async def sutra_request_merge(
        ctx: Context,
        pull_request_id: str,
        completion_summary: str,
    ) -> Dict[str, Any]:
        """Final handover step: Verifies that CI passed and SUTRA governance is satisfied, then dispatches a formal merge request to the human repository owner.

STRICT BOUNDARY: Agents CANNOT merge branches directly. Merging is an exclusive human
authority. This tool verifies eligibility and alerts human reviewers to execute the
governed merge.
        """
        with SessionLocal() as db:
            try:
                session, agent = resolve_mcp_agent_session(ctx, db)

                pr = db.scalar(select(PullRequest).where(PullRequest.id == pull_request_id))
                if not pr:
                    return _format_error(f"Pull Request '{pull_request_id}' not found")

                gov_svc = GovernanceService(db)
                gov_eval = gov_svc.evaluate_pull_request(pr.id, actor_id=agent.id, record_audit=True)
                verdict = gov_eval.get("verdict")
                ready_for_merge = gov_eval.get("ready_for_merge", False)

                if verdict == "BLOCKED" or verdict == "CI_FAILED" or verdict == "POLICY_FAILED":
                    return {
                        "status": "blocked",
                        "verdict": verdict,
                        "ready_for_merge": False,
                        "blocking_reasons": gov_eval.get("failed", []),
                        "message": "PR cannot be handed over for merge because governance or CI checks are failing.",
                    }

                # Human review required if not already approved
                if pr.status != PullRequest.STATUS_APPROVED and not ready_for_merge:
                    return {
                        "status": "awaiting_human_approval",
                        "verdict": verdict,
                        "ready_for_merge": False,
                        "message": (
                            f"Governance verdict is {verdict}. Handover summary recorded. "
                            "A human repository owner must approve the change in SUTRA dashboard before merge."
                        ),
                        "handover_summary": completion_summary,
                    }

                # Ready for human merge
                return {
                    "status": "ready_for_human_merge",
                    "verdict": verdict,
                    "ready_for_merge": True,
                    "message": (
                        "All governance and CI gates are satisfied. Human repository owner has been alerted "
                        "to execute the governed merge."
                    ),
                    "handover_summary": completion_summary,
                }
            except MCPAuthError as e:
                return _format_error(e.message, {"code": e.code})
            except Exception as e:
                logger.error(f"sutra_request_merge failed: {e}", exc_info=True)
                return _format_error(f"Failed to request merge: {str(e)}")

    # =========================================================================
    # TOOL 7: sutra_get_provenance
    # =========================================================================
    @server.tool()
    async def sutra_get_provenance(
        ctx: Context,
        repository_id: str,
        commit_sha: str,
    ) -> Dict[str, Any]:
        """Inspects the full cryptographic provenance chain for any commit SHA in the repository.

Resolves whether the commit was authored by an agent or human, the associated SUTRA Task,
Change ID, Agent Session, and reviewer approval records.
        """
        with SessionLocal() as db:
            try:
                session, agent = resolve_mcp_agent_session(ctx, db)
                prov_svc = CodeProvenanceService(db)
                result = prov_svc.resolve_commit(repository_id, commit_sha)
                return {
                    "status": "success",
                    "repository_id": repository_id,
                    "commit_sha": commit_sha,
                    "provenance": result,
                }
            except MCPAuthError as e:
                return _format_error(e.message, {"code": e.code})
            except Exception as e:
                logger.error(f"sutra_get_provenance failed: {e}", exc_info=True)
                return _format_error(f"Failed to resolve provenance: {str(e)}")

    # =========================================================================
    # TOOL 8: sutra_create_issue
    # =========================================================================
    @server.tool()
    async def sutra_create_issue(
        ctx: Context,
        task_id: str,
        title: str,
        body: str,
    ) -> Dict[str, Any]:
        """Creates a tracked GitHub issue linked to your current SUTRA task and repository context.

Use this to report bugs, document technical debt discovered during execution, or propose
follow-up tasks.
        """
        with SessionLocal() as db:
            try:
                session, agent = resolve_mcp_agent_session(ctx, db)

                task = db.scalar(select(Task).where(Task.id == task_id))
                if not task:
                    return _format_error(f"Task '{task_id}' not found")

                now = datetime.now(timezone.utc)
                issue = Issue(
                    repository_id=task.repository_id,
                    source_type="agent",
                    agent_id=agent.id,
                    agent_session_id=session.id,
                    task_id=task.id,
                    actor_id=agent.id,
                    title=title,
                    body=body,
                    status="open",
                    created_at=now,
                    updated_at=now,
                )
                db.add(issue)
                db.commit()
                db.refresh(issue)

                return {
                    "status": "created",
                    "issue_id": issue.id,
                    "task_id": task.id,
                    "title": issue.title,
                    "created_at": issue.created_at.isoformat(),
                }
            except MCPAuthError as e:
                return _format_error(e.message, {"code": e.code})
            except Exception as e:
                db.rollback()
                logger.error(f"sutra_create_issue failed: {e}", exc_info=True)
                return _format_error(f"Failed to create issue: {str(e)}")
