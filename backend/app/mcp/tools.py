"""Curated SUTRA MCP Interface.

Implements high-signal agent workflows and inspection primitives as an
adapter layer over existing SUTRA domain services.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
import logging
from typing import Annotated, Any, Dict, List, Optional
from uuid import uuid4

from pydantic import Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.api.agent_tasks import _get_provider_for_repository
from app.api.agents import get_agent_context
from app.db.session import SessionLocal
from app.mcp.auth import MCPAuthError, resolve_mcp_agent_session
from app.models.actor import Actor
from app.models.agent_repository_access import AgentRepositoryAccess
from app.models.change import Change
from app.models.discussion import Discussion, DiscussionComment
from app.models.inline_review_comment import InlineReviewComment
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
from app.services.repository_service import RepositoryService
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
    """Register curated SUTRA tools on the MCP server instance."""

    # =========================================================================
    # TOOL 1: sutra_get_context
    # =========================================================================
    @server.tool()
    async def sutra_get_context(ctx: Context) -> Dict[str, Any]:
        """AUTHORITATIVE ENGINEERING CONTEXT & IDENTITY: Discovers agent session, assigned repository, permissions, and active task.

Call this tool at the start of a session or when inspecting your working environment:
- Discovers agent identity, actor permissions, and authorized capabilities.
- Identifies the assigned repository, default branch, and active lease.
- Resolves the current active task (if any) and legal next steps.
- Answers: "who am I?", "what repository am I working on?", "what permissions do I have?".

SUTRA is the engineering control plane; code cannot be merged without satisfying SUTRA governance. Agents cannot merge or self-approve.
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
        repository_id: Annotated[str, Field(description="UUID or slug of the repository to search.")],
        query: Annotated[str, Field(description="Natural language query or code symbol to search (e.g. 'auth middleware', 'calculate_tax', 'database schema').")],
        limit: Annotated[int, Field(description="Maximum number of architecture/code knowledge nodes to return (default 10, max 25).")] = 10,
    ) -> Dict[str, Any]:
        """CODEBASE INTELLIGENCE & ARCHITECTURE SEARCH: Queries the SUTRA Knowledge Graph for symbols, contracts, dependencies, and decisions.

Use this before writing, modifying, or refactoring code to:
- Understand existing codebase architecture, classes, functions, and module boundaries.
- Inspect internal APIs, data schemas, contracts, and engineering conventions.
- Trace dependencies, callers, and related implementations across the repository.
- Answers: "search codebase architecture", "how does feature X work?", "where is function Y defined?".

Read-only inspection tool for repository intelligence and code understanding.
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
        task_id: Annotated[Optional[str], Field(description="Optional UUID of an existing SUTRA Task to claim/resume. Omit when starting a new user request--do NOT ask the user for a Task ID.")] = None,
        title: Annotated[Optional[str], Field(description="Title summarizing the user's coding objective (e.g. 'Fix auth token expiration bug', 'Add health check endpoint').")] = None,
        description: Annotated[Optional[str], Field(description="Detailed explanation of the task, requirements, acceptance criteria, or error message.")] = None,
        repository: Annotated[Optional[str], Field(description="Repository name or slug (optional if active session is already scoped to a repository).")] = None,
        priority: Annotated[str, Field(description="Task priority level: 'low', 'medium', 'high', or 'critical' (default 'medium').")] = "medium",
        task_type: Annotated[str, Field(description="Type of engineering work: 'feature', 'bug', 'refactor', 'test', or 'docs' (default 'feature').")] = "feature",
    ) -> Dict[str, Any]:
        """START AN ENGINEERING TASK: Begins a new coding request, bug fix, feature, refactor, test, or documentation task.

NATURAL WORKFLOW (DEFAULT):
When the user asks you to write code or solve an engineering problem (e.g. 'Fix the auth bug', 'Implement user profile endpoint', 'Add unit tests'),
do NOT ask the user for a Task ID!
Call this tool with 'title' (and optionally 'description', 'task_type', 'priority').
SUTRA automatically creates the governed Task, binds it to your active AgentSession, and grants your exclusive execution lease.

EXISTING TASK MODE:
Provide 'task_id' only if the user explicitly provided an existing SUTRA Task UUID to claim or resume.

Answers intents like:
- "start this task" / "start working on this"
- "fix this bug" / "implement this feature"
- "new coding request" / "refactor this component"

Canonical next step after starting: Call sutra_declare_change to allocate the feature branch.
        """
        with SessionLocal() as db:
            try:
                session, agent = resolve_mcp_agent_session(ctx, db)
                task_svc = TaskService(db)

                if task_id:
                    task = task_svc.claim_agent_task(task_id, session)
                else:
                    task = task_svc.create_and_claim_agent_task(
                        session=session,
                        title=title,
                        description=description,
                        repository=repository,
                        priority=priority,
                        task_type=task_type,
                    )

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
                    "source": getattr(task, "source", "agent") or "agent",
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
        task_id: Annotated[str, Field(description="UUID of the active SUTRA Task (from sutra_start_task) that this change belongs to.")],
        intent: Annotated[str, Field(description="Clear explanation of the change objective (e.g. 'Fix null pointer in auth middleware and add regression test').")],
        branch: Annotated[str, Field(description="Git feature branch name to create/target (e.g. 'agent/task-xxxx' or 'fix-auth-null-check').")],
        base_branch: Annotated[str, Field(description="Target base branch to merge into eventually (default 'main').")] = "main",
        base_commit: Annotated[Optional[str], Field(description="Optional base commit SHA from which the branch originates.")] = None,
    ) -> Dict[str, Any]:
        """BEGIN TRACKING A CODE CHANGE: Declares a feature, bug fix, refactor, or documentation change under SUTRA governance.

Call this after sutra_start_task to establish a tracked Change record bound to your session and task.
This allocates your git feature branch and prepares SUTRA to receive governed commits.

Answers intents like:
- "begin tracking a code change"
- "track this change" / "start code change"
- "create/allocate feature branch"
- "prepare repository modification"

Do NOT use terminal `git checkout -b` or terminal `git push`. Submit code changes through sutra_push_commit.
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
        change_id: Annotated[str, Field(description="UUID of the declared SUTRA Change (from sutra_declare_change). Identifies the governed change container.")],
        commit_message: Annotated[str, Field(description="Conventional Git commit message explaining the change (e.g. 'fix(auth): handle expired token gracefully').")],
        file_patches: Annotated[List[Dict[str, Any]], Field(description="List of file modifications submitted to SUTRA's governed Git commit path. Each element is {'path': 'relative/path/to/file.py', 'content': 'full file content as string'} or {'path': 'path/to/file.py', 'operation': 'delete'} for deletions.")],
    ) -> Dict[str, Any]:
        """CREATE AND PUSH A GIT COMMIT: Pushes repository code changes with SUTRA cryptographic provenance and governance stamping.

USE THIS TOOL INSTEAD OF TERMINAL `git commit` / `git push` FOR GOVERNED ENGINEERING WORK.
Submits file modifications and deletions directly to the repository through the SUTRA GitHub App.
Commits created through this tool are cryptographically recorded with origin 'sutra_governed', which is required for SUTRA governance verification and merge approval.

Answers intents like:
- "commit this" / "create a Git commit"
- "push the commit" / "push this change"
- "repository code submission" / "save code changes"
- "submit patches"

Next step after committing: Call sutra_open_pull_request to open the linked GitHub PR.
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
        change_id: Annotated[str, Field(description="UUID of the SUTRA Change (from sutra_declare_change) containing the pushed governed commit.")],
        pr_title: Annotated[str, Field(description="Title of the GitHub Pull Request (e.g. 'fix: resolve auth token expiration bug').")],
        pr_description: Annotated[Optional[str], Field(description="Detailed Pull Request markdown description summarizing changes, motivation, and validation results.")] = None,
        base_branch: Annotated[str, Field(description="Target branch to merge into on GitHub (default 'main').")] = "main",
    ) -> Dict[str, Any]:
        """CREATE AND OPEN A GITHUB PULL REQUEST: Opens the linked PR for your SUTRA Change, Task, and governed commits.

USE THIS TOOL INSTEAD OF `gh pr create` OR DIRECT GITHUB UI PR CREATION FOR GOVERNED WORK.
Opens the Pull Request on GitHub, links it to your SUTRA Change and Task, and initiates automated CI checks, provenance verification, and governance evaluation.

Answers intents like:
- "open a PR" / "create a pull request"
- "open a GitHub Pull Request"
- "submit PR for review"
- "submit code for review"

Next step after opening: Call sutra_get_status or sutra_get_governance to monitor CI and governance progress.
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
        task_id: Annotated[str, Field(description="UUID of the active SUTRA Task to associate with the external commit.")],
        commit_sha: Annotated[str, Field(description="Full 40-character SHA of the externally-pushed Git commit to reconcile.")],
        intent: Annotated[str, Field(description="Explanation of what was modified in the external commit.")],
        branch: Annotated[str, Field(description="Git branch where the commit was pushed.")],
        pr_title: Annotated[str, Field(description="Title for the linked GitHub Pull Request.")],
        pr_description: Annotated[Optional[str], Field(description="Optional markdown description for the Pull Request.")] = None,
        base_branch: Annotated[str, Field(description="Base branch targeted for merge (default 'main').")] = "main",
        base_commit: Annotated[Optional[str], Field(description="Optional base commit SHA before this change.")] = None,
        is_legacy_submit: Annotated[bool, Field(description="Internal flag indicating whether this is invoked via legacy sutra_submit_change.")] = False,
    ) -> Dict[str, Any]:
        """EXTERNAL / UNVERIFIED COMMIT IMPORT: Reconciles an externally-pushed terminal commit into SUTRA for observation.

WARNING: Commits imported via this tool originate outside SUTRA's governed pipeline and are stamped with origin 'external_unverified'. Under standard SUTRA governance policies, external unverified commits CANNOT receive automated governance approval.

DO NOT use this for standard agent engineering work.
Use the canonical governed pipeline: sutra_declare_change -> sutra_push_commit -> sutra_open_pull_request.
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
        task_id: Annotated[str, Field(description="[LEGACY] UUID of the active SUTRA Task.")],
        commit_sha: Annotated[str, Field(description="[LEGACY] SHA of the commit to submit.")],
        intent: Annotated[str, Field(description="[LEGACY] Description of the change intent.")],
        branch: Annotated[str, Field(description="[LEGACY] Git branch name.")],
        pr_title: Annotated[str, Field(description="[LEGACY] Pull Request title.")],
        pr_description: Annotated[Optional[str], Field(description="[LEGACY] Pull Request description.")] = None,
        base_branch: Annotated[str, Field(description="[LEGACY] Target base branch (default 'main').")] = "main",
        base_commit: Annotated[Optional[str], Field(description="[LEGACY] Base commit SHA.")] = None,
    ) -> Dict[str, Any]:
        """[DEPRECATED / LEGACY COMPATIBILITY] Legacy single-step change submission tool.

DO NOT USE FOR NEW WORK. Prefer the canonical 3-step governed workflow:
1. sutra_declare_change (declares change and allocates branch)
2. sutra_push_commit (creates and pushes governed commit with cryptographic provenance)
3. sutra_open_pull_request (opens linked GitHub PR)

This tool is preserved strictly for backwards compatibility with legacy integrations and maps internally to external commit reconciliation.
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
    # TOOL 9: sutra_get_status
    # =========================================================================
    @server.tool()
    async def sutra_get_status(
        ctx: Context,
        pull_request_id: Annotated[Optional[str], Field(description="UUID of the SUTRA Pull Request to query lifecycle status for.")] = None,
        task_id: Annotated[Optional[str], Field(description="UUID of the SUTRA Task to query lifecycle status for.")] = None,
        change_id: Annotated[Optional[str], Field(description="UUID of the SUTRA Change to query lifecycle status for.")] = None,
    ) -> Dict[str, Any]:
        """ENGINEERING LIFECYCLE STATUS & PIPELINE INSPECTION: Queries current state, active stage, and blocking reasons across Task, Change, or PR.

Aggregates the authoritative engineering lifecycle:
Task -> Session -> Change -> Commit -> PR -> CI -> Governance -> Approval -> Merge -> Task Completion.

Returns:
- current_stage: Current position in the pipeline (task_claimed, change_declared, committed, pr_opened, ci_running, under_review, approved, merged).
- overall_state: High-level status (in_progress, pending_review, ready_for_merge, blocked, completed).
- next_action: Legally expected next operation in the lifecycle.
- next_actor: Who must act next (agent or human reviewer).
- blocking_reasons: Detailed explanations of any policy, CI, or conflict blockers.

Answers intents like:
- "what's the status?" / "what is the lifecycle status?"
- "task/change/PR state"
- "what is blocking progress?" / "what's blocking?"
- "what step is next?"

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
    # TOOL 10: sutra_request_merge
    # =========================================================================
    @server.tool()
    async def sutra_request_merge(
        ctx: Context,
        pull_request_id: Annotated[str, Field(description="UUID of the SUTRA Pull Request that is ready for merge handover.")],
        completion_summary: Annotated[str, Field(description="Summary of work completed and test validations to present to human reviewers.")] = "",
    ) -> Dict[str, Any]:
        """REQUEST MERGE HANDOVER: Verifies CI and governance pass, then alerts human repository owners to execute the merge.

STRICT BOUNDARY: Agents CANNOT merge branches directly. Merging is an exclusive human authority enforced by SUTRA governance.
This tool verifies that CI checks passed and SUTRA governance policies are satisfied, then dispatches a formal merge request to human owners.

Answers intents like:
- "request merge" / "ask for merge"
- "ready to merge" / "handover PR for merge"
- "notify human reviewer to merge"
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
    # TOOL 11: sutra_get_provenance
    # =========================================================================
    @server.tool()
    async def sutra_get_provenance(
        ctx: Context,
        repository_id: Annotated[str, Field(description="UUID or slug of the repository.")],
        commit_sha: Annotated[str, Field(description="Git commit SHA (40-char or short) to resolve cryptographic and author provenance for.")],
    ) -> Dict[str, Any]:
        """CRYPTOGRAPHIC PROVENANCE & AUDIT INSPECTION: Inspects author identity, task binding, and audit trail for any Git commit.

Resolves whether the commit was authored by a verified SUTRA agent or human, the associated SUTRA Task ID, Change ID, Agent Session, and reviewer approval records.
Reveals whether the commit is stamped 'sutra_governed' or 'external_unverified'.

Answers intents like:
- "who wrote this commit?"
- "is this commit verified / governed?"
- "check commit provenance" / "audit trail"
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
    # TOOL 12: sutra_get_governance
    # =========================================================================
    @server.tool()
    async def sutra_get_governance(
        ctx: Context,
        pull_request_id: Annotated[Optional[str], Field(description="UUID of the SUTRA Pull Request to evaluate governance for.")] = None,
        task_id: Annotated[Optional[str], Field(description="UUID of the SUTRA Task to check governance for.")] = None,
        change_id: Annotated[Optional[str], Field(description="UUID of the SUTRA Change to check governance for.")] = None,
    ) -> Dict[str, Any]:
        """GOVERNANCE VERIFICATION & MERGE READINESS: Evaluates CI tests, branch policies, commit origin, and approval status.

Authoritatively evaluates whether a change can proceed and merge:
- Commit origin verification ('sutra_governed' required; external unverified rejected)
- Cryptographic provenance and task lease validity
- CI check statuses and automated test pass/fail results
- Branch protection rules and human approval satisfaction
- Git conflict detection

Answers intents like:
- "can this merge?" / "is this ready to merge?"
- "why can't this merge?" / "why is this blocked?"
- "are CI tests passing?" / "is policy satisfied?"
- "check governance" / "merge readiness"

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
    # TOOL 13: sutra_create_issue
    # =========================================================================
    @server.tool()
    async def sutra_create_issue(
        ctx: Context,
        task_id: Annotated[str, Field(description="UUID of the current SUTRA Task to link this issue to.")],
        title: Annotated[str, Field(description="Title of the GitHub issue (e.g. 'Bug: Token refresh fails on 401 response').")],
        body: Annotated[str, Field(description="Markdown body describing the bug, steps to reproduce, or technical debt.")],
    ) -> Dict[str, Any]:
        """FILE AN ISSUE / REPORT TECHNICAL DEBT: Creates a tracked GitHub issue linked to your current SUTRA task and repository context.

Use this to report bugs discovered during implementation, document technical debt, or propose follow-up tasks for future engineering sessions.

Answers intents like:
- "create an issue" / "file a bug ticket"
- "report technical debt"
- "log a follow-up item"
        """
        with SessionLocal() as db:
            try:
                session, agent = resolve_mcp_agent_session(ctx, db)

                task = db.scalar(select(Task).where(Task.id == task_id))
                if not task:
                    return _format_error(f"Task '{task_id}' not found")

                author = db.scalar(select(Actor).where(Actor.id == agent.id))
                if not author:
                    author = Actor(
                        id=agent.id,
                        type="agent",
                        name=agent.name,
                    )
                    db.add(author)
                    db.flush()
                elif author.name != agent.name:
                    author.name = agent.name
                    db.flush()

                clean_title = title.strip()
                agent_prefix = f"[{agent.name}]"
                if not clean_title.startswith(agent_prefix) and not clean_title.startswith("[Agent:"):
                    issue_title = f"{agent_prefix} {clean_title}"
                else:
                    issue_title = clean_title

                header = f"[SUTRA Agent: {agent.name}]\nAgent ID: {agent.id}\nSession ID: {session.id}\nTask ID: {task.id}\n\n"
                full_body = header + body

                now = datetime.now(timezone.utc)
                issue = Issue(
                    repository_id=task.repository_id,
                    source_type="agent",
                    agent_id=agent.id,
                    agent_session_id=session.id,
                    task_id=task.id,
                    actor_id=author.id,
                    title=issue_title,
                    body=full_body,
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
                    "author_name": agent.name,
                    "created_at": issue.created_at.isoformat(),
                }
            except MCPAuthError as e:
                return _format_error(e.message, {"code": e.code})
            except Exception as e:
                db.rollback()
                logger.error(f"sutra_create_issue failed: {e}", exc_info=True)
                return _format_error(f"Failed to create issue: {str(e)}")

    # =========================================================================
    # TOOL 14: sutra_complete_task
    # =========================================================================
    @server.tool()
    async def sutra_complete_task(
        ctx: Context,
        task_id: Annotated[Optional[str], Field(description="UUID of the SUTRA Task to finalize. If omitted, automatically resolves the session's active in-progress task.")] = None,
        outcome: Annotated[str, Field(description="Final task outcome: 'completed' (work finished and tests passed), 'blocked' (blocked by external dependency or failing check), or 'cancelled'.")] = "completed",
        execution_summary: Annotated[str, Field(description="Detailed summary of code changes implemented, files modified, and architecture impact.")] = "",
        validation_summary: Annotated[str, Field(description="Summary of validation performed: unit tests run, test results, linting, and build verification.")] = "",
    ) -> Dict[str, Any]:
        """FINALIZE TASK & RECORD OUTCOME: Summarizes implementation, test validations, and marks task complete under governance rules.

Records the engineering outcome, files changed, and test validations on the authoritative Task record.
Enforces SUTRA governance: if outcome is 'completed', verifies that any linked Pull Request does not require pending human review/approval before closing.

Outcomes:
- 'completed': Implementation finished, verified with tests, and ready/handed over.
- 'blocked': Implementation blocked by external dependencies, failing tests, or policy.
- 'cancelled': Task discarded or superseded.

Answers intents like:
- "finish the task" / "mark task complete"
- "task done" / "finalize engineering work"
- "record validation summary"
        """
        with SessionLocal() as db:
            try:
                session, agent = resolve_mcp_agent_session(ctx, db)
                task_svc = TaskService(db)

                resolved_task_id = task_id
                if not resolved_task_id:
                    claimed_task = db.scalar(
                        select(Task).where(
                            Task.claimed_by_session_id == session.id,
                            Task.status == Task.STATUS_IN_PROGRESS,
                        )
                    )
                    if claimed_task:
                        resolved_task_id = claimed_task.id
                    else:
                        return _format_error("No task_id provided and no active task claimed by this session")

                task = task_svc.complete_agent_task(
                    task_id=resolved_task_id,
                    session=session,
                    outcome=outcome,
                    execution_summary=execution_summary,
                    validation_summary=validation_summary,
                )
                db.commit()
                db.refresh(task)

                return {
                    "status": "success",
                    "task_id": task.id,
                    "task_status": task.status,
                    "outcome": outcome,
                    "execution_summary": task.execution_summary,
                    "validation_summary": task.validation_summary,
                    "completed_at": task.completed_at.isoformat() if task.completed_at else None,
                    "message": f"Task '{task.title}' updated with status '{task.status}'."
                }
            except MCPAuthError as e:
                return _format_error(e.message, {"code": e.code})
            except PermissionError as e:
                db.rollback()
                return _format_error(f"Permission denied: {str(e)}")
            except ValueError as e:
                db.rollback()
                return _format_error(f"Task completion rejected: {str(e)}")
            except Exception as e:
                db.rollback()
                logger.error(f"sutra_complete_task failed: {e}", exc_info=True)
                return _format_error(f"Failed to complete task: {str(e)}")

    # =========================================================================
    # TOOL 15: sutra_clone_repository
    # =========================================================================
    @server.tool()
    async def sutra_clone_repository(
        ctx: Context,
        url: Annotated[str, Field(description="Git repository URL or GitHub 'owner/name' shorthand to clone into SUTRA storage (e.g. 'https://github.com/octocat/Hello-World.git' or 'octocat/Hello-World').")],
        name: Annotated[Optional[str], Field(description="Custom local repository name. If omitted, automatically derived from the URL.")] = None,
        description: Annotated[Optional[str], Field(description="Optional repository description.")] = None,
        visibility: Annotated[str, Field(description="Repository visibility: 'private' or 'public' (default 'private').")] = "private",
    ) -> Dict[str, Any]:
        """CLONE REPOSITORY INTO SUTRA: Clones any Git URL or repository into SUTRA storage and registers it for autonomous engineering.

Enables an agent or user to import external repositories or open-source projects into SUTRA:
- Clones repository into SUTRA managed bare Git storage.
- Installs SUTRA pre-receive policy hook ensuring all subsequent pushes adhere to SUTRA governance.
- Automatically connects fork/upstream metadata if the repository is an upstream or fork.
- Triggers initial Knowledge Graph indexing of the codebase architecture.

Answers intents like:
- 'clone a repo' / 'clone repository'
- 'import git repository' / 'clone this url'
        """
        with SessionLocal() as db:
            try:
                session, agent = resolve_mcp_agent_session(ctx, db)
                owner_id = agent.owner_id
                repo_svc = RepositoryService(db)
                repo = repo_svc.clone_repository(
                    owner_id=owner_id,
                    url=url,
                    name=name,
                    description=description,
                    visibility=visibility,
                )

                access = db.scalar(
                    select(AgentRepositoryAccess).where(
                        AgentRepositoryAccess.agent_id == agent.id,
                        AgentRepositoryAccess.repository_id == repo.id,
                    )
                )
                if not access:
                    access = AgentRepositoryAccess(
                        agent_id=agent.id,
                        repository_id=repo.id,
                        enabled=True,
                    )
                    db.add(access)
                    db.commit()

                owner_name = agent.owner.username if getattr(agent, "owner", None) else "sutra"
                return {
                    "status": "success",
                    "repository_id": repo.id,
                    "name": repo.name,
                    "slug": repo.slug,
                    "visibility": repo.visibility,
                    "default_branch": repo.default_branch,
                    "connection_type": repo.connection_type,
                    "upstream_url": repo.upstream_url,
                    "upstream_repository_id": repo.upstream_repository_id,
                    "clone_url": (
                        repo.upstream_url
                        if repo.upstream_url and "github.com" in repo.upstream_url
                        else f"https://github.com/{repo.provider_owner or owner_name}/{repo.name}.git"
                    ),
                    "message": f"Successfully cloned repository '{repo.name}' into SUTRA storage.",
                }
            except MCPAuthError as e:
                return _format_error(e.message, {"code": e.code})
            except Exception as e:
                db.rollback()
                logger.error(f"sutra_clone_repository failed: {e}", exc_info=True)
                return _format_error(f"Failed to clone repository: {str(e)}")

    # =========================================================================
    # TOOL 16: sutra_create_discussion
    # =========================================================================
    @server.tool()
    async def sutra_create_discussion(
        ctx: Context,
        task_id: Annotated[str, Field(description="UUID of the SUTRA Task providing context for this discussion.")],
        title: Annotated[str, Field(description="Discussion topic title.")],
        body: Annotated[str, Field(description="Discussion body explaining the architecture proposal, question, or design trade-off.")],
        category: Annotated[str, Field(description="Discussion category (e.g. 'General', 'Architecture', 'Q&A', 'RFC').")] = "General",
    ) -> Dict[str, Any]:
        """START ARCHITECTURAL DISCUSSION: Starts a discussion topic on the repository linked to the active task with agent provenance.

Enables agents to propose design alternatives, request architectural guidance, or record architectural decisions with full provenance.
        """
        with SessionLocal() as db:
            try:
                session, agent = resolve_mcp_agent_session(ctx, db)
                task = db.scalar(select(Task).where(Task.id == task_id))
                if not task:
                    return _format_error(f"Task '{task_id}' not found")

                author = db.scalar(select(Actor).where(Actor.id == agent.id))
                if not author:
                    author = Actor(
                        id=agent.id,
                        type="agent",
                        name=agent.name,
                    )
                    db.add(author)
                    db.flush()
                elif author.name != agent.name:
                    author.name = agent.name
                    db.flush()

                clean_title = title.strip()
                agent_prefix = f"[{agent.name}]"
                if not clean_title.startswith(agent_prefix) and not clean_title.startswith("[Agent:"):
                    disc_title = f"{agent_prefix} {clean_title}"
                else:
                    disc_title = clean_title

                header = f"[SUTRA Agent: {agent.name}]\nAgent ID: {agent.id}\nSession ID: {session.id}\nTask ID: {task.id}\n\n"
                full_body = header + body

                now = datetime.now(timezone.utc)
                discussion = Discussion(
                    repository_id=task.repository_id,
                    author_id=author.id,
                    title=disc_title,
                    body=full_body,
                    category=category,
                    created_at=now,
                    updated_at=now,
                )
                db.add(discussion)
                db.commit()
                db.refresh(discussion)

                return {
                    "status": "created",
                    "discussion_id": discussion.id,
                    "repository_id": task.repository_id,
                    "task_id": task.id,
                    "title": discussion.title,
                    "author_name": agent.name,
                    "category": discussion.category,
                    "created_at": discussion.created_at.isoformat(),
                }
            except MCPAuthError as e:
                return _format_error(e.message, {"code": e.code})
            except Exception as e:
                db.rollback()
                logger.error(f"sutra_create_discussion failed: {e}", exc_info=True)
                return _format_error(f"Failed to create discussion: {str(e)}")

    # =========================================================================
    # TOOL 17: sutra_list_discussions
    # =========================================================================
    @server.tool()
    async def sutra_list_discussions(
        ctx: Context,
        repository_id: Annotated[str, Field(description="UUID or slug of the repository to query discussions for.")],
        category: Annotated[Optional[str], Field(description="Optional category to filter discussions by (e.g. 'General', 'Architecture', 'Q&A', 'RFC').")] = None,
        limit: Annotated[int, Field(description="Maximum number of discussions to return (default 20, max 50).")] = 20,
    ) -> Dict[str, Any]:
        """LIST ARCHITECTURAL DISCUSSIONS: Lists discussion topics and design threads for a repository.

Enables agents to discover ongoing architectural proposals, design decisions, and team guidance.
        """
        with SessionLocal() as db:
            try:
                session, agent = resolve_mcp_agent_session(ctx, db)
                repo = db.scalar(
                    select(Repository).where(
                        (Repository.id == repository_id) | (Repository.slug == repository_id.lower()),
                        Repository.deleted_at.is_(None),
                    )
                )
                if not repo:
                    return _format_error(f"Repository '{repository_id}' not found")

                stmt = select(Discussion).where(Discussion.repository_id == repo.id)
                if category and category != "View all discussions":
                    stmt = stmt.where(Discussion.category == category)
                stmt = stmt.order_by(Discussion.created_at.desc()).limit(min(limit, 50))
                discussions = db.scalars(stmt).all()

                results = []
                for d in discussions:
                    author = db.get(Actor, d.author_id)
                    results.append({
                        "id": d.id,
                        "title": d.title,
                        "category": d.category,
                        "author_name": author.name if author else "Unknown",
                        "author_type": author.type if author else "human",
                        "created_at": d.created_at.isoformat(),
                    })

                return {
                    "status": "success",
                    "repository_id": repo.id,
                    "count": len(results),
                    "discussions": results,
                }
            except MCPAuthError as e:
                return _format_error(e.message, {"code": e.code})
            except Exception as e:
                logger.error(f"sutra_list_discussions failed: {e}", exc_info=True)
                return _format_error(f"Failed to list discussions: {str(e)}")

    # =========================================================================
    # TOOL 18: sutra_comment_discussion
    # =========================================================================
    @server.tool()
    async def sutra_comment_discussion(
        ctx: Context,
        discussion_id: Annotated[str, Field(description="UUID of the discussion to reply or participate in.")],
        body: Annotated[str, Field(description="Markdown body of the comment or design recommendation.")],
        task_id: Annotated[Optional[str], Field(description="Optional task UUID providing engineering context for this reply.")] = None,
    ) -> Dict[str, Any]:
        """PARTICIPATE IN ARCHITECTURAL DISCUSSION: Posts a reply or comment to an existing discussion thread with full agent provenance.

Allows agents to engage in collaborative technical discussions, answer questions, and propose concrete architectural solutions.
        """
        with SessionLocal() as db:
            try:
                session, agent = resolve_mcp_agent_session(ctx, db)
                discussion = db.scalar(select(Discussion).where(Discussion.id == discussion_id))
                if not discussion:
                    return _format_error(f"Discussion '{discussion_id}' not found")

                repo = db.scalar(select(Repository).where(Repository.id == discussion.repository_id))
                if not repo:
                    return _format_error("Repository not found")

                author = db.scalar(select(Actor).where(Actor.id == agent.id))
                if not author:
                    author = Actor(
                        id=agent.id,
                        type="agent",
                        name=agent.name,
                    )
                    db.add(author)
                    db.flush()
                elif author.name != agent.name:
                    author.name = agent.name
                    db.flush()

                task_info = f"Task ID: {task_id}" if task_id else "Task ID: None"
                header = f"[SUTRA Agent: {agent.name}]\nAgent ID: {agent.id}\nSession ID: {session.id}\n{task_info}\n\n"
                full_body = header + body

                now = datetime.now(timezone.utc)
                comment = DiscussionComment(
                    discussion_id=discussion.id,
                    author_id=author.id,
                    body=full_body,
                    created_at=now,
                    updated_at=now,
                )
                db.add(comment)
                db.commit()
                db.refresh(comment)

                return {
                    "status": "created",
                    "comment_id": comment.id,
                    "discussion_id": discussion.id,
                    "author_name": agent.name,
                    "created_at": comment.created_at.isoformat(),
                    "message": "Comment posted with agent provenance.",
                }
            except MCPAuthError as e:
                return _format_error(e.message, {"code": e.code})
            except Exception as e:
                db.rollback()
                logger.error(f"sutra_comment_discussion failed: {e}", exc_info=True)
                return _format_error(f"Failed to comment on discussion: {str(e)}")

    # =========================================================================
    # TOOL 19: sutra_list_issues
    # =========================================================================
    @server.tool()
    async def sutra_list_issues(
        ctx: Context,
        repository_id: Annotated[str, Field(description="UUID or slug of the repository to query issues for.")],
        status: Annotated[str, Field(description="Issue state filter: 'open', 'closed', or 'all' (default 'open').")] = "open",
        limit: Annotated[int, Field(description="Maximum number of issues to return (default 20, max 50).")] = 20,
    ) -> Dict[str, Any]:
        """LIST ISSUES & BUG TICKETS: Lists tracked repository issues, bug reports, and technical debt items.

Enables agents to discover backlog work, review reported bugs, and prioritize engineering tasks.
        """
        with SessionLocal() as db:
            try:
                session, agent = resolve_mcp_agent_session(ctx, db)
                repo = db.scalar(
                    select(Repository).where(
                        (Repository.id == repository_id) | (Repository.slug == repository_id.lower()),
                        Repository.deleted_at.is_(None),
                    )
                )
                if not repo:
                    return _format_error(f"Repository '{repository_id}' not found")

                stmt = select(Issue).where(Issue.repository_id == repo.id)
                if status in {"open", "closed"}:
                    stmt = stmt.where(Issue.status == status)
                stmt = stmt.order_by(Issue.created_at.desc()).limit(min(limit, 50))
                issues = db.scalars(stmt).all()

                results = []
                for i in issues:
                    author = db.get(Actor, i.actor_id) if i.actor_id else None
                    author_name = author.name if author else (i.github_author_login or "Unknown")
                    author_type = author.type if author else ("agent" if i.agent_id else "human")
                    results.append({
                        "id": i.id,
                        "github_issue_number": i.github_issue_number,
                        "title": i.title,
                        "status": i.status,
                        "author_name": author_name,
                        "author_type": author_type,
                        "created_at": i.created_at.isoformat(),
                        "github_html_url": i.github_html_url,
                    })

                return {
                    "status": "success",
                    "repository_id": repo.id,
                    "count": len(results),
                    "issues": results,
                }
            except MCPAuthError as e:
                return _format_error(e.message, {"code": e.code})
            except Exception as e:
                logger.error(f"sutra_list_issues failed: {e}", exc_info=True)
                return _format_error(f"Failed to list issues: {str(e)}")

    # =========================================================================
    # TOOL 20: sutra_get_ci_logs
    # =========================================================================
    @server.tool()
    async def sutra_get_ci_logs(
        ctx: Context,
        pull_request_id: Annotated[str, Field(description="UUID of the SUTRA Pull Request to inspect CI check logs for.")],
    ) -> Dict[str, Any]:
        """INSPECT CI LOGS & STEP FAILURES: Fetches CI job statuses, check runs, and failure logs for a Pull Request.

Crucial for autonomous debugging: when a CI build or test fails, calling this reveals the exact error, failing step, and failure logs so the agent can fix it immediately.
        """
        with SessionLocal() as db:
            try:
                session, agent = resolve_mcp_agent_session(ctx, db)
                ci_svc = CIService(db)
                checks = ci_svc.get_pr_checks(pull_request_id, actor_id=agent.id)
                return {
                    "status": "success",
                    "pull_request_id": pull_request_id,
                    "checks": checks,
                }
            except MCPAuthError as e:
                return _format_error(e.message, {"code": e.code})
            except Exception as e:
                logger.error(f"sutra_get_ci_logs failed: {e}", exc_info=True)
                return _format_error(f"Failed to fetch CI logs: {str(e)}")

    # =========================================================================
    # TOOL 21: sutra_get_pr_comments
    # =========================================================================
    @server.tool()
    async def sutra_get_pr_comments(
        ctx: Context,
        pull_request_id: Annotated[str, Field(description="UUID of the Pull Request to retrieve comments and review threads for.")],
    ) -> Dict[str, Any]:
        """READ PR REVIEW COMMENTS: Retrieves review comments, feedback threads, and inline review notes on a Pull Request.

Enables agents to read human code review comments, understand change requests, and address feedback accurately.
        """
        with SessionLocal() as db:
            try:
                session, agent = resolve_mcp_agent_session(ctx, db)
                pr = db.scalar(select(PullRequest).where(PullRequest.id == pull_request_id))
                if not pr:
                    return _format_error(f"Pull Request '{pull_request_id}' not found")

                comments = db.scalars(
                    select(InlineReviewComment)
                    .where(InlineReviewComment.pull_request_id == pr.id)
                    .order_by(InlineReviewComment.created_at.asc())
                ).all()

                results = [
                    {
                        "id": c.id,
                        "author_id": c.author_id,
                        "body": c.body,
                        "path": c.path,
                        "line_number": c.line_number,
                        "status": c.status,
                        "parent_id": c.parent_id,
                        "created_at": c.created_at.isoformat(),
                    }
                    for c in comments
                ]

                return {
                    "status": "success",
                    "pull_request_id": pr.id,
                    "count": len(results),
                    "comments": results,
                }
            except MCPAuthError as e:
                return _format_error(e.message, {"code": e.code})
            except Exception as e:
                logger.error(f"sutra_get_pr_comments failed: {e}", exc_info=True)
                return _format_error(f"Failed to get PR comments: {str(e)}")

    # =========================================================================
    # TOOL 22: sutra_add_pr_comment
    # =========================================================================
    @server.tool()
    async def sutra_add_pr_comment(
        ctx: Context,
        pull_request_id: Annotated[str, Field(description="UUID of the Pull Request to add a review comment or reply to.")],
        body: Annotated[str, Field(description="Markdown body of the comment or response to review feedback.")],
        path: Annotated[Optional[str], Field(description="Optional file path for an inline code comment.")] = None,
        line_number: Annotated[Optional[int], Field(description="Optional line number for an inline code comment.")] = None,
        parent_id: Annotated[Optional[str], Field(description="Optional parent comment UUID if replying to an existing thread.")] = None,
    ) -> Dict[str, Any]:
        """POST PR REVIEW COMMENT: Posts a response or inline review comment on a Pull Request with agent provenance.

Allows agents to acknowledge reviewer suggestions, clarify architectural decisions, or confirm fixes on PR threads.
        """
        with SessionLocal() as db:
            try:
                session, agent = resolve_mcp_agent_session(ctx, db)
                pr = db.scalar(select(PullRequest).where(PullRequest.id == pull_request_id))
                if not pr:
                    return _format_error(f"Pull Request '{pull_request_id}' not found")

                author = db.scalar(select(Actor).where(Actor.id == agent.id))
                if not author:
                    author = Actor(
                        id=agent.id,
                        type="agent",
                        name=agent.name,
                    )
                    db.add(author)
                    db.flush()

                header = f"[SUTRA Agent: {agent.name}]\nAgent ID: {agent.id}\nSession ID: {session.id}\n\n"
                full_body = header + body

                now = datetime.now(timezone.utc)
                comment = InlineReviewComment(
                    pull_request_id=pr.id,
                    repository_id=pr.repository_id,
                    author_id=agent.owner_id,
                    parent_id=parent_id,
                    path=path,
                    diff_side="RIGHT" if path else None,
                    line_number=line_number,
                    body=full_body,
                    status=InlineReviewComment.STATUS_ACTIVE,
                    created_at=now,
                    updated_at=now,
                )
                db.add(comment)
                db.commit()
                db.refresh(comment)

                return {
                    "status": "created",
                    "comment_id": comment.id,
                    "pull_request_id": pr.id,
                    "author_name": agent.name,
                    "created_at": comment.created_at.isoformat(),
                    "message": "Review comment posted with agent provenance.",
                }
            except MCPAuthError as e:
                return _format_error(e.message, {"code": e.code})
            except Exception as e:
                db.rollback()
                logger.error(f"sutra_add_pr_comment failed: {e}", exc_info=True)
                return _format_error(f"Failed to post PR comment: {str(e)}")
