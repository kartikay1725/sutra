from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import subprocess
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.actor import Actor
from app.models.change import Change
from app.models.change_event import ChangeEvent
from app.models.change_file import ChangeFile
from app.models.change_review import ChangeReview
from app.models.pull_request import PullRequest
from app.models.repository import Repository
from app.models.task import Task
from app.models.user import User
from app.services.authorization_service import AuthorizationService
from app.services.change_policy_service import ChangePolicyService
from app.services.conflict_service import ConflictResult, ConflictService
from app.services.git_merge_service import GitMergeService
from app.services.notification_service import NotificationService


@dataclass
class PRMergeResult:
    status: str
    detail: str
    pull_request: PullRequest


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

    def __init__(self, db: Session):
        self.db = db

    # ---------------------------------------------------------
    # AUTHORIZATION HELPERS
    # ---------------------------------------------------------

    def _authorize_user_repo_access(
        self,
        user_id: str,
        repository: Repository,
    ) -> None:
        """Verify human user owns or has access to repository."""
        if repository.owner_id != user_id:
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
                if change and change.resulting_commit:
                    try:
                        from app.services.ci_service import CIService
                        ci_svc = CIService(self.db)
                        ci_job = ci_svc.create_job(
                            pull_request_id=pr.id,
                            actor_id=author_id,
                            trigger="pull_request",
                        )
                        running_job = self.db.scalar(
                            select(CIJob).where(
                                CIJob.repository_id == repository.id,
                                CIJob.status == CIJob.STATUS_RUNNING,
                            )
                        )
                        if not running_job and ci_job:
                            ci_svc.run_execution(ci_job.id, worker_id=f"api_worker_{uuid4().hex[:8]}")
                    except Exception:
                        pass

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
        if repository is None or repository.owner_id != user_id:
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

        # Evaluate policy
        policy_decision = ChangePolicyService(self.db).evaluate(change)
        if policy_decision.decision == ChangePolicyService.BLOCK:
            raise ValueError(f"Change is currently blocked by policy: {policy_decision.reason}")

        # Resolve authoritative ChangeReview
        if review_id:
            review = self.db.scalar(
                select(ChangeReview).where(
                    ChangeReview.id == review_id,
                    ChangeReview.change_id == change.id,
                )
            )
        else:
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
                },
            )
            self.db.flush()

            if change.status == "proposed":
                ChangeService(self.db).finalize_change(change)
                self.db.flush()

        elif review.status == "approved":
            if review.reviewer_id == approver_id or (review.reviewer_id and review.reviewer_id != pr.author_id and review.reviewer_id != change.actor_id):
                pass
            elif review.reviewer_id == pr.author_id or review.reviewer_id == change.actor_id:
                raise ValueError("Self-review approval is strictly prohibited")

        return self.transition_pull_request(
            pr,
            self.STATUS_APPROVED,
            actor_id=approver_id,
            reason=reason,
            metadata={
                "review_id": review.id if review else None,
                "reviewer_id": approver_id,
            },
        )

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

        # 2. Repository resolution & authorization check
        repository = self.db.scalar(
            select(Repository).where(
                Repository.id == pr.repository_id,
                Repository.deleted_at.is_(None),
            )
        )
        if repository is None:
            return None

        self._authorize_user_repo_access(merger_id, repository)

        # 3. Lifecycle check
        if pr.status == self.STATUS_MERGED:
            return PRMergeResult(
                status="merged",
                detail="PullRequest is already merged",
                pull_request=pr,
            )

        if pr.status == self.STATUS_CLOSED:
            raise ValueError(f"Cannot merge PullRequest in status '{pr.status}'")

        if pr.status not in {self.STATUS_OPEN, self.STATUS_APPROVED}:
            raise ValueError(f"Cannot merge PullRequest in status '{pr.status}'")

        # 4. Source Change resolution & cross-repository invariant
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

        # 5. Policy evaluation
        policy = ChangePolicyService(self.db).evaluate(change)
        if policy.decision == ChangePolicyService.BLOCK:
            raise ValueError(f"Merge rejected: Change is blocked by policy: {policy.reason}")

        if policy.decision == ChangePolicyService.REVIEW:
            reviews = self.db.scalars(
                select(ChangeReview).where(
                    ChangeReview.change_id == change.id,
                    ChangeReview.status == "approved",
                )
            ).all()
            valid = [r for r in reviews if r.reviewer_id != pr.author_id and r.reviewer_id != change.actor_id]
            if not valid:
                raise ValueError("Merge rejected: Change requires an approved ChangeReview")

        # 6. Conflict check
        conflict = ConflictService(self.db).analyze(change)
        if conflict.level == ConflictService.LEVEL_CONFLICT:
            raise ValueError("Merge rejected: Git detected an actual merge conflict")

        if conflict.level == ConflictService.LEVEL_POTENTIAL:
            raise ValueError(f"Merge rejected: Potential Git conflict: {conflict.reason}")

        # 7. Branch protection evaluation gate
        from app.services.branch_protection_service import BranchProtectionService
        bp_eval = BranchProtectionService(self.db).evaluate_pull_request(pr.id)
        if not bp_eval["passed"]:
            failed_str = ", ".join(bp_eval["failed_gates"])
            raise ValueError(f"Merge rejected by branch protection: Failed gates: {failed_str}")

        # 8. Real Server-Side Git Merge Transport Execution (v0.3.6)
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

        now = datetime.now(timezone.utc)
        old_status = pr.status
        pr.target_commit = merge_res.resulting_commit
        pr.status = self.STATUS_MERGED
        pr.merged_at = now
        change.status = "recorded"

        self._record_event(
            pr=pr,
            event_type="pull_request.merged",
            from_status=old_status,
            to_status=self.STATUS_MERGED,
            actor_id=merger_id,
            metadata={
                "source_commit": pr.source_commit,
                "previous_target_commit": merge_res.previous_target_commit,
                "resulting_commit": merge_res.resulting_commit,
                "is_fast_forward": merge_res.is_fast_forward,
                "target_branch": pr.target_branch,
            },
        )

        # Complete linked task if present
        linked_task = self.db.scalar(
            select(Task)
            .where(Task.resulting_pull_request_id == pr.id)
            .with_for_update()
        )

        if linked_task:
            from app.services.task_service import TaskService
            TaskService(self.db)._complete_locked_task(
                linked_task,
                actor_id=merger_id,
            )

        self.db.flush()

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
            detail=f"Successfully merged PR #{pr.id} into '{pr.target_branch}' at commit {merge_res.resulting_commit}",
            pull_request=pr,
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
