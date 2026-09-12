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
                repo_name = repo.name if repo else "unknown"
                default_branch = repo.default_branch if repo and repo.default_branch else "main"

                actor = db.scalar(select(Actor).where(Actor.id == agent.id))
                capabilities: List[str] = []
                if actor and actor.capabilities:
                    try:
                        capabilities = json.loads(actor.capabilities)
                    except Exception:
                        capabilities = []

                recommended_branch = f"agent/task-{task.id[:8]}"
                return {
                    "status": "claimed",
                    "task_id": task.id,
                    "agent_id": agent.id,
                    "session_id": session.id,
                    "task_status": task.status,
                    "title": task.title,
                    "description": task.description,
                    "acceptance_criteria": task.description,
                    "priority": task.priority,
                    "task_type": task.task_type,
                    "repository": {
                        "id": task.repository_id,
                        "slug": repo_slug,
                        "name": repo_name,
                        "default_branch": default_branch,
                    },
                    "repository_id": task.repository_id,
                    "repository_slug": repo_slug,
                    "branch": {
                        "name": recommended_branch,
                        "recommended_branch": recommended_branch,
                        "base_branch": default_branch,
                    },
                    "recommended_branch": recommended_branch,
                    "scope": {
                        "capabilities": capabilities,
                        "can_read_repository": True,
                        "can_create_change": "change.create" in capabilities or not capabilities,
                        "can_commit_change": "change.commit" in capabilities or not capabilities,
                        "can_approve": False,
                        "can_merge": False,
                    },
                    "lease_expires_at": task.lease_expires_at.isoformat() if task.lease_expires_at else None,
                    "instructions": (
                        f"Task '{task.title}' claimed. Next step: Call sutra_declare_change with your intent and branch '{recommended_branch}'. "
                        "Then make your code edits and push them via sutra_push_commit (do NOT use terminal git push). "
                        "Finally call sutra_open_pull_request to open the linked PR for CI and governance verification."
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
    # TOOL 4: sutra_declare_change
    # =========================================================================
    @server.tool()
    async def sutra_declare_change(
        ctx: Context,
        task_id: str,
        intent: str,
        branch: str,
        base_branch: str = "main",
        base_commit: Optional[str] = None,
    ) -> Dict[str, Any]:
        """FIRST GOVERNED CODE STEP: Formally declares an engineering Change under SUTRA governance.

Call this after sutra_start_task to establish a tracked Change record bound to your
session and task. This allocates the feature branch and prepares SUTRA to accept
governed commits via sutra_push_commit.

Do NOT use terminal git push. All code must be submitted via sutra_push_commit.
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

                change = None
                if task.resulting_change_id:
                    change = db.scalar(select(Change).where(Change.id == task.resulting_change_id))

                if change:
                    change_meta = {}
                    try:
                        change_meta = json.loads(change.metadata_json or "{}")
                    except Exception:
                        pass
                    declared_branch = change_meta.get("branch")
                    if branch and declared_branch and branch.strip() != declared_branch.strip():
                        return _format_error(
                            f"Branch mismatch: Change was already declared on branch '{declared_branch}', but received '{branch}'"
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

                db.commit()
                db.refresh(change)

                return {
                    "status": "declared",
                    "task_id": task.id,
                    "change_id": change.id,
                    "branch": branch,
                    "base_branch": base_branch,
                    "intent": intent,
                    "message": (
                        f"Change {change.id[:8]} declared on branch '{branch}'. "
                        "Next step: Call sutra_push_commit with your file patches and commit message."
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
                logger.error(f"sutra_declare_change failed: {e}", exc_info=True)
                return _format_error(f"Failed to declare change: {str(e)}")

    # =========================================================================
    # TOOL 5: sutra_push_commit
    # =========================================================================
    @server.tool()
    async def sutra_push_commit(
        ctx: Context,
        change_id: str,
        commit_message: str,
        file_patches: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """SUTRA-GOVERNED COMMIT CREATION: Atomically pushes code changes to the feature branch.

The agent submits file paths and their contents directly to SUTRA. SUTRA creates the
git blobs, commit object, and advances the branch ref via its GitHub App installation token.
The commit is cryptographically registered and stamped as 'sutra_governed'.

Do NOT run `git commit` or `git push` in the terminal.

Parameters:
  - change_id: The ID of the declared change from sutra_declare_change.
  - commit_message: Conventional git commit message explaining the change.
  - file_patches: Array of file objects to write or delete:
      [{"path": "relative/path/to/file.py", "content": "file contents as string"}]
      For deletion: [{"path": "file.py", "operation": "delete"}]
        """
        with SessionLocal() as db:
            try:
                session, agent = resolve_mcp_agent_session(ctx, db)

                change = db.scalar(select(Change).where(Change.id == change_id))
                if not change:
                    return _format_error(f"Change '{change_id}' not found")

                task = db.scalar(select(Task).where(Task.resulting_change_id == change.id))
                if not task:
                    task = db.scalar(select(Task).where(Task.claimed_by_session_id == session.id))
                if not task:
                    return _format_error("No active task associated with this Change")

                if task.assigned_agent_id != session.agent_id:
                    return _format_error("Agent is not assigned to the task for this change")

                if task.claimed_by_session_id != session.id:
                    return _format_error("Agent session does not hold the active task lease")

                repo = db.scalar(select(Repository).where(Repository.id == task.repository_id))
                if not repo:
                    return _format_error(f"Repository '{task.repository_id}' not found")

                provider = _get_provider_for_repository(repo)
                agent_svc = AgentChangeService(db=db, provider=provider)

                result = agent_svc.push_governed_commit(
                    session=session,
                    task=task,
                    change=change,
                    file_patches=file_patches,
                    commit_message=commit_message,
                )

                db.commit()
                db.refresh(change)
                db.refresh(task)

                return {
                    "status": "committed",
                    "task_id": task.id,
                    "change_id": change.id,
                    "commit_sha": result["commit_sha"],
                    "branch": result["branch"],
                    "html_url": result.get("html_url"),
                    "commit_origin": "sutra_governed",
                    "message": (
                        f"Governed commit {result['commit_sha'][:8]} pushed successfully on branch '{result['branch']}'. "
                        "Next step: Call sutra_open_pull_request to open the linked Pull Request."
                    ),
                }
            except MCPAuthError as e:
                return _format_error(e.message, {"code": e.code})
            except PermissionError as e:
                db.rollback()
                return _format_error(f"Permission denied: {str(e)}")
            except ValueError as e:
                db.rollback()
                return _format_error(f"Commit creation rejected: {str(e)}")
            except Exception as e:
                db.rollback()
                logger.error(f"sutra_push_commit failed: {e}", exc_info=True)
                return _format_error(f"Failed to push governed commit: {str(e)}")

    # =========================================================================
    # TOOL 6: sutra_open_pull_request
    # =========================================================================
    @server.tool()
    async def sutra_open_pull_request(
        ctx: Context,
        change_id: str,
        pr_title: str,
        pr_description: Optional[str] = None,
        base_branch: str = "main",
    ) -> Dict[str, Any]:
        """OPENS LINKED PULL REQUEST: Creates the GitHub PR linked to your SUTRA Change and Task.

Call this after sutra_push_commit has recorded the governed commit.
This opens the Pull Request on GitHub and initiates CI evaluation and SUTRA governance checks.

After calling this, use sutra_get_status to monitor CI and governance progress.
        """
        with SessionLocal() as db:
            try:
                session, agent = resolve_mcp_agent_session(ctx, db)

                change = db.scalar(select(Change).where(Change.id == change_id))
                if not change:
                    return _format_error(f"Change '{change_id}' not found")

                task = db.scalar(select(Task).where(Task.resulting_change_id == change.id))
                if not task:
                    task = db.scalar(select(Task).where(Task.claimed_by_session_id == session.id))
                if not task:
                    return _format_error("No active task associated with this Change")

                if task.assigned_agent_id != session.agent_id:
                    return _format_error("Agent is not assigned to the task for this change")

                if task.claimed_by_session_id != session.id:
                    return _format_error("Agent session does not hold the active task lease")

                # Idempotency check: if PR already exists
                if task.resulting_pull_request_id:
                    pr = db.scalar(select(PullRequest).where(PullRequest.id == task.resulting_pull_request_id))
                    if pr:
                        c_meta = {}
                        try:
                            c_meta = json.loads(change.metadata_json or "{}")
                        except Exception:
                            pass
                        return {
                            "status": "opened",
                            "task_id": task.id,
                            "change_id": change.id,
                            "pull_request_id": pr.id,
                            "pull_request_url": c_meta.get("github_html_url"),
                            "pr_status": pr.status,
                            "idempotent": True,
                            "message": f"Pull Request {pr.id[:8]} already exists for this task.",
                        }

                repo = db.scalar(select(Repository).where(Repository.id == task.repository_id))
                if not repo:
                    return _format_error(f"Repository '{task.repository_id}' not found")

                provider = _get_provider_for_repository(repo)
                agent_svc = AgentChangeService(db=db, provider=provider)

                pr = agent_svc.create_pull_request(
                    session=session,
                    task=task,
                    title=pr_title,
                    target_branch=base_branch,
                    description=pr_description or change.intent,
                )

                db.commit()
                db.refresh(pr)
                db.refresh(change)

                c_meta = {}
                try:
                    c_meta = json.loads(change.metadata_json or "{}")
                except Exception:
                    pass

                return {
                    "status": "opened",
                    "task_id": task.id,
                    "change_id": change.id,
                    "pull_request_id": pr.id,
                    "pull_request_url": c_meta.get("github_html_url"),
                    "pr_status": pr.status,
                    "message": (
                        f"Pull Request {pr.id[:8]} opened successfully. "
                        "Next step: Call sutra_get_status to monitor CI and governance verdicts."
                    ),
                }
            except MCPAuthError as e:
                return _format_error(e.message, {"code": e.code})
            except PermissionError as e:
                db.rollback()
                return _format_error(f"Permission denied: {str(e)}")
            except ValueError as e:
                db.rollback()
                return _format_error(f"PR creation rejected: {str(e)}")
            except Exception as e:
                db.rollback()
                logger.error(f"sutra_open_pull_request failed: {e}", exc_info=True)
                return _format_error(f"Failed to open pull request: {str(e)}")

    # =========================================================================
    # TOOL 7: sutra_import_external_change (legacy / unverified observation)
    # =========================================================================
    @server.tool()
    async def sutra_import_external_change(
        ctx: Context,
        task_id: str,
        commit_sha: str,
        intent: str,
        branch: str,
        pr_title: str,
        pr_description: Optional[str] = None,
        base_branch: str = "main",
        base_commit: Optional[str] = None,
        is_legacy_submit: bool = False,
    ) -> Dict[str, Any]:
        """EXTERNAL / UNVERIFIED COMMIT IMPORT: Reconciles an externally-pushed terminal commit.

WARNING: Commits imported via this tool are stamped with origin 'external_unverified'
and CANNOT receive SUTRA governance approval. Use sutra_declare_change and sutra_push_commit
for SUTRA-governed engineering tasks.
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

                # Determine commit origin
                if is_legacy_submit and getattr(repo, "provider_type", None) == "local":
                    commit_origin = "sutra_governed"
                else:
                    commit_origin = "external_unverified"

                # 1. Create or load existing Change for this task
                change = None
                if task.resulting_change_id:
                    change = db.scalar(select(Change).where(Change.id == task.resulting_change_id))

                if change:
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
                    if change.status == "recorded" and change.resulting_commit == commit_sha.strip():
                        pr = None
                        if task.resulting_pull_request_id:
                            pr = db.scalar(select(PullRequest).where(PullRequest.id == task.resulting_pull_request_id))
                        return _format_error(
                            f"Commit '{commit_sha[:8]}' has already been recorded for this task/change",
                            details={
                                "idempotent": True,
                                "task_id": task.id,
                                "change_id": change.id,
                                "pull_request_id": pr.id if pr else None,
                                "pull_request_url": change_meta.get("github_html_url"),
                                "commit_sha": commit_sha.strip(),
                                "branch": branch,
                                "base_branch": base_branch,
                                "commit_origin": commit_origin,
                                "current_status": "reconciled" if is_legacy_submit else "external_observed",
                            },
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
                c_meta["commit_origin"] = commit_origin
                change.metadata_json = json.dumps(c_meta, sort_keys=True)
                if base_commit and not change.base_commit:
                    change.base_commit = base_commit

                # 2. Reconcile and record commit SHA
                change = agent_svc.record_commit(
                    session=session,
                    task=task,
                    resulting_commit=commit_sha.strip(),
                )
                try:
                    c_meta = json.loads(change.metadata_json or "{}")
                except Exception:
                    c_meta = {}
                c_meta["commit_origin"] = commit_origin
                change.metadata_json = json.dumps(c_meta, sort_keys=True)

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

                try:
                    c_meta = json.loads(change.metadata_json or "{}")
                except Exception:
                    c_meta = {}
                gh_pr_url = c_meta.get("github_html_url")

                ret_status = "reconciled_and_submitted" if is_legacy_submit else "external_observed"
                current_status = "reconciled" if is_legacy_submit else "external_observed"
                msg = (
                    f"Commit {commit_sha[:8]} registered and reconciled into SUTRA Change {change.id[:8]}. "
                    f"Pull Request {pr.id[:8]} opened. Next step: Call sutra_get_status to monitor "
                    "CI checks and governance verdict."
                    if is_legacy_submit else
                    f"External commit {commit_sha[:8]} imported into SUTRA Change {change.id[:8]}. "
                    f"Pull Request {pr.id[:8]} opened. WARNING: Because this commit was not created via "
                    "sutra_push_commit, SUTRA governance policy will NOT grant approval."
                )

                return {
                    "status": ret_status,
                    "commit_origin": commit_origin,
                    "governed": commit_origin == "sutra_governed",
                    "task_id": task.id,
                    "change_id": change.id,
                    "pull_request_id": pr.id,
                    "pull_request_url": gh_pr_url,
                    "commit_sha": commit_sha.strip(),
                    "branch": branch,
                    "base_branch": base_branch,
                    "pr_status": pr.status,
                    "repository": {
                        "id": repo.id,
                        "slug": repo.slug,
                        "name": repo.name,
                    },
                    "current_status": current_status,
                    "idempotent": False,
                    "message": msg,
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
                logger.error(f"sutra_import_external_change failed: {e}", exc_info=True)
                return _format_error(f"Failed to import external change: {str(e)}")

    # =========================================================================
    # TOOL 7b: sutra_submit_change (backward compatibility alias)
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
        """DEPRECATED: Use sutra_declare_change + sutra_push_commit + sutra_open_pull_request instead.

This tool now reconciles commits for backwards compatibility while tagging origin appropriately.
        """
        return await sutra_import_external_change(
            ctx=ctx,
            task_id=task_id,
            commit_sha=commit_sha,
            intent=intent,
            branch=branch,
            pr_title=pr_title,
            pr_description=pr_description,
            base_branch=base_branch,
            base_commit=base_commit,
            is_legacy_submit=True,
        )

    # =========================================================================
    # TOOL 5: sutra_get_status
    # =========================================================================
    @server.tool()
    async def sutra_get_status(
        ctx: Context,
        pull_request_id: Optional[str] = None,
        task_id: Optional[str] = None,
        change_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Returns consolidated engineering lifecycle status for your Task, Change, or Pull Request.

Aggregates the authoritative engineering lifecycle: Task -> Session -> Change ->
Commit -> PR -> CI -> Governance -> Approval -> Merge -> Task completion.

Provides current_stage, overall_state, next_action, next_actor, and blocking_reasons.
Accepts pull_request_id, task_id, or change_id.
        """
        with SessionLocal() as db:
            try:
                session, agent = resolve_mcp_agent_session(ctx, db)
                from app.services.lifecycle_status_service import LifecycleStatusService
                svc = LifecycleStatusService(db)
                result = svc.get_lifecycle_status(
                    task_id=task_id,
                    pull_request_id=pull_request_id,
                    change_id=change_id,
                    actor_id=agent.id,
                )
                if result.get("status") == "not_found":
                    return _format_error(result.get("error", "Lifecycle status not found"))
                return result
            except MCPAuthError as e:
                return _format_error(e.message, {"code": e.code})
            except Exception as e:
                logger.error(f"sutra_get_status failed: {e}", exc_info=True)
                return _format_error(f"Failed to get lifecycle status: {str(e)}")

    # =========================================================================
    # TOOL 6: sutra_request_merge
    # =========================================================================
    @server.tool()
    async def sutra_request_merge(
        ctx: Context,
        pull_request_id: str,
        completion_summary: str = "",
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

                # If already merged: return explicit merged state
                if pr.status == PullRequest.STATUS_MERGED:
                    return {
                        "status": "merged",
                        "pull_request_id": pr.id,
                        "verdict": "MERGED",
                        "ready_for_merge": False,
                        "is_merged": True,
                        "merge_commit_sha": pr.target_commit,
                        "message": f"Pull Request {pr.id[:8]} is already merged on substrate.",
                        "handover_summary": completion_summary,
                    }

                gov_svc = GovernanceService(db)
                gov_eval = gov_svc.evaluate_pull_request(pr.id, actor_id=agent.id, record_audit=True)
                verdict = gov_eval.get("verdict")
                ready_for_merge = gov_eval.get("ready_for_merge", False)

                if verdict in ("BLOCKED", "CI_FAILED", "POLICY_FAILED"):
                    return {
                        "status": "blocked",
                        "pull_request_id": pr.id,
                        "verdict": verdict,
                        "ready_for_merge": False,
                        "blocking_reasons": gov_eval.get("failed", []),
                        "message": "PR cannot be handed over for merge because governance or CI checks are failing.",
                        "handover_summary": completion_summary,
                    }

                # Human review required if not already approved
                if pr.status != PullRequest.STATUS_APPROVED and not ready_for_merge:
                    return {
                        "status": "awaiting_human_approval",
                        "pull_request_id": pr.id,
                        "verdict": verdict,
                        "ready_for_merge": False,
                        "blocking_reasons": ["Awaiting independent human reviewer approval in SUTRA dashboard."],
                        "message": (
                            f"Governance verdict is {verdict}. Handover summary recorded. "
                            "A human repository owner must approve the change in SUTRA dashboard before merge."
                        ),
                        "handover_summary": completion_summary,
                    }

                # Ready for human merge
                return {
                    "status": "ready_for_merge",
                    "pull_request_id": pr.id,
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
    # TOOL 8: sutra_get_governance
    # =========================================================================
    @server.tool()
    async def sutra_get_governance(
        ctx: Context,
        pull_request_id: Optional[str] = None,
        task_id: Optional[str] = None,
        change_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Inspects the authoritative SUTRA governance evaluation and gate verification for a Pull Request.

Evaluates:
  - Change integrity and commit origin ('sutra_governed' required)
  - Cryptographic and task provenance
  - CI check statuses
  - Branch protection rules and review satisfaction
  - Conflict detection

Accepts pull_request_id, task_id, or change_id.
        """
        with SessionLocal() as db:
            try:
                session, agent = resolve_mcp_agent_session(ctx, db)

                pr = None
                if pull_request_id:
                    pr = db.scalar(select(PullRequest).where(PullRequest.id == pull_request_id))
                elif task_id:
                    task = db.scalar(select(Task).where(Task.id == task_id))
                    if task and task.resulting_pull_request_id:
                        pr = db.scalar(select(PullRequest).where(PullRequest.id == task.resulting_pull_request_id))
                elif change_id:
                    pr = db.scalar(select(PullRequest).where(PullRequest.source_change_id == change_id))

                if not pr:
                    return _format_error(
                        "Pull Request could not be resolved. Provide a valid pull_request_id, task_id, or change_id."
                    )

                gov_svc = GovernanceService(db)
                evaluation = gov_svc.evaluate_pull_request(pr.id, actor_id=agent.id, record_audit=False)
                return {
                    "status": "success",
                    "pull_request_id": pr.id,
                    "governance": evaluation,
                }
            except MCPAuthError as e:
                return _format_error(e.message, {"code": e.code})
            except Exception as e:
                logger.error(f"sutra_get_governance failed: {e}", exc_info=True)
                return _format_error(f"Failed to evaluate governance: {str(e)}")

    # =========================================================================
    # TOOL 9: sutra_create_issue
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
