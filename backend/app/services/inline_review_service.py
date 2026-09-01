from datetime import datetime, timezone
import json
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.change_event import ChangeEvent
from app.models.inline_review_comment import InlineReviewComment
from app.models.pull_request import PullRequest
from app.models.repository import Repository
from app.models.user import User
from app.services.authorization_service import AuthorizationService


class InlineReviewService:
    """
    Authoritative business logic service for Inline Code Review discussion & threads.

    Note: Inline comments and thread resolution are discussion artifacts.
    ChangeReview remains the sole authoritative approval mechanism in SUTRA.
    """

    MAX_BODY_LENGTH = 10000

    def __init__(self, db: Session):
        self.db = db

    def _authorize_user_repo_access(self, user_id: str, repository: Repository) -> None:
        user = self.db.scalar(select(User).where(User.id == user_id))
        if user is None:
            raise PermissionError("User not found")

        if repository.visibility == "private" and repository.owner_id != user_id:
            raise PermissionError("User does not have access to this private repository")

    def _record_event(
        self,
        pr: PullRequest,
        event_type: str,
        comment: InlineReviewComment,
        actor_id: str,
        metadata: dict | None = None,
    ) -> ChangeEvent:
        safe_meta = {
            "pull_request_id": pr.id,
            "repository_id": pr.repository_id,
            "comment_id": comment.id,
            "parent_id": comment.parent_id,
            "path": comment.path,
            "line_number": comment.line_number,
            "diff_side": comment.diff_side,
            "status": comment.status,
        }
        if metadata:
            for k, v in metadata.items():
                if k.lower() not in {"token", "jwt", "password", "secret", "authorization", "cookie"}:
                    safe_meta[k] = v

        event = ChangeEvent(
            change_id=pr.source_change_id,
            actor_id=actor_id,
            event_type=event_type,
            from_status=None,
            to_status=comment.status,
            reason=None,
            metadata_json=json.dumps(safe_meta, sort_keys=True),
        )
        self.db.add(event)
        return event

    def create_comment(
        self,
        pull_request_id: str,
        author_id: str,
        body: str,
        path: str | None = None,
        diff_side: str | None = None,
        line_number: int | None = None,
        line_range_start: int | None = None,
        line_range_end: int | None = None,
        commit_sha: str | None = None,
        parent_id: str | None = None,
    ) -> InlineReviewComment:
        if not body or not body.strip():
            raise ValueError("Comment body cannot be empty")
        if len(body) > self.MAX_BODY_LENGTH:
            raise ValueError(f"Comment body exceeds maximum allowed length ({self.MAX_BODY_LENGTH})")

        # 1. Fetch & validate PR
        pr = self.db.scalar(select(PullRequest).where(PullRequest.id == pull_request_id))
        if pr is None:
            raise ValueError("PullRequest not found")

        # 2. Fetch & validate Repository
        repository = self.db.scalar(
            select(Repository).where(
                Repository.id == pr.repository_id,
                Repository.deleted_at.is_(None),
            )
        )
        if repository is None:
            raise ValueError("Repository not found or deleted")

        # 3. Authorize user access
        self._authorize_user_repo_access(author_id, repository)

        # 4. Validate reply parent if provided
        parent_comment = None
        if parent_id is not None:
            parent_comment = self.db.scalar(
                select(InlineReviewComment).where(InlineReviewComment.id == parent_id)
            )
            if parent_comment is None:
                raise ValueError("Parent comment not found")
            if parent_comment.pull_request_id != pull_request_id:
                raise ValueError("Parent comment belongs to a different PullRequest")

            # Inherit parent path & line if not explicitly provided
            if path is None:
                path = parent_comment.path
            if diff_side is None:
                diff_side = parent_comment.diff_side
            if line_number is None:
                line_number = parent_comment.line_number

        # 5. Validate inline comment parameters
        if path is not None:
            if not path.strip() or ".." in path or path.startswith("-"):
                raise ValueError(f"Invalid file path '{path}'")
        if line_number is not None:
            if line_number <= 0:
                raise ValueError("line_number must be greater than 0")
        if diff_side is not None:
            if diff_side not in InlineReviewComment.VALID_SIDES:
                raise ValueError(f"Invalid diff_side '{diff_side}'. Must be 'LEFT' or 'RIGHT'")

        now = datetime.now(timezone.utc)
        comment = InlineReviewComment(
            pull_request_id=pull_request_id,
            repository_id=pr.repository_id,
            author_id=author_id,
            parent_id=parent_id,
            path=path.strip() if path else None,
            diff_side=diff_side,
            line_number=line_number,
            line_range_start=line_range_start,
            line_range_end=line_range_end,
            commit_sha=commit_sha,
            body=body.strip(),
            status=InlineReviewComment.STATUS_ACTIVE,
            created_at=now,
            updated_at=now,
        )
        self.db.add(comment)
        self.db.flush()

        event_type = "inline_review.reply_created" if parent_id else "inline_review.comment_created"
        self._record_event(pr, event_type, comment, author_id)
        self.db.flush()
        return comment

    def get_comments_for_pull_request(
        self,
        pull_request_id: str,
        user_id: str,
    ) -> tuple[PullRequest, list[InlineReviewComment]] | None:
        pr = self.db.scalar(select(PullRequest).where(PullRequest.id == pull_request_id))
        if pr is None:
            return None

        repository = self.db.scalar(
            select(Repository).where(
                Repository.id == pr.repository_id,
                Repository.deleted_at.is_(None),
            )
        )
        if repository is None:
            return None

        self._authorize_user_repo_access(user_id, repository)

        comments = self.db.scalars(
            select(InlineReviewComment)
            .where(InlineReviewComment.pull_request_id == pull_request_id)
            .order_by(InlineReviewComment.created_at.asc(), InlineReviewComment.id.asc())
        ).all()

        return pr, list(comments)

    def resolve_thread(
        self,
        comment_id: str,
        user_id: str,
    ) -> InlineReviewComment:
        comment = self.db.scalar(
            select(InlineReviewComment)
            .where(InlineReviewComment.id == comment_id)
            .with_for_update()
        )
        if comment is None:
            raise ValueError("Comment not found")

        target_comment = comment
        if comment.parent_id is not None:
            root = self.db.scalar(
                select(InlineReviewComment)
                .where(InlineReviewComment.id == comment.parent_id)
                .with_for_update()
            )
            if root is not None:
                target_comment = root

        pr = self.db.scalar(select(PullRequest).where(PullRequest.id == target_comment.pull_request_id))
        if pr is None:
            raise ValueError("PullRequest not found")

        repository = self.db.scalar(
            select(Repository).where(
                Repository.id == pr.repository_id,
                Repository.deleted_at.is_(None),
            )
        )
        if repository is None:
            raise ValueError("Repository not found or deleted")

        self._authorize_user_repo_access(user_id, repository)

        if target_comment.status == InlineReviewComment.STATUS_RESOLVED:
            return target_comment

        now = datetime.now(timezone.utc)
        target_comment.status = InlineReviewComment.STATUS_RESOLVED
        target_comment.resolved_at = now
        target_comment.resolved_by = user_id
        target_comment.updated_at = now

        self._record_event(pr, "inline_review.thread_resolved", target_comment, user_id)
        self.db.flush()
        return target_comment

    def reopen_thread(
        self,
        comment_id: str,
        user_id: str,
    ) -> InlineReviewComment:
        comment = self.db.scalar(
            select(InlineReviewComment)
            .where(InlineReviewComment.id == comment_id)
            .with_for_update()
        )
        if comment is None:
            raise ValueError("Comment not found")

        target_comment = comment
        if comment.parent_id is not None:
            root = self.db.scalar(
                select(InlineReviewComment)
                .where(InlineReviewComment.id == comment.parent_id)
                .with_for_update()
            )
            if root is not None:
                target_comment = root

        pr = self.db.scalar(select(PullRequest).where(PullRequest.id == target_comment.pull_request_id))
        if pr is None:
            raise ValueError("PullRequest not found")

        repository = self.db.scalar(
            select(Repository).where(
                Repository.id == pr.repository_id,
                Repository.deleted_at.is_(None),
            )
        )
        if repository is None:
            raise ValueError("Repository not found or deleted")

        self._authorize_user_repo_access(user_id, repository)

        if target_comment.status == InlineReviewComment.STATUS_ACTIVE:
            return target_comment

        now = datetime.now(timezone.utc)
        target_comment.status = InlineReviewComment.STATUS_ACTIVE
        target_comment.resolved_at = None
        target_comment.resolved_by = None
        target_comment.updated_at = now

        self._record_event(pr, "inline_review.thread_reopened", target_comment, user_id)
        self.db.flush()
        return target_comment
