from datetime import datetime, timezone
import fnmatch
import re
from typing import Any, Dict, List, Optional
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.actor import Actor
from app.models.agent import Agent
from app.models.branch_protection_rule import BranchProtectionRule
from app.models.change import Change
from app.models.change_event import ChangeEvent
from app.models.change_review import ChangeReview
from app.models.inline_review_comment import InlineReviewComment
from app.models.pull_request import PullRequest
from app.models.repository import Repository
from app.models.user import User
from app.services.agent_review_service import AgentReviewService
from app.services.authorization_service import AuthorizationService
from app.services.conflict_service import ConflictService


SAFE_BRANCH_PATTERN = r"^[a-zA-Z0-9_\-/*.]+$"


class BranchProtectionService:
    def __init__(self, db: Session):
        self.db = db

    def _get_user_actor(self, user_id: str) -> Actor:
        """
        Resolve the Actor identity for a human user.

        Older data may use Actor.type == "user", while current identity
        records use Actor.type == "human". Reuse either existing identity
        rather than attempting to create a duplicate Actor.

        If no Actor exists at all, create the canonical current "human"
        Actor.
        """
        actor = self.db.scalar(
            select(Actor).where(
                Actor.id == user_id,
                Actor.type.in_(("human", "user")),
            )
        )

        if actor is not None:
            return actor

        actor = Actor(
            id=user_id,
            owner_id=user_id,
            type="human",
            name=user_id,
            capabilities=(
                '["repository.read", '
                '"repository.write", '
                '"change.create", '
                '"change.review", '
                '"change.approve"]'
            ),
        )

        self.db.add(actor)
        self.db.flush()

        return actor

    def create_rule(
        self,
        repository_id: str,
        actor_user_id: str,
        branch_pattern: str,
        enabled: bool = True,
        required_approvals: int = 1,
        require_change_review: bool = True,
        require_clean_conflict: bool = True,
        require_resolved_threads: bool = True,
        require_agent_review: bool = False,
        require_no_blocking_agent_findings: bool = False,
        allow_author_self_approval: bool = False,
        require_ci_passed: bool = False,
    ) -> BranchProtectionRule:
        repo = self.db.scalar(
            select(Repository).where(
                Repository.id == repository_id,
                Repository.deleted_at.is_(None),
            )
        )

        if not repo:
            raise ValueError("Repository not found")

        user_actor = self._get_user_actor(
            actor_user_id
        )

        if repo.owner_id != actor_user_id:
            auth_res = AuthorizationService.check(
                user_actor,
                repo,
                AuthorizationService.WRITE,
            )

            if not auth_res.allowed:
                raise PermissionError(
                    "User is not authorized to manage branch protection rules"
                )

        if (
            not branch_pattern
            or not re.match(
                SAFE_BRANCH_PATTERN,
                branch_pattern,
            )
            or ".." in branch_pattern
            or branch_pattern.startswith("-")
        ):
            raise ValueError(
                "Invalid branch pattern"
            )

        if required_approvals < 0:
            raise ValueError(
                "required_approvals cannot be negative"
            )

        rule = BranchProtectionRule(
            id=str(uuid4()),
            repository_id=repository_id,
            branch_pattern=branch_pattern,
            enabled=enabled,
            required_approvals=required_approvals,
            require_change_review=require_change_review,
            require_clean_conflict=require_clean_conflict,
            require_resolved_threads=require_resolved_threads,
            require_agent_review=require_agent_review,
            require_no_blocking_agent_findings=(
                require_no_blocking_agent_findings
            ),
            allow_author_self_approval=(
                allow_author_self_approval
            ),
            require_ci_passed=require_ci_passed,
            created_by=actor_user_id,
            updated_by=actor_user_id,
        )

        self.db.add(rule)
        self.db.flush()

        change = self.db.scalar(
            select(Change)
            .where(
                Change.repository_id == repository_id
            )
            .order_by(
                Change.created_at.desc()
            )
        )

        if change:
            event = ChangeEvent(
                id=str(uuid4()),
                change_id=change.id,
                event_type="branch_protection.created",
                actor_id=actor_user_id,
                metadata_json=(
                    f'{{"rule_id": "{rule.id}", '
                    f'"branch_pattern": "{branch_pattern}"}}'
                ),
            )
            self.db.add(event)

        return rule

    def update_rule(
        self,
        rule_id: str,
        actor_user_id: str,
        **updates: Any,
    ) -> BranchProtectionRule:
        rule = self.db.scalar(
            select(BranchProtectionRule).where(
                BranchProtectionRule.id == rule_id
            )
        )

        if not rule:
            raise ValueError(
                "Branch protection rule not found"
            )

        repo = self.db.scalar(
            select(Repository).where(
                Repository.id == rule.repository_id
            )
        )

        if not repo:
            raise ValueError(
                "Repository not found"
            )

        user_actor = self._get_user_actor(
            actor_user_id
        )

        if repo.owner_id != actor_user_id:
            auth_res = AuthorizationService.check(
                user_actor,
                repo,
                AuthorizationService.WRITE,
            )

            if not auth_res.allowed:
                raise PermissionError(
                    "User is not authorized to manage branch protection rules"
                )

        if "branch_pattern" in updates:
            bp = updates["branch_pattern"]

            if (
                not bp
                or not re.match(
                    SAFE_BRANCH_PATTERN,
                    bp,
                )
                or ".." in bp
                or bp.startswith("-")
            ):
                raise ValueError(
                    "Invalid branch pattern"
                )

            rule.branch_pattern = bp

        if "required_approvals" in updates:
            ra = updates["required_approvals"]

            if ra < 0:
                raise ValueError(
                    "required_approvals cannot be negative"
                )

            rule.required_approvals = ra

        for field in [
            "enabled",
            "require_change_review",
            "require_clean_conflict",
            "require_resolved_threads",
            "require_agent_review",
            "require_no_blocking_agent_findings",
            "allow_author_self_approval",
            "require_ci_passed",
        ]:
            if field in updates:
                setattr(
                    rule,
                    field,
                    updates[field],
                )

        rule.updated_by = actor_user_id
        rule.updated_at = datetime.now(
            timezone.utc
        )

        self.db.flush()

        change = self.db.scalar(
            select(Change)
            .where(
                Change.repository_id == repo.id
            )
            .order_by(
                Change.created_at.desc()
            )
        )

        if change:
            event = ChangeEvent(
                id=str(uuid4()),
                change_id=change.id,
                event_type="branch_protection.updated",
                actor_id=actor_user_id,
                metadata_json=(
                    f'{{"rule_id": "{rule.id}", '
                    f'"branch_pattern": '
                    f'"{rule.branch_pattern}"}}'
                ),
            )
            self.db.add(event)

        return rule

    def delete_rule(
        self,
        rule_id: str,
        actor_user_id: str,
    ) -> bool:
        rule = self.db.scalar(
            select(BranchProtectionRule).where(
                BranchProtectionRule.id == rule_id
            )
        )

        if not rule:
            raise ValueError(
                "Branch protection rule not found"
            )

        repo = self.db.scalar(
            select(Repository).where(
                Repository.id == rule.repository_id
            )
        )

        if repo and repo.owner_id != actor_user_id:
            user_actor = self._get_user_actor(
                actor_user_id
            )

            auth_res = AuthorizationService.check(
                user_actor,
                repo,
                AuthorizationService.WRITE,
            )

            if not auth_res.allowed:
                raise PermissionError(
                    "User is not authorized to manage branch protection rules"
                )

        self.db.delete(rule)
        self.db.flush()

        return True

    def get_effective_rule(
        self,
        repository_id: str,
        branch: str,
    ) -> Optional[BranchProtectionRule]:
        rules = self.db.scalars(
            select(BranchProtectionRule).where(
                BranchProtectionRule.repository_id
                == repository_id,
                BranchProtectionRule.enabled.is_(True),
            )
        ).all()

        for rule in rules:
            if rule.branch_pattern == branch:
                return rule

        for rule in rules:
            if fnmatch.fnmatch(
                branch,
                rule.branch_pattern,
            ):
                return rule

        return None

    def evaluate_pull_request(
        self,
        pull_request_id: str,
    ) -> Dict[str, Any]:
        pr = self.db.scalar(
            select(PullRequest).where(
                PullRequest.id == pull_request_id
            )
        )

        if not pr:
            raise ValueError(
                "PullRequest not found"
            )

        rule = self.get_effective_rule(
            pr.repository_id,
            pr.target_branch,
        )

        if not rule:
            return {
                "passed": True,
                "failed_gates": [],
                "rule_id": None,
                "target_branch": pr.target_branch,
            }

        failed_gates: List[str] = []

        reviews = self.db.scalars(
            select(ChangeReview).where(
                ChangeReview.change_id
                == pr.source_change_id,
                ChangeReview.status == "approved",
            )
        ).all()

        if (
            rule.require_change_review
            and not reviews
        ):
            failed_gates.append(
                "missing_change_review"
            )

        valid_reviews = reviews

        if not rule.allow_author_self_approval:
            valid_reviews = [
                review
                for review in reviews
                if review.reviewer_id
                != pr.author_id
            ]

        unique_reviewers = {
            review.reviewer_id
            for review in valid_reviews
        }

        if (
            len(unique_reviewers)
            < rule.required_approvals
        ):
            failed_gates.append(
                "insufficient_approvals"
            )

        if rule.require_resolved_threads:
            unresolved = self.db.scalars(
                select(InlineReviewComment).where(
                    InlineReviewComment.pull_request_id
                    == pr.id,
                    InlineReviewComment.status
                    != "resolved",
                )
            ).all()

            if unresolved:
                failed_gates.append(
                    "unresolved_inline_threads"
                )

        if (
            rule.require_agent_review
            or rule.require_no_blocking_agent_findings
        ):
            agent_svc = AgentReviewService(
                self.db
            )

            summary = (
                agent_svc.get_agent_review_summary(
                    pr.id,
                    pr.author_id,
                    is_agent=False,
                )
            )

            if (
                rule.require_agent_review
                and summary["total_findings"] == 0
                and summary[
                    "participating_agents_count"
                ] == 0
            ):
                failed_gates.append(
                    "missing_agent_review"
                )

            if (
                rule.require_no_blocking_agent_findings
            ):
                critical = summary[
                    "severity_distribution"
                ].get(
                    "critical",
                    0,
                )

                high = summary[
                    "severity_distribution"
                ].get(
                    "high",
                    0,
                )

                if critical > 0 or high > 0:
                    failed_gates.append(
                        "unresolved_agent_findings"
                    )

        if rule.require_clean_conflict:
            change = self.db.scalar(
                select(Change).where(
                    Change.id
                    == pr.source_change_id
                )
            )

            if change:
                conflict_res = (
                    ConflictService(
                        self.db
                    ).analyze(change)
                )

                if (
                    conflict_res.level
                    != ConflictService.LEVEL_NONE
                ):
                    failed_gates.append(
                        "conflict_detected"
                    )

        if getattr(
            rule,
            "require_ci_passed",
            False,
        ):
            from app.models.ci_job import CIJob

            change = self.db.scalar(
                select(Change).where(
                    Change.id
                    == pr.source_change_id
                )
            )

            target_commit = (
                change.resulting_commit
                if change
                else pr.source_commit
            )

            latest_ci = self.db.scalar(
                select(CIJob)
                .where(
                    CIJob.pull_request_id
                    == pr.id,
                    CIJob.commit_sha
                    == target_commit,
                )
                .order_by(
                    CIJob.created_at.desc()
                )
            )

            if (
                not latest_ci
                or latest_ci.status
                != CIJob.STATUS_PASSED
            ):
                failed_gates.append(
                    "missing_or_failed_ci"
                )

        passed = len(failed_gates) == 0

        return {
            "passed": passed,
            "failed_gates": failed_gates,
            "rule_id": rule.id,
            "target_branch": pr.target_branch,
            "required_approvals": (
                rule.required_approvals
            ),
            "actual_approvals": len(
                unique_reviewers
            ),
        }