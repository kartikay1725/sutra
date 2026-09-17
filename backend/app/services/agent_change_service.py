import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.actor import Actor
from app.models.agent import Agent
from app.models.agent_session import AgentSession
from app.models.change import Change
from app.models.change_event import ChangeEvent
from app.models.change_file import ChangeFile
from app.models.pull_request import PullRequest
from app.models.repository import Repository
from app.models.task import Task
from app.models.task_event import TaskEvent
from app.providers.base import RepositoryProvider
from app.providers.github.repository import GitHubRepositoryProvider
from app.services.authorization_service import AuthorizationService
from app.services.change_policy_service import ChangePolicyService
from app.services.change_service import ChangeService
from app.services.pull_request_service import PullRequestService


class AgentChangeService:
    """
    Service for Agent-originated Change lifecycle operations.

    Enforces sovereign AgentSession governance:
        session.agent_id == task.assigned_agent_id
        task.claimed_by_session_id == session.id

    Links:
        Task
          ↓
        AgentSession
          ↓
        Agent Change
          ↓
        SUTRA Change record (linked to task.resulting_change_id)
          ↓
        Repository / Branch / Commit substrate
    """

    def __init__(
        self,
        db: Session,
        provider: Optional[RepositoryProvider] = None,
    ):
        self.db = db
        self.provider = provider

    def _validate_session_and_task(
        self,
        session: AgentSession,
        task: Task,
    ) -> tuple[Agent, Actor, Repository]:
        # 1. Validate active agent
        agent = self.db.scalar(
            select(Agent).where(
                Agent.id == session.agent_id,
                Agent.is_active.is_(True),
                Agent.status == "active",
            )
        )
        if agent is None:
            raise PermissionError("Agent session does not belong to an active agent")

        # 2. Validate task assignment
        if task.assigned_agent_id != agent.id:
            raise PermissionError("Agent is not assigned to this task")

        # 3. Validate task lease hold
        if task.claimed_by_session_id != session.id:
            raise PermissionError("Agent session does not hold the task lease")

        # 4. Check lease expiration
        now = datetime.now(timezone.utc)
        if task.lease_expires_at:
            lease_exp = task.lease_expires_at
            if lease_exp.tzinfo is None:
                lease_exp = lease_exp.replace(tzinfo=timezone.utc)
            if lease_exp <= now:
                raise ValueError("Task lease expired")

        # 5. Validate repository
        repository = self.db.scalar(
            select(Repository).where(
                Repository.id == task.repository_id,
                Repository.deleted_at.is_(None),
            )
        )
        if repository is None:
            raise ValueError("Task repository not found")

        # 6. Ensure Agent Actor exists
        actor = self.db.scalar(
            select(Actor).where(Actor.id == agent.id)
        )
        if actor is None:
            actor = Actor(
                id=agent.id,
                owner_id=agent.owner_id,
                type="agent",
                name=agent.name,
                capabilities=json.dumps([
                    "repository.read",
                    "repository.write",
                    "change.create",
                    "change.commit",
                    "change.conflict.read",
                ]),
            )
            self.db.add(actor)
            self.db.flush()

        return agent, actor, repository

    def create_change(
        self,
        *,
        session: AgentSession,
        task: Task,
        intent: str,
        branch: Optional[str] = None,
        base_branch: Optional[str] = None,
        base_commit: Optional[str] = None,
        risk_level: str = "unknown",
    ) -> Change:
        agent, actor, repository = self._validate_session_and_task(session, task)

        # Enforce change.create capability
        try:
            AuthorizationService.require(
                actor=actor,
                repository=repository,
                capability=AuthorizationService.CHANGE_CREATE,
                db=self.db,
            )
        except PermissionError as exc:
            raise PermissionError(str(exc)) from exc

        # Determine base branch
        resolved_base_branch = (
            base_branch
            or getattr(repository, "default_branch", None)
            or "main"
        )

        # Determine base commit using substrate provider where available
        resolved_base_commit = base_commit
        if not resolved_base_commit:
            if isinstance(self.provider, GitHubRepositoryProvider) and repository.provider_owner:
                try:
                    gh_branch = self.provider.get_branch(
                        owner=repository.provider_owner,
                        name=repository.name,
                        branch=resolved_base_branch,
                    )
                    if gh_branch:
                        resolved_base_commit = gh_branch.commit_sha
                except Exception:
                    pass

            if not resolved_base_commit and repository.storage_key:
                storage_root = Path(settings.repository_storage_path).resolve()
                repo_path = (storage_root / repository.storage_key).resolve()
                if repo_path.exists():
                    res = subprocess.run(
                        [
                            "git",
                            "--git-dir",
                            str(repo_path),
                            "rev-parse",
                            f"{resolved_base_branch}^{{commit}}",
                        ],
                        capture_output=True,
                        text=True,
                        check=False,
                    )
                    if res.returncode == 0:
                        resolved_base_commit = res.stdout.strip()

        # Determine target branch
        clean_name = agent.name.lower().replace(" ", "-")
        resolved_branch = branch or f"agent/{clean_name}/task-{task.id[:8]}"

        metadata = {
            "task_id": task.id,
            "task_title": task.title,
            "agent_id": agent.id,
            "agent_name": agent.name,
            "agent_session_id": session.id,
            "branch": resolved_branch,
            "base_branch": resolved_base_branch,
            "source": "agent",
            "commit_origin": "pending",  # Updated to 'sutra_governed' by push_governed_commit or 'external_unverified' by import path
            "intent": intent,
            "risk_level": risk_level,
        }

        # Check if task already has a resulting change in proposed status
        change = None
        if task.resulting_change_id:
            existing = self.db.scalar(
                select(Change).where(Change.id == task.resulting_change_id)
            )
            if existing and existing.status == "proposed":
                change = existing
                change.intent = intent
                change.risk_level = risk_level
                if resolved_base_commit:
                    change.base_commit = resolved_base_commit
                change.metadata_json = json.dumps(metadata, sort_keys=True)
                change.updated_at = datetime.now(timezone.utc)

        if change is None:
            change = Change(
                id=str(uuid4()),
                repository_id=repository.id,
                actor_id=actor.id,
                intent=intent,
                base_commit=resolved_base_commit,
                resulting_commit=None,
                operation_key=(uuid4().hex * 2)[:64],
                status="proposed",
                risk_level=risk_level,
                metadata_json=json.dumps(metadata, sort_keys=True),
            )
            self.db.add(change)
            self.db.flush()

        task.resulting_change_id = change.id
        if task.status == Task.STATUS_ASSIGNED:
            task.status = Task.STATUS_IN_PROGRESS
        task.updated_at = datetime.now(timezone.utc)

        # Audit events
        change_service = ChangeService(self.db)
        change_service.transition_change(
            change=change,
            new_status="proposed",
            actor_id=actor.id,
            event_type="change.created",
            reason="Change declared by authenticated agent session for task.",
            metadata=metadata,
        )

        task_event = TaskEvent(
            id=str(uuid4()),
            task_id=task.id,
            actor_id=actor.id,
            session_id=session.id,
            event_type="task.change_created",
            from_status=task.status,
            to_status=task.status,
            metadata_json=json.dumps({
                "task_id": task.id,
                "change_id": change.id,
                "agent_id": agent.id,
                "branch": resolved_branch,
            }),
            created_at=datetime.now(timezone.utc),
        )
        self.db.add(task_event)
        self.db.flush()

        return change

    def record_commit(
        self,
        *,
        session: AgentSession,
        task: Task,
        resulting_commit: str,
    ) -> Change:
        agent, actor, repository = self._validate_session_and_task(session, task)

        if not task.resulting_change_id:
            raise ValueError("Task does not have an active Change record. Create a Change first.")

        change = self.db.scalar(
            select(Change).where(Change.id == task.resulting_change_id)
        )
        if change is None:
            raise ValueError("Resulting Change record not found")

        if change.actor_id != actor.id:
            raise PermissionError("Agent does not own this change")

        if change.status != "proposed":
            raise ValueError(f"Change cannot accept commits in status '{change.status}'")

        # Enforce change.commit capability
        try:
            AuthorizationService.require(
                actor=actor,
                repository=repository,
                capability=AuthorizationService.CHANGE_COMMIT,
                db=self.db,
            )
        except PermissionError as exc:
            raise PermissionError(str(exc)) from exc

        # Handle GitHub-backed repository
        if isinstance(self.provider, GitHubRepositoryProvider) and repository.provider_owner:
            # Verify commit exists on GitHub
            commit_obj = self.provider.get_commit(
                owner=repository.provider_owner,
                name=repository.name,
                sha=resulting_commit,
            )
            if not commit_obj:
                raise ValueError(
                    f"Commit '{resulting_commit}' was not found on GitHub repository"
                )

            # Get diff stats from GitHub compare API if base_commit exists
            files_data = []
            if change.base_commit:
                try:
                    diff_stats = self.provider.get_diff_stats(
                        owner=repository.provider_owner,
                        name=repository.name,
                        base=change.base_commit,
                        head=resulting_commit,
                    )
                    files_data = diff_stats.changed_files
                except Exception:
                    pass

            # Clear old change files and record new ones
            existing_files = self.db.scalars(
                select(ChangeFile).where(ChangeFile.change_id == change.id)
            ).all()
            for ef in existing_files:
                self.db.delete(ef)

            for f in files_data:
                self.db.add(
                    ChangeFile(
                        change_id=change.id,
                        path=f.get("filename") or "unknown",
                        operation=f.get("status") or "modified",
                        additions=f.get("additions", 0),
                        deletions=f.get("deletions", 0),
                    )
                )

            change.resulting_commit = resulting_commit
            change.status = "recorded"
            change.updated_at = datetime.now(timezone.utc)

            # Update metadata_json
            try:
                meta = json.loads(change.metadata_json or "{}")
            except Exception:
                meta = {}
            meta["resulting_commit"] = resulting_commit
            meta["committed_at"] = datetime.now(timezone.utc).isoformat()
            change.metadata_json = json.dumps(meta, sort_keys=True)

            # Record event
            commit_origin = "unknown"
            try:
                _meta = json.loads(change.metadata_json or "{}")
                commit_origin = _meta.get("commit_origin", "unknown")
            except Exception:
                pass
            event = ChangeEvent(
                id=str(uuid4()),
                change_id=change.id,
                actor_id=actor.id,
                event_type="change.commit_attached",
                from_status="proposed",
                to_status="recorded",
                reason=(
                    f"Commit {resulting_commit[:8]} registered via SUTRA-governed push. "
                    f"Session: {session.id[:8]}. Origin: {commit_origin}."
                ),
                metadata_json=json.dumps({
                    "commit_sha": resulting_commit,
                    "commit_origin": commit_origin,
                    "task_id": task.id,
                    "agent_id": agent.id,
                    "session_id": session.id,
                }),
                created_at=datetime.now(timezone.utc),
            )
            self.db.add(event)
            self.db.flush()

            return change

        # Fallback to local git repository via ChangeService
        change_service = ChangeService(self.db)
        return change_service.record_commit(
            change=change,
            repository=repository,
            actor=actor,
            resulting_commit=resulting_commit,
        )

    def push_governed_commit(
        self,
        *,
        session: AgentSession,
        task: Task,
        change: "Change",
        file_patches: list,
        commit_message: str,
    ) -> dict:
        """Execute a SUTRA-governed commit via the GitHub App installation token.

        The agent never calls git push. SUTRA uses its GitHub App token to:
          1. Create blobs for each file patch.
          2. Build a tree on top of the current branch HEAD.
          3. Create a commit object authored by the SUTRA App.
          4. Advance the branch ref (fast-forward only).

        On success:
          - Sets change.resulting_commit = new SHA.
          - Sets change.status = 'recorded'.
          - Updates change.metadata_json[commit_origin] = 'sutra_governed'.
          - Creates a ChangeEvent stamped with session + task.

        Returns:
            Dict with commit_sha, branch, html_url.

        Raises:
            PermissionError: session/task validation failure.
            ValueError: commit cannot be created (bad branch, empty patches, etc.).
        """
        agent, actor, repository = self._validate_session_and_task(session, task)

        if not isinstance(self.provider, GitHubRepositoryProvider) or not repository.provider_owner:
            raise ValueError(
                "push_governed_commit requires a GitHub-backed repository with a configured SUTRA GitHub App."
            )

        if change.actor_id != actor.id:
            raise PermissionError("Agent does not own this change.")

        if change.status != "proposed":
            raise ValueError(
                f"Only proposed changes can receive a governed commit (current status: '{change.status}')."
            )

        if not file_patches:
            raise ValueError("file_patches must contain at least one file entry.")

        # Enforce change.commit capability
        AuthorizationService.require(
            actor=actor,
            repository=repository,
            capability=AuthorizationService.CHANGE_COMMIT,
            db=self.db,
        )

        try:
            meta = json.loads(change.metadata_json or "{}")
        except Exception:
            meta = {}

        branch = meta.get("branch") or f"agent/{agent.name.lower().replace(' ', '-')}/task-{task.id[:8]}"
        base_branch = meta.get("base_branch") or getattr(repository, "default_branch", None) or "main"

        # Derive author identity from agent record
        author_name = f"SUTRA Agent [{agent.name}]"
        author_email = f"sutra-agent+{agent.id[:8]}@sutra.ai"

        # Execute SUTRA-governed commit via GitHub App
        result = self.provider.create_governed_commit(
            owner=repository.provider_owner,
            name=repository.name,
            branch=branch,
            commit_message=commit_message,
            file_patches=file_patches,
            author_name=author_name,
            author_email=author_email,
            base_branch=base_branch,
        )

        new_sha = result["commit_sha"]

        # Stamp the change with the governed SHA
        change.resulting_commit = new_sha
        change.status = "recorded"
        change.updated_at = datetime.now(timezone.utc)

        meta["resulting_commit"] = new_sha
        meta["committed_at"] = datetime.now(timezone.utc).isoformat()
        meta["commit_origin"] = "sutra_governed"
        meta["commit_html_url"] = result.get("html_url")
        change.metadata_json = json.dumps(meta, sort_keys=True)

        # Sync ChangeFiles from GitHub diff
        if change.base_commit:
            try:
                from app.models.change_file import ChangeFile
                from sqlalchemy import select as _select
                diff_stats = self.provider.get_diff_stats(
                    owner=repository.provider_owner,
                    name=repository.name,
                    base=change.base_commit,
                    head=new_sha,
                )
                existing_files = self.db.scalars(
                    _select(ChangeFile).where(ChangeFile.change_id == change.id)
                ).all()
                for ef in existing_files:
                    self.db.delete(ef)
                for f in diff_stats.changed_files:
                    self.db.add(
                        ChangeFile(
                            change_id=change.id,
                            path=f.get("filename") or "unknown",
                            operation=f.get("status") or "modified",
                            additions=f.get("additions", 0),
                            deletions=f.get("deletions", 0),
                        )
                    )
            except Exception:
                pass  # Non-fatal: diff sync failure doesn't block commit recording

        # Audit ChangeEvent
        audit_event = ChangeEvent(
            id=str(uuid4()),
            change_id=change.id,
            actor_id=actor.id,
            event_type="change.commit_governed",
            from_status="proposed",
            to_status="recorded",
            reason=(
                f"Commit {new_sha[:8]} created by SUTRA GitHub App (governed). "
                f"Session: {session.id[:8]}. Task: {task.id[:8]}."
            ),
            metadata_json=json.dumps({
                "commit_sha": new_sha,
                "commit_origin": "sutra_governed",
                "branch": branch,
                "task_id": task.id,
                "agent_id": agent.id,
                "session_id": session.id,
                "commit_html_url": result.get("html_url"),
            }),
            created_at=datetime.now(timezone.utc),
        )
        self.db.add(audit_event)

        # Task event
        task_event = TaskEvent(
            id=str(uuid4()),
            task_id=task.id,
            actor_id=actor.id,
            session_id=session.id,
            event_type="task.governed_commit_pushed",
            from_status=task.status,
            to_status=task.status,
            metadata_json=json.dumps({
                "task_id": task.id,
                "change_id": change.id,
                "commit_sha": new_sha,
                "commit_origin": "sutra_governed",
                "branch": branch,
            }),
            created_at=datetime.now(timezone.utc),
        )
        self.db.add(task_event)
        self.db.flush()

        return {
            "commit_sha": new_sha,
            "branch": branch,
            "html_url": result.get("html_url"),
            "commit_origin": "sutra_governed",
        }

    def create_pull_request(
        self,
        *,
        session: AgentSession,
        task: Task,
        title: Optional[str] = None,
        target_branch: Optional[str] = None,
        description: Optional[str] = None,
        is_draft: bool = False,
    ) -> PullRequest:
        agent, actor, repository = self._validate_session_and_task(session, task)

        if not task.resulting_change_id:
            raise ValueError("Task does not have an active Change record. Create a Change first.")

        change = self.db.scalar(
            select(Change).where(Change.id == task.resulting_change_id)
        )
        if change is None:
            raise ValueError("Resulting Change record not found")

        if change.actor_id != actor.id:
            raise PermissionError("Agent does not own this change")

        if change.repository_id != repository.id:
            raise ValueError("Change does not belong to target repository")

        if change.status != "recorded" or not change.resulting_commit:
            raise ValueError(
                f"Change must be in 'recorded' status with a recorded commit before creating a PR (current status: '{change.status}')"
            )

        # Enforce write / PR capability
        try:
            AuthorizationService.require(
                actor=actor,
                repository=repository,
                capability=AuthorizationService.WRITE,
                db=self.db,
            )
        except PermissionError as exc:
            raise PermissionError(str(exc)) from exc

        # Check existing PR for this change (idempotency)
        existing_pr = self.db.scalar(
            select(PullRequest).where(PullRequest.source_change_id == change.id)
        )
        if existing_pr is not None:
            if task.resulting_pull_request_id != existing_pr.id:
                task.resulting_pull_request_id = existing_pr.id
                task.updated_at = datetime.now(timezone.utc)
                self.db.flush()
            return existing_pr

        # Determine branches
        try:
            meta = json.loads(change.metadata_json or "{}")
        except Exception:
            meta = {}

        clean_name = agent.name.lower().replace(" ", "-")
        head_branch = meta.get("branch") or f"agent/{clean_name}/task-{task.id[:8]}"
        base_branch = (
            target_branch
            or meta.get("base_branch")
            or getattr(repository, "default_branch", None)
            or "main"
        )

        # Enforce repository-configured PR policies for agents
        repo_policies = (repository.settings or {}).get("policies", {})
        from app.services.branch_protection_service import BranchProtectionService
        from app.services.conflict_service import ConflictService
        effective_rule = BranchProtectionService(self.db).get_effective_rule(
            repository.id, base_branch
        )

        if repo_policies.get("enforce_governed_provenance"):
            if meta.get("commit_origin") == "external_unverified":
                raise ValueError(
                    "Policy violation: Agent PR rejected due to unverified external commit provenance."
                )

        if repo_policies.get("require_clean_conflict") or (
            effective_rule and effective_rule.require_clean_conflict
        ):
            conflict = ConflictService(self.db).analyze(change)
            if conflict.level == ConflictService.LEVEL_CONFLICT:
                raise ValueError(
                    f"Policy violation: Agent PR creation blocked because Git detected a merge conflict with '{base_branch}'."
                )

        pr_title = (title or task.title or change.intent or f"Task: {task.title}").strip()

        # Format SUTRA Agent provenance block for GitHub PR body
        provenance_footer = (
            f"\n\n---\n"
            f"### SUTRA Agent Provenance\n"
            f"- **Agent:** {agent.name} (`{agent.id}`)\n"
            f"- **Session ID:** `{session.id}`\n"
            f"- **Task ID:** `{task.id}` ({task.title})\n"
            f"- **Change ID:** `{change.id}`\n"
            f"- **Commit SHA:** `{change.resulting_commit}`\n"
        )
        raw_body = (description or task.description or change.intent or "").strip()
        full_body = (raw_body + provenance_footer).strip()

        gh_pr_number = None
        gh_pr_url = None

        # Create GitHub Pull Request if backed by GitHub
        if isinstance(self.provider, GitHubRepositoryProvider) and repository.provider_owner:
            # Verify head branch exists on GitHub fork/local repo
            gh_branch = self.provider.get_branch(
                owner=repository.provider_owner,
                name=repository.name,
                branch=head_branch,
            )
            if not gh_branch:
                raise ValueError(
                    f"Head branch '{head_branch}' does not exist on GitHub repository"
                )

            # Determine target upstream repo and head reference for fork PRs
            target_owner = repository.provider_owner
            target_repo = repository.name
            target_head = head_branch

            if getattr(repository, "connection_type", None) == "fork" and getattr(repository, "upstream_repository_id", None):
                upstream = self.db.scalar(
                    select(Repository).where(Repository.id == repository.upstream_repository_id)
                )
                if upstream and upstream.provider_owner:
                    target_owner = upstream.provider_owner
                    target_repo = upstream.name
                    target_head = f"{repository.provider_owner}:{head_branch}"

            gh_pr = self.provider.create_pull_request(
                owner=target_owner,
                name=target_repo,
                title=pr_title,
                body=full_body,
                head_branch=target_head,
                base_branch=base_branch,
            )
            gh_pr_number = gh_pr.number
            gh_pr_url = gh_pr.html_url

        # Persist SUTRA PullRequest
        pr_svc = PullRequestService(self.db, provider=self.provider)
        pr = pr_svc.create_pull_request(
            repository_id=repository.id,
            author_id=actor.id,
            source_change_id=change.id,
            title=pr_title,
            target_branch=base_branch,
            description=full_body,
            is_draft=is_draft,
        )

        # Link Task -> PR
        task.resulting_pull_request_id = pr.id
        task.updated_at = datetime.now(timezone.utc)

        # Update change metadata with PR information
        meta["pull_request_id"] = pr.id
        meta["pull_request_title"] = pr.title
        meta["pull_request_status"] = pr.status
        meta["target_branch"] = base_branch
        meta["head_branch"] = head_branch
        if gh_pr_number is not None:
            meta["github_pr_number"] = gh_pr_number
        if gh_pr_url is not None:
            meta["github_pr_url"] = gh_pr_url
        change.metadata_json = json.dumps(meta, sort_keys=True)
        change.updated_at = datetime.now(timezone.utc)

        # Audit event on task
        task_event = TaskEvent(
            id=str(uuid4()),
            task_id=task.id,
            actor_id=actor.id,
            session_id=session.id,
            event_type="task.pull_request_created",
            from_status=task.status,
            to_status=task.status,
            metadata_json=json.dumps({
                "task_id": task.id,
                "change_id": change.id,
                "pull_request_id": pr.id,
                "github_pr_number": gh_pr_number,
                "github_pr_url": gh_pr_url,
            }),
            created_at=datetime.now(timezone.utc),
        )
        self.db.add(task_event)
        self.db.flush()

        return pr
