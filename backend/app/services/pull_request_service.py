from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import subprocess
from typing import Optional
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.actor import Actor
from app.models.agent import Agent
from app.models.change import Change
from app.models.change_event import ChangeEvent
from app.models.change_file import ChangeFile
from app.models.change_review import ChangeReview
from app.models.ci_job import CIJob
from app.models.pull_request import PullRequest
from app.models.repository import Repository
from app.models.task import Task
from app.models.user import User
from app.providers.base import RepositoryProvider
from app.services.authorization_service import AuthorizationService
from app.services.branch_protection_service import BranchProtectionService
from app.services.change_policy_service import ChangePolicyService
from app.services.conflict_service import ConflictResult, ConflictService
from app.services.git_merge_service import GitMergeService
from app.services.notification_service import NotificationService


@dataclass
class PRMergeResult:
    status: str
    detail: str
    pull_request: PullRequest
    merge_commit_sha: Optional[str] = None
    merged_at: Optional[datetime] = None


class PullRequestService:
    """
    Authoritative service for PullRequest lifecycle and orchestration.

    Architecture Rule:
      PullRequest is a management/orchestration abstraction.
      Existing systems remain authoritative:
        - Change -> code-operation truth
        - ChangeReview -> review truth
        - ChangePolicyService -> policy truth
        - ConflictService -> conflict truth
        - AuthorizationService -> authorization truth
        - PostgreSQL UNIQUE(source_change_id) -> race boundary
    """

    STATUS_DRAFT = PullRequest.STATUS_DRAFT
    STATUS_OPEN = PullRequest.STATUS_OPEN
    STATUS_APPROVED = PullRequest.STATUS_APPROVED
    STATUS_MERGED = PullRequest.STATUS_MERGED
    STATUS_CLOSED = PullRequest.STATUS_CLOSED
    STATUS_REJECTED = PullRequest.STATUS_REJECTED

    VALID_STATUSES = {
        STATUS_DRAFT,
        STATUS_OPEN,
        STATUS_APPROVED,
        STATUS_MERGED,
        STATUS_CLOSED,
        STATUS_REJECTED,
    }

    TERMINAL_STATUSES = {
        STATUS_MERGED,
        STATUS_CLOSED,
    }

    VALID_TRANSITIONS = {
        STATUS_DRAFT: {STATUS_OPEN, STATUS_CLOSED},
        STATUS_OPEN: {STATUS_APPROVED, STATUS_REJECTED, STATUS_CLOSED},
        STATUS_APPROVED: {STATUS_MERGED, STATUS_REJECTED, STATUS_CLOSED},
        STATUS_REJECTED: {STATUS_OPEN},
        STATUS_MERGED: set(),
        STATUS_CLOSED: set(),
    }

    def __init__(self, db: Session, provider: Optional[RepositoryProvider] = None):
        self.db = db
        self.provider = provider

    def _get_provider(self, repository: Repository) -> Optional[RepositoryProvider]:
        if self.provider is not None:
            return self.provider
        if repository.provider_type == "github" and repository.provider_owner:
            if settings.github_app_id and settings.github_private_key_pem:
                try:
                    from app.providers.github.auth import GitHubAppAuthService
                    from app.providers.github.repository import GitHubRepositoryProvider
                    auth_service = GitHubAppAuthService(
                        app_id=settings.github_app_id,
                        private_key_pem=settings.github_private_key_pem,
                        base_url=settings.github_api_base_url,
                    )
                    return GitHubRepositoryProvider(
                        auth_service=auth_service,
                        base_url=settings.github_api_base_url,
                    )
                except Exception:
                    return None
        return None

    def sync_change_files_from_provider(
        self,
        repository: Repository,
        change: Change,
    ) -> list[ChangeFile]:
        """
        Synchronize ChangeFile records from the repository provider (e.g. GitHub)
        using git compare between base_commit and resulting_commit.
        """
        if not change.base_commit or not change.resulting_commit:
            return []

        provider = self._get_provider(repository)
        if not provider:
            return []

        try:
            owner = repository.provider_owner or repository.name
            name = repository.name
            stats = provider.get_diff_stats(
                owner=owner,
                name=name,
                base=change.base_commit,
                head=change.resulting_commit,
            )
            if not stats or not stats.changed_files:
                return []

            # Remove existing files for this change
            existing_files = self.db.scalars(
                select(ChangeFile).where(ChangeFile.change_id == change.id)
            ).all()
            for ef in existing_files:
                self.db.delete(ef)

            new_change_files = []
            for cf_data in stats.changed_files:
                filename = cf_data.get("filename")
                if not filename:
                    continue
                cfile = ChangeFile(
                    change_id=change.id,
                    path=filename,
                    operation=cf_data.get("status") or "modified",
                    additions=int(cf_data.get("additions", 0)),
                    deletions=int(cf_data.get("deletions", 0)),
                )
                self.db.add(cfile)
                new_change_files.append(cfile)

            self.db.flush()
            return new_change_files
        except Exception:
            return []

    # ---------------------------------------------------------
    # AUTHORIZATION HELPERS
    # ---------------------------------------------------------

    def _authorize_user_repo_access(
        self,
        user_id: str,
        repository: Repository,
    ) -> None:
        """Verify human user owns or has access to repository."""
        if repository.visibility == "private" and repository.owner_id != user_id:
            raise PermissionError("Repository access denied")

    def _record_event(
        self,
        pr: PullRequest,
        event_type: str,
        from_status: str | None,
        to_status: str | None,
        actor_id: str | None = None,
        reason: str | None = None,
        metadata: dict | None = None,
    ) -> ChangeEvent:
        safe_meta = {
            "pull_request_id": pr.id,
            "repository_id": pr.repository_id,
            "author_id": pr.author_id,
            "title": pr.title,
            "target_branch": pr.target_branch,
        }
        if metadata:
            for k, v in metadata.items():
                if k.lower() not in {"token", "jwt", "password", "secret", "authorization"}:
                    safe_meta[k] = v

        event = ChangeEvent(
            change_id=pr.source_change_id,
            actor_id=actor_id or pr.author_id,
            event_type=event_type,
            from_status=from_status,
            to_status=to_status,
            reason=reason,
            metadata_json=json.dumps(
                safe_meta,
                separators=(",", ":"),
                sort_keys=True,
            ),
        )
        self.db.add(event)
        return event

    def transition_pull_request(
        self,
        pr: PullRequest,
        new_status: str,
        actor_id: str | None = None,
        reason: str | None = None,
        metadata: dict | None = None,
    ) -> PullRequest:
        if new_status not in self.VALID_STATUSES:
            raise ValueError(f"Invalid status '{new_status}'")

        allowed = self.VALID_TRANSITIONS.get(pr.status, set())
        if new_status not in allowed:
            raise ValueError(
                f"Cannot transition PullRequest from '{pr.status}' to '{new_status}'"
            )

        old_status = pr.status
        now = datetime.now(timezone.utc)
        pr.status = new_status
        pr.updated_at = now

        if new_status == self.STATUS_MERGED:
            pr.merged_at = now
        elif new_status in {self.STATUS_CLOSED, self.STATUS_REJECTED}:
            pr.closed_at = now

        if new_status == self.STATUS_OPEN:
            event_type = "pull_request.opened"
        elif new_status == self.STATUS_APPROVED:
            event_type = "pull_request.approved"
        elif new_status == self.STATUS_REJECTED:
            event_type = "pull_request.rejected"
        elif new_status == self.STATUS_CLOSED:
            event_type = "pull_request.closed"
        elif new_status == self.STATUS_MERGED:
            event_type = "pull_request.merged"
        else:
            event_type = f"pull_request.{new_status}"

        self._record_event(
            pr=pr,
            event_type=event_type,
            from_status=old_status,
            to_status=new_status,
            actor_id=actor_id,
            reason=reason,
            metadata=metadata,
        )

        self.db.flush()
        return pr

    # ---------------------------------------------------------
    # PR CREATION
    # ---------------------------------------------------------

    def create_pull_request(
        self,
        repository_id: str,
        author_id: str,
        source_change_id: str,
        title: str,
        target_branch: str,
        description: str | None = None,
        is_draft: bool = False,
    ) -> PullRequest:
        if not title or not title.strip():
            raise ValueError("title cannot be empty")

        if not target_branch or not target_branch.strip():
            raise ValueError("Target branch cannot be empty")

        if target_branch.startswith("-") or ".." in target_branch:
            raise ValueError(
                f"Invalid target branch '{target_branch}'"
            )

        # 1. Validate repository first.
        repository = self.db.scalar(
            select(Repository).where(
                Repository.id == repository_id,
                Repository.deleted_at.is_(None),
            )
        )

        if repository is None:
            raise ValueError("Repository not found")

        # 2. Validate the source Change BEFORE author authorization.
        # This preserves the repository/change invariant and gives the
        # caller the correct validation error when they don't match.
        change = self.db.scalar(
            select(Change).where(
                Change.id == source_change_id
            )
        )

        if change is None:
            raise ValueError("Source Change not found")

        if change.repository_id != repository_id:
            raise ValueError(
                "Change does not belong to target repository"
            )

        # 3. Validate the author.
        author = self.db.scalar(
            select(Actor).where(
                Actor.id == author_id
            )
        )

        if author is None:
            raise ValueError("Author user not found")

        # 4. Human/user authors use repository ownership/access.
        # Agent authors use the centralized agent authorization service.
        if getattr(author, "type", None) in {
            "human",
            "user",
        }:
            self._authorize_user_repo_access(
                author_id,
                repository,
            )
        else:
            AuthorizationService.require(
                actor=author,
                repository=repository,
                capability=AuthorizationService.WRITE,
                db=self.db,
            )

        # 5. Evaluate change policy.
        policy = ChangePolicyService(
            self.db
        ).evaluate(change)

        if policy.decision == ChangePolicyService.BLOCK:
            raise ValueError(
                f"Blocked changes cannot enter pull request: "
                f"{policy.reason}"
            )

        repo_policies = (repository.settings or {}).get("policies", {})
        effective_rule = BranchProtectionService(self.db).get_effective_rule(
            repository_id, target_branch.strip()
        )

        # Policy Gate: Require Task Linkage
        if repo_policies.get("require_task_linkage"):
            is_agent = getattr(author, "type", None) == "agent"
            task_for_change = self.db.scalar(
                select(Task).where(Task.resulting_change_id == source_change_id)
            )
            c_meta = {}
            if change.metadata_json:
                try:
                    c_meta = json.loads(change.metadata_json)
                except Exception:
                    pass
            task_id_in_meta = c_meta.get("task_id")
            if not task_for_change and not task_id_in_meta:
                if is_agent or repo_policies.get("require_task_linkage_for_all", True):
                    raise ValueError(
                        "Policy violation: Pull request must be linked to an active SUTRA Task."
                    )

        # Policy Gate: Enforce Governed Provenance
        if repo_policies.get("enforce_governed_provenance"):
            c_meta = {}
            if change.metadata_json:
                try:
                    c_meta = json.loads(change.metadata_json)
                except Exception:
                    pass
            if c_meta.get("commit_origin") == "external_unverified":
                raise ValueError(
                    "Policy violation: Unverified external commits are rejected by repository policy."
                )

        # Policy Gate: Require Clean Conflict on PR Creation
        if repo_policies.get("require_clean_conflict") or (
            effective_rule and effective_rule.require_clean_conflict
        ):
            conflict = ConflictService(self.db).analyze(change)
            if conflict.level == ConflictService.LEVEL_CONFLICT:
                raise ValueError(
                    f"Policy violation: Cannot open PR because Git detected a merge conflict with '{target_branch.strip()}'."
                )

        # 5. Idempotency & Race-safe PR creation using PostgreSQL UNIQUE constraint
        existing = self.db.scalar(
            select(PullRequest).where(
                PullRequest.source_change_id == source_change_id
            )
        )
        if existing is not None:
            return existing

        initial_status = (
            self.STATUS_DRAFT if is_draft else self.STATUS_OPEN
        )

        pr = PullRequest(
            repository_id=repository_id,
            author_id=author_id,
            source_change_id=source_change_id,
            title=title.strip(),
            description=description,
            target_branch=target_branch.strip(),
            source_commit=change.resulting_commit,
            status=initial_status,
        )

        savepoint = self.db.begin_nested()
        try:
            self.db.add(pr)
            self.db.flush()

            self._record_event(
                pr=pr,
                event_type="pull_request.created",
                from_status=None,
                to_status=initial_status,
                actor_id=author_id,
            )

            if initial_status == self.STATUS_OPEN:
                self._record_event(
                    pr=pr,
                    event_type="pull_request.opened",
                    from_status=None,
                    to_status=self.STATUS_OPEN,
                    actor_id=author_id,
                )
                
                NotificationService.create_notification(
                    db=self.db,
                    user_id=repository.owner_id,
                    title=f"PR opened: {pr.title}",
                    message=f"Pull request #{pr.id[:8]} was opened by {author.name}.",
                    type="pr",
                    link=f"/repositories/{repository.slug}/pull-requests/{pr.id}",
                    commit=False
                )

                # When the author is an agent, enter the human review workflow
                # by requesting a review from the repository maintainers / owner.
                if getattr(author, "type", None) == "agent":
                    existing_pending_review = self.db.scalar(
                        select(ChangeReview).where(
                            ChangeReview.change_id == source_change_id,
                            ChangeReview.status == "pending",
                        )
                    )
                    if existing_pending_review is None:
                        agent_review_req = ChangeReview(
                            change_id=source_change_id,
                            requested_by=repository.owner_id,
                            status="pending",
                            reason=f"Agent PR #{pr.id[:8]} submitted for human review",
                        )
                        self.db.add(agent_review_req)
                        self.db.flush()

                        self._record_event(
                            pr=pr,
                            event_type="pull_request.review_requested",
                            from_status=None,
                            to_status=None,
                            actor_id=author_id,
                            reason=agent_review_req.reason,
                            metadata={
                                "review_id": agent_review_req.id,
                                "requested_by": repository.owner_id,
                            },
                        )

                # Automatic CI dispatch upon opening an eligible Pull Request
                if change and change.resulting_commit and repository.provider_type != "github":
                    try:
                        from app.services.ci_service import CIService
                        ci_svc = CIService(self.db)
                        ci_svc.create_job(
                            pull_request_id=pr.id,
                            actor_id=author_id,
                            trigger="pull_request",
                        )
                    except Exception:
                        pass
            now = datetime.now(timezone.utc)
            # Link Task -> PR if Change belongs to a Task
            task = self.db.scalar(
                select(Task).where(Task.resulting_change_id == source_change_id)
            )
            if task is not None:
                task.resulting_pull_request_id = pr.id
                task.updated_at = now

            # Sync PR info and GitHub substrate into change metadata
            if change:
                try:
                    meta = json.loads(change.metadata_json or "{}")
                except Exception:
                    meta = {}
                meta["pull_request_id"] = pr.id
                meta["pull_request_title"] = pr.title
                meta["pull_request_status"] = pr.status
                meta["target_branch"] = pr.target_branch

                provider = self._get_provider(repository)
                if provider is not None and repository.provider_owner and "github_pr_number" not in meta:
                    head_branch = meta.get("branch") or meta.get("head_branch")
                    if head_branch:
                        try:
                            gh_head = provider.get_branch(
                                owner=repository.provider_owner,
                                name=repository.name,
                                branch=head_branch,
                            )
                            if gh_head:
                                gh_pr = provider.create_pull_request(
                                    owner=repository.provider_owner,
                                    name=repository.name,
                                    title=pr.title,
                                    body=pr.description or "",
                                    head_branch=head_branch,
                                    base_branch=pr.target_branch,
                                )
                                meta["github_pr_number"] = gh_pr.number
                                meta["github_pr_url"] = gh_pr.html_url
                        except Exception:
                            pass

                change.metadata_json = json.dumps(meta, sort_keys=True)
                change.updated_at = now

            self.db.flush()
            savepoint.commit()
            return pr
        except IntegrityError:
            savepoint.rollback()
            existing_pr = self.db.scalar(
                select(PullRequest).where(
                    PullRequest.source_change_id == source_change_id
                )
            )
            if existing_pr is not None:
                return existing_pr
            raise

    def upsert_github_pull_request(
        self,
        *,
        repository: Repository,
        pr_number: int,
        title: str,
        target_branch: str,
        head_branch: Optional[str] = None,
        head_sha: Optional[str] = None,
        base_sha: Optional[str] = None,
        description: Optional[str] = None,
        html_url: Optional[str] = None,
        author_login: Optional[str] = None,
        is_merged: bool = False,
        is_closed: bool = False,
        action: Optional[str] = None,
    ) -> PullRequest:
        """
        Idempotently synchronize or ingest a GitHub-created Pull Request into SUTRA.
        Preserves existing agent provenance if the PR already has an associated SUTRA Agent/Task.
        If a new PR record is created for an external GitHub PR, it is backed by an external tracking Change.
        """
        now = datetime.now(timezone.utc)

        # 1. Locate existing PR by repository + github_pr_number in Change metadata
        pr = self.db.scalar(
            select(PullRequest)
            .join(Change, PullRequest.source_change_id == Change.id)
            .where(
                PullRequest.repository_id == repository.id,
                Change.metadata_json.contains(f'"github_pr_number": {pr_number}'),
            )
        )
        if not pr and head_branch:
            pr = self.db.scalar(
                select(PullRequest)
                .join(Change, PullRequest.source_change_id == Change.id)
                .where(
                    PullRequest.repository_id == repository.id,
                    Change.metadata_json.contains(f'"branch": "{head_branch}"'),
                )
            )

        if pr is not None:
            change = self.db.scalar(select(Change).where(Change.id == pr.source_change_id))
            meta = {}
            if change and change.metadata_json:
                try:
                    meta = json.loads(change.metadata_json)
                except Exception:
                    pass

            meta["github_pr_number"] = pr_number
            if html_url:
                meta["github_pr_url"] = html_url
            if head_branch:
                meta["branch"] = head_branch

            old_head = pr.source_commit
            # Handle action / synchronization
            if action == "synchronize" or (head_sha and head_sha != pr.source_commit):
                if head_sha and head_sha != old_head:
                    is_governed = meta.get("commit_origin") == "sutra_governed"
                    was_approved = (pr.status == PullRequest.STATUS_APPROVED) or bool(meta.get("approved_head_sha"))

                    if is_governed and change and change.resulting_commit and change.resulting_commit != head_sha:
                        logger.warning(
                            f"External push detected on SUTRA-governed branch for PR {pr.id[:8]}, "
                            f"new SHA {head_sha[:8]} != governed SHA {change.resulting_commit[:8]}. "
                            "Governed Change resulting_commit preserved; PR source_commit updated to trigger governance mismatch."
                        )
                        pr.source_commit = head_sha
                        meta["approved_head_sha"] = None
                        if pr.status == PullRequest.STATUS_APPROVED:
                            pr.status = PullRequest.STATUS_OPEN
                    else:
                        pr.source_commit = head_sha
                        if change:
                            change.resulting_commit = head_sha
                            meta["approved_head_sha"] = None
                            if pr.status == PullRequest.STATUS_APPROVED:
                                pr.status = PullRequest.STATUS_OPEN

                    if was_approved:
                        if change:
                            stale_reviews = self.db.scalars(
                                select(ChangeReview).where(
                                    ChangeReview.change_id == change.id,
                                    ChangeReview.status == "approved",
                                )
                            ).all()
                            for sr in stale_reviews:
                                sr.status = "stale"

                        self._record_event(
                            pr=pr,
                            event_type="approval.invalidated",
                            from_status=PullRequest.STATUS_APPROVED,
                            to_status=PullRequest.STATUS_OPEN,
                            actor_id=pr.author_id,
                            reason="New commit pushed to branch; approval invalidated and fresh review required.",
                            metadata={"old_head_sha": old_head, "new_head_sha": head_sha},
                        )

                        try:
                            from app.services.governance_service import GovernanceService
                            gov_svc = GovernanceService(self.db, provider=self._get_provider(repository))
                            gov_svc.sync_governance_check_to_github(pr.id)
                        except Exception as e:
                            logger.warning(f"Could not sync governance check run after approval invalidation: {e}")

            if is_merged:
                pr.status = PullRequest.STATUS_MERGED
                pr.merged_at = pr.merged_at or now
                if base_sha:
                    pr.target_commit = base_sha
                if change:
                    change.status = "recorded"
                    meta["merged"] = True
            elif is_closed:
                pr.status = PullRequest.STATUS_CLOSED
                pr.closed_at = pr.closed_at or now
            elif action == "reopened":
                pr.status = PullRequest.STATUS_OPEN
                pr.closed_at = None

            pr.title = title or pr.title
            if description is not None:
                pr.description = description
            pr.target_branch = target_branch or pr.target_branch
            pr.updated_at = now

            if change:
                change.metadata_json = json.dumps(meta, sort_keys=True)
                change.updated_at = now
                if head_sha and head_sha != old_head:
                    self.sync_change_files_from_provider(repository, change)

            self.db.flush()
            return pr

        # 2. PR does not exist yet: create external tracking Change + PullRequest
        # Ensure owner actor exists
        owner_actor = self.db.scalar(select(Actor).where(Actor.id == repository.owner_id))
        if not owner_actor:
            owner_actor = Actor(
                id=repository.owner_id,
                owner_id=repository.owner_id,
                type="human",
                name=repository.provider_owner or "Repository Owner",
                capabilities="[]",
            )
            self.db.add(owner_actor)
            self.db.flush()

        change_meta = {
            "source": "github",
            "source_type": "github",
            "github_pr_number": pr_number,
            "github_pr_url": html_url or f"https://github.com/{repository.provider_owner or 'owner'}/{repository.name}/pull/{pr_number}",
            "branch": head_branch,
            "base_branch": target_branch,
            "github_author_login": author_login,
        }

        initial_status = PullRequest.STATUS_OPEN
        if is_merged:
            initial_status = PullRequest.STATUS_MERGED
        elif is_closed:
            initial_status = PullRequest.STATUS_CLOSED

        change = Change(
            id=str(uuid4()),
            repository_id=repository.id,
            actor_id=owner_actor.id,
            intent=f"GitHub PR #{pr_number}: {title}",
            base_commit=base_sha,
            resulting_commit=head_sha,
            operation_key=f"github-pr-{repository.id}-{pr_number}-{uuid4().hex[:12]}",
            status="recorded" if is_merged else "proposed",
            risk_level="low",
            metadata_json=json.dumps(change_meta, sort_keys=True),
        )
        self.db.add(change)
        self.db.flush()

        # Synchronize diff stats and changed files from GitHub
        if base_sha and head_sha:
            self.sync_change_files_from_provider(repository, change)

        pr = PullRequest(
            id=str(uuid4()),
            repository_id=repository.id,
            author_id=owner_actor.id,
            source_change_id=change.id,
            title=title.strip() if title else f"GitHub PR #{pr_number}",
            description=description,
            target_branch=target_branch.strip() if target_branch else (repository.default_branch or "main"),
            source_commit=head_sha,
            target_commit=base_sha if is_merged else None,
            status=initial_status,
            merged_at=now if is_merged else None,
            closed_at=now if is_closed else None,
            created_at=now,
            updated_at=now,
        )
        self.db.add(pr)
        self.db.flush()

        self._record_event(
            pr=pr,
            event_type="pull_request.opened" if not is_merged else "pull_request.merged",
            from_status=None,
            to_status=initial_status,
            actor_id=owner_actor.id,
            reason="Synchronized from GitHub",
        )

        return pr

    # ---------------------------------------------------------
    # PR READ / LIST
    # ---------------------------------------------------------

    def get_pull_request(
        self,
        pr_id: str,
        user_id: str,
    ) -> PullRequest | None:
        pr = self.db.scalar(
            select(PullRequest).where(PullRequest.id == pr_id)
        )
        if pr is None:
            return None

        repository = self.db.scalar(
            select(Repository).where(
                Repository.id == pr.repository_id,
                Repository.deleted_at.is_(None),
            )
        )
        if repository is None or (repository.visibility == "private" and repository.owner_id != user_id):
            # Hide private repo resource existence
            return None

        return pr

    def list_pull_requests(
        self,
        repository_id: str,
        user_id: str,
        status: str | None = None,
        target_branch: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[PullRequest]:
        repository = self.db.scalar(
            select(Repository).where(
                Repository.id == repository_id,
                Repository.deleted_at.is_(None),
            )
        )
        if repository is None:
            raise ValueError("Repository not found")

        self._authorize_user_repo_access(user_id, repository)

        stmt = select(PullRequest).where(
            PullRequest.repository_id == repository_id
        )

        if status:
            stmt = stmt.where(PullRequest.status == status)

        if target_branch:
            stmt = stmt.where(PullRequest.target_branch == target_branch)

        stmt = stmt.order_by(PullRequest.created_at.desc()).offset(offset).limit(limit)

        return list(self.db.scalars(stmt).all())

    def list_all_pull_requests(
        self,
        user_id: str,
        status: str | None = None,
        target_branch: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[PullRequest]:
        stmt = (
            select(PullRequest)
            .join(Repository, PullRequest.repository_id == Repository.id)
            .where(
                Repository.owner_id == user_id,
                Repository.deleted_at.is_(None),
            )
        )

        if status:
            stmt = stmt.where(PullRequest.status == status)

        if target_branch:
            stmt = stmt.where(PullRequest.target_branch == target_branch)

        stmt = stmt.order_by(PullRequest.created_at.desc()).offset(offset).limit(limit)

        return list(self.db.scalars(stmt).all())

    def get_pull_request_change(
        self,
        pr_id: str,
        user_id: str,
    ) -> tuple[PullRequest, Change] | None:
        pr = self.get_pull_request(pr_id, user_id)
        if pr is None:
            return None

        change = self.db.scalar(
            select(Change).where(Change.id == pr.source_change_id)
        )
        if change is None:
            return None

        if change.repository_id != pr.repository_id:
            return None

        return pr, change

    def get_pull_request_reviews(
        self,
        pr_id: str,
        user_id: str,
    ) -> tuple[PullRequest, list[ChangeReview]] | None:
        pr = self.get_pull_request(pr_id, user_id)
        if pr is None:
            return None

        reviews = list(
            self.db.scalars(
                select(ChangeReview)
                .where(ChangeReview.change_id == pr.source_change_id)
                .order_by(ChangeReview.created_at.desc())
            ).all()
        )

        return pr, reviews

    def get_pull_request_conflicts(
        self,
        pr_id: str,
        user_id: str,
    ) -> tuple[PullRequest, ConflictResult] | None:
        pr = self.get_pull_request(pr_id, user_id)
        if pr is None:
            return None

        change = self.db.scalar(
            select(Change).where(Change.id == pr.source_change_id)
        )
        if change is None:
            return None

        if change.repository_id != pr.repository_id:
            return None

        conflict_result = ConflictService(self.db).analyze(change)
        return pr, conflict_result

    # ---------------------------------------------------------
    # PR REVIEW INTEGRATION (Reuses ChangeReview & ChangePolicyService)
    # ---------------------------------------------------------

    def create_pull_request_review_request(
        self,
        pr: PullRequest,
        requester_id: str,
        reason: str | None = None,
    ) -> ChangeReview:
        repository = self.db.scalar(
            select(Repository).where(
                Repository.id == pr.repository_id,
                Repository.deleted_at.is_(None),
            )
        )
        if repository is None:
            raise ValueError("Repository not found")

        self._authorize_user_repo_access(requester_id, repository)

        change = self.db.scalar(
            select(Change).where(Change.id == pr.source_change_id)
        )
        if change is None:
            raise ValueError("Source Change not found")

        policy = ChangePolicyService(self.db).evaluate(change)
        if policy.decision == ChangePolicyService.BLOCK:
            raise ValueError(f"Blocked changes cannot enter review: {policy.reason}")

        existing_pending = self.db.scalar(
            select(ChangeReview).where(
                ChangeReview.change_id == change.id,
                ChangeReview.status == "pending",
            )
        )
        if existing_pending is not None:
            raise ValueError("A pending review already exists for this change")

        review = ChangeReview(
            change_id=change.id,
            requested_by=requester_id,
            status="pending",
            reason=reason,
        )

        self.db.add(review)
        self.db.flush()

        from app.services.change_service import ChangeService
        ChangeService(self.db).transition_change(
            change=change,
            new_status=change.status,
            actor_id=requester_id,
            event_type="change.review_requested",
            reason=reason,
            metadata={
                "review_id": review.id,
                "requested_by": requester_id,
            },
        )

        return review

    def approve_pull_request(
        self,
        pr: PullRequest,
        approver_id: str,
        reason: str | None = None,
        review_id: str | None = None,
    ) -> PullRequest:
        if pr.status not in {self.STATUS_OPEN, self.STATUS_APPROVED}:
            raise ValueError(f"Cannot approve PullRequest in status '{pr.status}'")

        repository = self.db.scalar(
            select(Repository).where(
                Repository.id == pr.repository_id,
                Repository.deleted_at.is_(None),
            )
        )
        if repository is None:
            raise ValueError("Repository not found")

        change = self.db.scalar(
            select(Change).where(Change.id == pr.source_change_id)
        )
        if change is None:
            raise ValueError("Source Change not found")

        # Self-approval prohibition
        if pr.author_id == approver_id or change.actor_id == approver_id:
            raise ValueError("Self-review approval is strictly prohibited: A reviewer cannot approve their own review request")

        # Ensure approver is a human user, not an agent
        approver_actor = self.db.scalar(select(Actor).where(Actor.id == approver_id))
        if approver_actor and approver_actor.type == "agent":
            raise ValueError("Agents cannot approve pull requests: only human reviewers may approve")
        approver_agent = self.db.scalar(select(Agent).where(Agent.id == approver_id))
        if approver_agent:
            raise ValueError("Agents cannot approve pull requests: only human reviewers may approve")

        # Evaluate policy
        policy_decision = ChangePolicyService(self.db).evaluate(change)
        if policy_decision.decision == ChangePolicyService.BLOCK:
            raise ValueError(f"Change is currently blocked by policy: {policy_decision.reason}")

        # Evaluate governance precondition
        from app.services.governance_service import GovernanceService, GovernanceVerdict
        provider = self._get_provider(repository)
        gov_svc = GovernanceService(self.db, provider=provider)
        gov_eval = gov_svc.evaluate_pull_request(pr.id, record_audit=False)
        if gov_eval["verdict"] in (GovernanceVerdict.BLOCKED, GovernanceVerdict.CI_FAILED):
            failing_reasons = [f for f in gov_eval.get("failed", []) if "CI" in f or "failed" in f.lower() or "blocked" in f.lower()]
            raise ValueError(f"Cannot approve PullRequest: Governance evaluation is blocked ({'; '.join(failing_reasons) if failing_reasons else gov_eval['verdict']})")
        elif gov_eval["verdict"] == GovernanceVerdict.CI_PENDING:
            raise ValueError("Cannot approve PullRequest: Automated CI checks are still running or pending")
        elif gov_eval["verdict"] == GovernanceVerdict.POLICY_FAILED:
            raise ValueError(f"Cannot approve PullRequest: Change policy violation: {'; '.join(gov_eval.get('failed', []))}")

        # Resolve authoritative ChangeReview
        if review_id:
            review = self.db.scalar(
                select(ChangeReview).where(
                    ChangeReview.id == review_id,
                    ChangeReview.change_id == change.id,
                )
            )
        else:
            # Find a pending review or review by this approver
            review = self.db.scalar(
                select(ChangeReview)
                .where(
                    ChangeReview.change_id == change.id,
                    (ChangeReview.status == "pending") | (ChangeReview.reviewer_id == approver_id),
                )
                .order_by(ChangeReview.created_at.desc())
            )
            if review is None:
                # Find latest review for source change
                review = self.db.scalar(
                    select(ChangeReview)
                    .where(ChangeReview.change_id == change.id)
                    .order_by(ChangeReview.created_at.desc())
                )

        if review is None:
            raise ValueError("An approved ChangeReview is required before PR approval")

        if review.requested_by == approver_id:
            # If the source change and PR are authored by a human and that human requested the review,
            # they cannot approve their own review request.
            if pr.author_id == approver_id or change.actor_id == approver_id:
                raise ValueError("Self-review approval is strictly prohibited: A reviewer cannot approve their own review request")

        if review.status == "rejected":
            raise ValueError("Cannot approve PullRequest: ChangeReview has been rejected")

        now = datetime.now(timezone.utc)
        head_sha = pr.source_commit or change.resulting_commit

        if review.status == "pending":
            review.status = "approved"
            review.reviewer_id = approver_id
            review.reason = reason or review.reason
            review.reviewed_at = now

            from app.services.change_service import ChangeService
            ChangeService(self.db).transition_change(
                change=change,
                new_status=change.status,
                actor_id=approver_id,
                event_type="change.review_approved",
                reason=reason,
                metadata={
                    "review_id": review.id,
                    "reviewer_id": approver_id,
                    "reason": reason,
                    "head_sha": head_sha,
                },
            )
            self.db.flush()

            if change.status == "proposed":
                ChangeService(self.db).finalize_change(change)
                self.db.flush()

        elif review.status == "approved":
            if review.reviewer_id == approver_id:
                # Idempotent re-approval by the same reviewer
                pass
            elif review.reviewer_id == pr.author_id or review.reviewer_id == change.actor_id:
                raise ValueError("Self-review approval is strictly prohibited")
            else:
                # Additional distinct human reviewer approval on multi-reviewer PR
                new_review = ChangeReview(
                    id=str(uuid4()),
                    change_id=change.id,
                    requested_by=review.requested_by,
                    reviewer_id=approver_id,
                    status="approved",
                    reason=reason or "Approved by additional human reviewer",
                    reviewed_at=now,
                )
                self.db.add(new_review)
                self.db.flush()
                review = new_review

        # Track reviewed commit SHA in change metadata
        change_meta = {}
        if change.metadata_json:
            try:
                change_meta = json.loads(change.metadata_json)
            except Exception:
                pass
        change_meta["approved_head_sha"] = head_sha
        reviewed_head_shas = change_meta.get("reviewed_head_shas", {})
        if review:
            reviewed_head_shas[review.id] = head_sha
        change_meta["reviewed_head_shas"] = reviewed_head_shas
        change.metadata_json = json.dumps(change_meta)
        self.db.flush()

        # Count total valid approvals against required approvals
        rule = BranchProtectionService(self.db).get_effective_rule(pr.repository_id, pr.target_branch)
        required_approvals = rule.required_approvals if rule else 1
        all_approved = self.db.scalars(
            select(ChangeReview).where(
                ChangeReview.change_id == change.id,
                ChangeReview.status == "approved",
                ChangeReview.reviewer_id != pr.author_id,
                ChangeReview.reviewer_id != change.actor_id,
            )
        ).all()
        unique_reviewers = {r.reviewer_id for r in all_approved if r.reviewer_id}
        actual_approvals = len(unique_reviewers)

        # Transition PR to approved if required approvals are satisfied
        if actual_approvals >= required_approvals:
            if pr.status != self.STATUS_APPROVED:
                pr = self.transition_pull_request(
                    pr,
                    self.STATUS_APPROVED,
                    actor_id=approver_id,
                    reason=reason,
                    metadata={
                        "review_id": review.id if review else None,
                        "reviewer_id": approver_id,
                        "head_sha": head_sha,
                        "required_approvals": required_approvals,
                        "actual_approvals": actual_approvals,
                    },
                )
        else:
            self._record_event(
                pr=pr,
                event_type="pull_request.review_approved",
                from_status=pr.status,
                to_status=pr.status,
                actor_id=approver_id,
                reason=reason,
                metadata={
                    "review_id": review.id if review else None,
                    "reviewer_id": approver_id,
                    "head_sha": head_sha,
                    "required_approvals": required_approvals,
                    "actual_approvals": actual_approvals,
                },
            )

        return pr

    # ---------------------------------------------------------
    # PR MERGE (Guarded Orchestration Boundary)
    # ---------------------------------------------------------

    def merge_pull_request(
        self,
        pr_or_id: PullRequest | str,
        merger_id: str,
    ) -> PRMergeResult | None:
        pr_id = pr_or_id.id if isinstance(pr_or_id, PullRequest) else pr_or_id

        # 1. Row locking for PostgreSQL concurrency protection
        pr = self.db.scalar(
            select(PullRequest)
            .where(PullRequest.id == pr_id)
            .with_for_update()
        )
        if pr is None:
            return None

        # 2. Repository resolution
        repository = self.db.scalar(
            select(Repository).where(
                Repository.id == pr.repository_id,
                Repository.deleted_at.is_(None),
            )
        )
        if repository is None:
            return None

        # 3. STRICT AGENT PROHIBITION: Agents cannot merge pull requests under any circumstances
        merger_actor = self.db.scalar(select(Actor).where(Actor.id == merger_id))
        if merger_actor and merger_actor.type == "agent":
            raise PermissionError("Agents are strictly prohibited from merging pull requests")
        merger_agent = self.db.scalar(select(Agent).where(Agent.id == merger_id))
        if merger_agent is not None:
            raise PermissionError("Agents are strictly prohibited from merging pull requests")

        # 4. Human Repository Authorization check
        self._authorize_user_repo_access(merger_id, repository)

        # 5. SUTRA Lifecycle check & Idempotency
        if pr.status == self.STATUS_MERGED:
            return PRMergeResult(
                status="merged",
                detail="PullRequest is already merged",
                pull_request=pr,
                merge_commit_sha=pr.target_commit,
                merged_at=pr.merged_at,
            )

        if pr.status == self.STATUS_CLOSED:
            raise ValueError(f"Cannot merge PullRequest in status '{pr.status}'")

        if pr.status not in {self.STATUS_OPEN, self.STATUS_APPROVED}:
            raise ValueError(f"Cannot merge PullRequest in status '{pr.status}'")

        # 6. Source Change resolution & cross-repository invariant
        change = self.db.scalar(
            select(Change).where(Change.id == pr.source_change_id)
        )
        if change is None:
            raise ValueError("Source Change not found")

        if change.repository_id != pr.repository_id:
            return None

        if not change.resulting_commit:
            raise ValueError("Source Change has no resulting commit; cannot merge")

        if not pr.target_branch:
            raise ValueError("Target branch is invalid")

        # Resolve change metadata
        change_meta = {}
        if change.metadata_json:
            try:
                change_meta = json.loads(change.metadata_json)
            except Exception:
                pass

        # 7. Substrate Provider Resolution
        provider = self._get_provider(repository)
        is_github = bool(
            repository.provider_type == "github"
            and repository.provider_owner
            and provider is not None
        )

        current_head = pr.source_commit or change.resulting_commit

        if is_github:
            gh_pr_number = change_meta.get("github_pr_number")
            if not gh_pr_number:
                raise ValueError("GitHub PR number could not be resolved for this pull request")

            # A. Live substrate state inspection
            gh_pr = provider.get_pull_request(
                owner=repository.provider_owner,
                name=repository.name,
                pr_number=gh_pr_number,
            )
            if gh_pr is None:
                raise ValueError(f"Pull request #{gh_pr_number} not found on GitHub substrate")

            # B. Substrate Idempotency Reconciler
            if gh_pr.is_merged:
                now = datetime.now(timezone.utc)
                pr.target_commit = gh_pr.base_sha or pr.target_commit or current_head
                pr.status = self.STATUS_MERGED
                pr.merged_at = pr.merged_at or now
                change.status = "recorded"
                change_meta["merged"] = True
                change_meta["merge_commit_sha"] = pr.target_commit
                change_meta["merged_at"] = pr.merged_at.isoformat()
                change_meta["merged_by"] = merger_id
                change.metadata_json = json.dumps(change_meta, sort_keys=True)

                linked_task = self.db.scalar(
                    select(Task).where(
                        (Task.resulting_pull_request_id == pr.id) |
                        (Task.resulting_change_id == change.id)
                    ).with_for_update()
                )
                if linked_task and linked_task.status != Task.STATUS_COMPLETED:
                    from app.services.task_service import TaskService
                    TaskService(self.db)._complete_locked_task(
                        linked_task,
                        actor_id=merger_id,
                    )
                self.db.flush()
                return PRMergeResult(
                    status="merged",
                    detail="PullRequest is already merged on GitHub substrate",
                    pull_request=pr,
                    merge_commit_sha=pr.target_commit,
                    merged_at=pr.merged_at,
                )

            # C. Substrate Mergeability Check
            if gh_pr.mergeable is False:
                raise ValueError("Merge rejected: GitHub reports pull request is not mergeable due to merge conflicts")

            # D. Substrate HEAD SHA Race Check (Part 1)
            substrate_head_sha = gh_pr.head_sha
            if pr.source_commit and pr.source_commit != substrate_head_sha:
                raise ValueError("Merge authorization invalidated: PR HEAD changed since governance evaluation.")
            if change.resulting_commit and change.resulting_commit != substrate_head_sha:
                raise ValueError("Merge authorization invalidated: PR HEAD changed since governance evaluation.")
            current_head = substrate_head_sha

        # 8. Authoritative Governance Precondition Gate
        from app.services.governance_service import GovernanceService, GovernanceVerdict
        gov_svc = GovernanceService(self.db, provider=provider)
        gov = gov_svc.evaluate_pull_request(pr.id)
        if gov["verdict"] != GovernanceVerdict.READY_FOR_MERGE:
            failed_reasons = gov.get("failed", [])
            fail_msg = failed_reasons[0] if failed_reasons else f"Pull request governance verdict is {gov['verdict']}; requires READY_FOR_MERGE"
            raise ValueError(f"Merge rejected by SUTRA governance: {fail_msg}")

        # 9. Verify Human Approval authorizes THIS HEAD
        approved_head_sha = change_meta.get("approved_head_sha")
        if approved_head_sha and current_head and approved_head_sha != current_head:
            raise ValueError("Merge authorization invalidated: PR HEAD changed since governance evaluation.")

        # 10. Execution Boundary
        if is_github:
            # Immediate pre-merge re-fetch to protect against race condition
            gh_pr_latest = provider.get_pull_request(
                owner=repository.provider_owner,
                name=repository.name,
                pr_number=gh_pr_number,
            )
            if not gh_pr_latest or gh_pr_latest.head_sha != current_head:
                raise ValueError("Merge authorization invalidated: PR HEAD changed since governance evaluation.")

            # Authoritative Substrate Merge Execution
            merge_res = provider.merge_pull_request(
                owner=repository.provider_owner,
                name=repository.name,
                pr_number=gh_pr_number,
                commit_title=f"Merge PR #{gh_pr_number}: {pr.title}",
                commit_message=f"{pr.title}\n\nApproved-by: Human {merger_id}\nReviewed-HEAD: {current_head}",
                expected_head_sha=current_head,
                method="merge",
            )
            if not merge_res.success:
                raise ValueError(f"GitHub substrate merge failed: {merge_res.message}")

            resulting_commit = merge_res.merge_commit_sha

            # Authoritative Post-Merge Verification
            verify_pr = provider.get_pull_request(
                owner=repository.provider_owner,
                name=repository.name,
                pr_number=gh_pr_number,
            )
            if verify_pr and not verify_pr.is_merged:
                raise ValueError("Post-merge substrate verification failed: GitHub reports PR is not merged")
            if not resulting_commit and verify_pr:
                resulting_commit = verify_pr.base_sha

        else:
            # Local repository fallback execution (for local workspace tests)
            policy = ChangePolicyService(self.db).evaluate(change)
            if policy.decision == ChangePolicyService.BLOCK:
                raise ValueError(f"Merge rejected: Change is blocked by policy: {policy.reason}")

            conflict = ConflictService(self.db).analyze(change)
            if conflict.level == ConflictService.LEVEL_CONFLICT:
                raise ValueError("Merge rejected: Git detected an actual merge conflict")
            if conflict.level == ConflictService.LEVEL_POTENTIAL:
                raise ValueError(f"Merge rejected: Potential Git conflict: {conflict.reason}")

            from app.services.branch_protection_service import BranchProtectionService
            bp_eval = BranchProtectionService(self.db).evaluate_pull_request(pr.id)
            if not bp_eval["passed"]:
                failed_str = ", ".join(bp_eval["failed_gates"])
                raise ValueError(f"Merge rejected by branch protection: Failed gates: {failed_str}")

            merge_svc = GitMergeService()
            merge_res = merge_svc.execute_server_side_merge(
                repository_storage_key=repository.storage_key,
                target_branch=pr.target_branch,
                source_commit=pr.source_commit,
                merger_id=merger_id,
                commit_message=f"Merge PR #{pr.id}: {pr.title}",
            )

            if not merge_res or not merge_res.success or not merge_res.resulting_commit:
                raise ValueError(
                    f"Git merge transport execution failed: {getattr(merge_res, 'error_message', 'Unknown error')}"
                )

            GitMergeService.validate_commit_sha(merge_res.resulting_commit)
            resulting_commit = merge_res.resulting_commit

        # 11. State Progression & Provenance Enrichment
        now = datetime.now(timezone.utc)
        old_status = pr.status
        pr.target_commit = resulting_commit
        pr.status = self.STATUS_MERGED
        pr.merged_at = now
        change.status = "recorded"

        change_meta["merged"] = True
        change_meta["merge_commit_sha"] = resulting_commit
        change_meta["merged_at"] = now.isoformat()
        change_meta["merged_by"] = merger_id
        change_meta["head_sha"] = current_head
        change.metadata_json = json.dumps(change_meta, sort_keys=True)

        # 12. Linked Task Completion
        linked_task = self.db.scalar(
            select(Task)
            .where(
                (Task.resulting_pull_request_id == pr.id) |
                (Task.resulting_change_id == change.id)
            )
            .with_for_update()
        )

        if linked_task and linked_task.status != Task.STATUS_COMPLETED:
            if not linked_task.resulting_pull_request_id:
                linked_task.resulting_pull_request_id = pr.id
            if not linked_task.resulting_change_id:
                linked_task.resulting_change_id = change.id
            from app.services.task_service import TaskService
            TaskService(self.db)._complete_locked_task(
                linked_task,
                actor_id=merger_id,
            )

        # 13. Immutable Sanitized Audit Event
        self._record_event(
            pr=pr,
            event_type="pull_request.merged",
            from_status=old_status,
            to_status=self.STATUS_MERGED,
            actor_id=merger_id,
            metadata={
                "pull_request_id": pr.id,
                "github_pr_number": gh_pr_number if is_github else None,
                "head_sha": current_head,
                "merge_sha": resulting_commit,
                "merge_method": "github" if is_github else "git_server_side",
                "actor_id": merger_id,
                "task_id": linked_task.id if linked_task else None,
                "change_id": change.id,
                "target_branch": pr.target_branch,
            },
        )

        self.db.flush()

        # Update Knowledge Graph with real lifecycle transition
        try:
            from app.services import knowledge_graph_service
            knowledge_graph_service.index_engineering_lifecycle(self.db, repository)
            self.db.flush()
        except Exception:
            pass

        NotificationService.create_notification(
            db=self.db,
            user_id=pr.author_id,
            title=f"PR merged: {pr.title}",
            message=f"Your pull request #{pr.id[:8]} was merged into {pr.target_branch}.",
            type="pr",
            link=f"/repositories/{repository.slug}/pull-requests/{pr.id}"
        )

        return PRMergeResult(
            status="merged",
            detail=f"Successfully merged PR #{pr.id} into '{pr.target_branch}' at commit {resulting_commit}",
            pull_request=pr,
            merge_commit_sha=resulting_commit,
            merged_at=now,
        )

    # ---------------------------------------------------------
    # CLOSE & REJECT
    # ---------------------------------------------------------

    def close_pull_request(
        self,
        pr: PullRequest,
        user_id: str,
        reason: str | None = None,
    ) -> PullRequest:
        repository = self.db.scalar(
            select(Repository).where(
                Repository.id == pr.repository_id,
                Repository.deleted_at.is_(None),
            )
        )
        if repository is not None:
            self._authorize_user_repo_access(user_id, repository)

        return self.transition_pull_request(
            pr,
            self.STATUS_CLOSED,
            actor_id=user_id,
            reason=reason,
        )

    def reject_pull_request(
        self,
        pr: PullRequest,
        user_id: str,
        reason: str | None = None,
    ) -> PullRequest:
        repository = self.db.scalar(
            select(Repository).where(
                Repository.id == pr.repository_id,
                Repository.deleted_at.is_(None),
            )
        )
        if repository is not None:
            self._authorize_user_repo_access(user_id, repository)

        return self.transition_pull_request(
            pr,
            self.STATUS_REJECTED,
            actor_id=user_id,
            reason=reason,
        )

    # ---------------------------------------------------------
    # PR EVENTS (Audit Read API)
    # ---------------------------------------------------------

    def get_pull_request_events(
        self,
        pr_id: str,
        user_id: str,
    ) -> tuple[PullRequest, list[ChangeEvent]] | None:
        pr = self.get_pull_request(pr_id, user_id)
        if pr is None:
            return None

        events = self.db.scalars(
            select(ChangeEvent)
            .where(ChangeEvent.change_id == pr.source_change_id)
            .order_by(ChangeEvent.created_at.asc(), ChangeEvent.id.asc())
        ).all()

        return pr, list(events)

    # ---------------------------------------------------------
    # PR DIFF & FILES ENGINE (Phase 17D)
    # ---------------------------------------------------------

    def get_pull_request_files(
        self,
        pr_id: str,
        user_id: str,
    ) -> tuple[PullRequest, list[dict]] | None:
        pr = self.get_pull_request(pr_id, user_id)
        if pr is None:
            return None

        c_files = self.db.scalars(
            select(ChangeFile).where(ChangeFile.change_id == pr.source_change_id)
        ).all()

        files = []
        for cf in c_files:
            files.append({
                "path": cf.path,
                "operation": cf.operation,
                "old_hash": cf.old_hash,
                "new_hash": cf.new_hash,
            })
        return pr, files

    def get_pull_request_diff(
        self,
        pr_id: str,
        user_id: str,
    ) -> tuple[PullRequest, dict] | None:
        pr = self.get_pull_request(pr_id, user_id)
        if pr is None:
            return None

        change = self.db.scalar(
            select(Change).where(Change.id == pr.source_change_id)
        )
        if change is None or not change.base_commit or not change.resulting_commit:
            return pr, {"files": []}

        repository = self.db.scalar(
            select(Repository).where(Repository.id == pr.repository_id)
        )
        if repository is None:
            return pr, {"files": []}

        repo_dir = Path(settings.repository_storage_path) / repository.storage_key
        if not repo_dir.exists():
            return pr, {"files": []}

        res = subprocess.run(
            [
                "git",
                "--git-dir",
                str(repo_dir),
                "diff",
                "-u",
                f"{change.base_commit}..{change.resulting_commit}",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        if res.returncode != 0 or not res.stdout:
            res = subprocess.run(
                [
                    "git",
                    "--git-dir",
                    str(repo_dir),
                    "diff-tree",
                    "-p",
                    "-r",
                    change.resulting_commit,
                ],
                capture_output=True,
                text=True,
                check=False,
            )

        parsed_files = self._parse_patch_text(res.stdout or "")
        return pr, {"files": parsed_files}

    @staticmethod
    def _parse_patch_text(patch_text: str) -> list[dict]:
        files = []
        current_file = None
        current_hunk = None
        old_line = 0
        new_line = 0

        for line in patch_text.splitlines():
            if line.startswith("diff --git "):
                if current_file:
                    if current_hunk:
                        current_file["hunks"].append(current_hunk)
                        current_hunk = None
                    files.append(current_file)
                parts = line.split(" ")
                old_p = parts[2][2:] if len(parts) > 2 and parts[2].startswith("a/") else ""
                new_p = parts[3][2:] if len(parts) > 3 and parts[3].startswith("b/") else ""
                current_file = {
                    "old_path": old_p,
                    "new_path": new_p,
                    "path": new_p or old_p,
                    "is_binary": False,
                    "hunks": [],
                }
            elif current_file is not None:
                if line.startswith("Binary files "):
                    current_file["is_binary"] = True
                elif line.startswith("@@ "):
                    if current_hunk:
                        current_file["hunks"].append(current_hunk)
                    m = re.search(r"@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@", line)
                    if m:
                        old_start = int(m.group(1))
                        old_count = int(m.group(2)) if m.group(2) is not None else 1
                        new_start = int(m.group(3))
                        new_count = int(m.group(4)) if m.group(4) is not None else 1
                    else:
                        old_start, old_count, new_start, new_count = 1, 0, 1, 0
                    old_line = old_start
                    new_line = new_start
                    current_hunk = {
                        "header": line,
                        "old_start": old_start,
                        "old_lines": old_count,
                        "new_start": new_start,
                        "new_lines": new_count,
                        "lines": [],
                    }
                elif current_hunk is not None:
                    if line.startswith("+") and not line.startswith("+++"):
                        current_hunk["lines"].append({
                            "type": "add",
                            "old_line_number": None,
                            "new_line_number": new_line,
                            "content": line[1:],
                        })
                        new_line += 1
                    elif line.startswith("-") and not line.startswith("---"):
                        current_hunk["lines"].append({
                            "type": "delete",
                            "old_line_number": old_line,
                            "new_line_number": None,
                            "content": line[1:],
                        })
                        old_line += 1
                    elif line.startswith(" ") or line == "":
                        current_hunk["lines"].append({
                            "type": "context",
                            "old_line_number": old_line,
                            "new_line_number": new_line,
                            "content": line[1:] if line.startswith(" ") else line,
                        })
                        old_line += 1
                        new_line += 1

        if current_file:
            if current_hunk:
                current_file["hunks"].append(current_hunk)
            files.append(current_file)

        return files
