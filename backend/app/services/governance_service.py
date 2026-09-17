from datetime import datetime, timezone
import json
import logging
from typing import Any, Dict, List, Optional
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings

from app.models.actor import Actor
from app.models.agent import Agent
from app.models.agent_session import AgentSession
from app.models.branch_protection_rule import BranchProtectionRule
from app.models.change import Change
from app.models.change_event import ChangeEvent
from app.models.change_review import ChangeReview
from app.models.governance_policy import GovernancePolicy
from app.models.pull_request import PullRequest
from app.models.repository import Repository
from app.models.task import Task
from app.models.user import User
from app.providers.base import RepositoryProvider
from app.services.agent_review_service import AgentReviewService
from app.services.authorization_service import AuthorizationService
from app.services.branch_protection_service import BranchProtectionService
from app.services.change_policy_service import ChangePolicyService
from app.services.ci_service import CIService
from app.services.conflict_service import ConflictService

logger = logging.getLogger("sutra.services.governance")


class GovernanceVerdict:
    READY_FOR_APPROVAL = "READY_FOR_APPROVAL"
    READY_FOR_MERGE = "READY_FOR_MERGE"
    BLOCKED = "BLOCKED"
    NEEDS_REVIEW = "NEEDS_REVIEW"
    CI_PENDING = "CI_PENDING"
    CI_FAILED = "CI_FAILED"
    POLICY_FAILED = "POLICY_FAILED"


class GovernanceService:
    """
    Authoritative SUTRA Control-Plane Governance Engine.

    Determines whether a Pull Request is eligible to proceed to Human Approval.

    Authoritative for:
      - SUTRA governance policies
      - Agent permissions & sessions
      - Cryptographic/database provenance requirements
      - Required CI state evaluation
      - Risk & conflict rules
      - Review requirements & self-review prevention
      - Structured auditability
    """

    def __init__(self, db: Session, provider: Optional[RepositoryProvider] = None):
        self.db = db
        self.provider = provider
        self.ci_service = CIService(db, provider=provider)
        self.branch_service = BranchProtectionService(db)
        self.change_policy_service = ChangePolicyService(db)

    def evaluate_pull_request(
        self,
        pull_request_id: str,
        actor_id: Optional[str] = None,
        record_audit: bool = False,
    ) -> Dict[str, Any]:
        """
        Deterministically evaluates the full control-plane governance policy for a PullRequest.
        """
        pr = self.db.scalar(select(PullRequest).where(PullRequest.id == pull_request_id))
        if not pr:
            raise ValueError("PullRequest not found")

        repo = self.db.scalar(
            select(Repository).where(
                Repository.id == pr.repository_id,
                Repository.deleted_at.is_(None),
            )
        )
        if not repo:
            raise ValueError("Repository not found or deleted")

        # Authorize actor if supplied
        if actor_id:
            self._authorize_actor_access(actor_id, repo)

        passed: List[str] = []
        failed: List[str] = []
        warnings: List[str] = []

        # =================================================================
        # 1. CHANGE VALIDITY & COMMIT CHECKS
        # =================================================================
        change = self.db.scalar(select(Change).where(Change.id == pr.source_change_id))
        if not change:
            failed.append("Source Change does not exist for this Pull Request.")
        elif change.repository_id != pr.repository_id:
            failed.append("Repository mismatch: Change does not belong to the PR repository.")
        elif not change.resulting_commit:
            failed.append("Change has no resulting commit recorded.")
        elif change.status not in ("proposed", "recorded"):
            failed.append(f"Change status '{change.status}' is not eligible for governance.")
        else:
            if pr.source_commit and change.resulting_commit and pr.source_commit != change.resulting_commit:
                failed.append(
                    f"PR HEAD commit ({pr.source_commit[:8]}) does not match Change resulting commit ({change.resulting_commit[:8]})."
                )
            else:
                passed.append("Change and commit integrity verified.")

        if change:
            try:
                c_meta = json.loads(change.metadata_json or "{}")
            except Exception:
                c_meta = {}
            commit_origin = c_meta.get("commit_origin", "unknown")
            if commit_origin == "external_unverified":
                failed.append(
                    "PR was submitted via external/unverified commit import and cannot "
                    "receive SUTRA governance approval. Only SUTRA-governed commits are eligible."
                )
            elif commit_origin == "sutra_governed":
                passed.append("Commit origin verified as SUTRA-governed.")
            elif commit_origin not in ("pending", "unknown"):
                warnings.append(f"Commit origin is '{commit_origin}'; SUTRA authorship unverifiable.")

        head_sha = pr.source_commit or (change.resulting_commit if change else "")

        # =================================================================
        # 2. TASK LINKAGE & AGENT PROVENANCE
        # =================================================================
        author_actor = self.db.scalar(select(Actor).where(Actor.id == pr.author_id))
        is_agent_author = False
        agent_id: Optional[str] = None
        agent_name: Optional[str] = None
        session_id: Optional[str] = None
        task_id: Optional[str] = None
        task_title: Optional[str] = None
        provenance_verified = False

        if author_actor and author_actor.type == "agent":
            is_agent_author = True
            agent_id = author_actor.id
        else:
            # Check if an Agent record exists with author_id
            direct_agent = self.db.scalar(select(Agent).where(Agent.id == pr.author_id))
            if direct_agent:
                is_agent_author = True
                agent_id = direct_agent.id

        if is_agent_author:
            # Locate originating task
            origin_task = self.db.scalar(
                select(Task).where(
                    (Task.resulting_pull_request_id == pr.id) |
                    (Task.resulting_change_id == pr.source_change_id)
                )
            )
            if origin_task:
                task_id = origin_task.id
                task_title = origin_task.title
                agent_id = origin_task.assigned_agent_id or agent_id
                session_id = origin_task.claimed_by_session_id
            
            if not session_id and change:
                try:
                    c_meta = json.loads(change.metadata_json or "{}")
                    session_id = c_meta.get("agent_session_id")
                except Exception:
                    pass

            agent_rec = self.db.scalar(select(Agent).where(Agent.id == agent_id)) if agent_id else None
            if agent_rec:
                agent_name = agent_rec.name

            if not origin_task:
                failed.append("Agent-created PR is missing required linkage to an originating SUTRA Task.")
            elif not agent_rec:
                failed.append("Originating Agent identity could not be resolved in the SUTRA registry.")
            else:
                # Check historical session governance: session existed and was associated with task/change
                if session_id:
                    session_rec = self.db.scalar(select(AgentSession).where(AgentSession.id == session_id))
                    if not session_rec:
                        warnings.append("Historical AgentSession record could not be located.")
                provenance_verified = True
                passed.append(f"Agent provenance verified (Agent: {agent_name or agent_id}, Session: #{session_id[:8] if session_id else 'N/A'}, Task: #{task_id[:8] if task_id else 'N/A'}).")
        else:
            # Human author
            user_rec = self.db.scalar(select(User).where(User.id == pr.author_id))
            if user_rec or (author_actor and author_actor.type in ("human", "user")):
                provenance_verified = True
                passed.append(f"Human author provenance verified ({user_rec.username if user_rec else pr.author_id}).")
            else:
                failed.append("PR author identity could not be resolved.")

        # =================================================================
        # 3. CI REQUIREMENTS & AUTOMATED CHECKS
        # =================================================================
        checks_data = self.ci_service.get_pr_checks(pr.id)
        ci_summary = checks_data.get("summary", {})
        ci_total = ci_summary.get("total", 0)
        ci_passed = ci_summary.get("passed", 0)
        ci_failed = ci_summary.get("failed", 0)
        ci_running = ci_summary.get("running", 0)
        ci_pending = ci_summary.get("pending", 0)

        effective_branch_rule = self.branch_service.get_effective_rule(repo.id, pr.target_branch)
        require_ci_rule = getattr(effective_branch_rule, "require_ci_passed", False) if effective_branch_rule else False
        repo_policies = (repo.settings or {}).get("policies", {})
        ci_required = require_ci_rule or repo_policies.get("require_ci_passed", False)

        ci_status = "none"
        if ci_failed > 0:
            ci_status = "failed"
            failing_check_names = [c["name"] for c in checks_data.get("checks", []) if c.get("sutra_state") in ("failed", "failure")]
            failed.append(f"Required CI check(s) failed: {', '.join(failing_check_names) if failing_check_names else 'Check failure'}.")
        elif ci_running > 0 or ci_pending > 0:
            if ci_required:
                ci_status = "running"
                failed.append("Automated CI checks are still running or pending.")
            else:
                ci_status = "passed"
                passed.append("Automated CI checks in progress; not configured as a blocking policy gate.")
        elif ci_total == 0:
            ci_status = "no_ci_file"
            passed.append("No CI workflow file found in codebase. Automated checks waived; PR merge is not blocked.")
        else:
            ci_status = "passed"
            passed.append(f"All automated CI checks passed ({ci_passed}/{ci_total}).")

        # =================================================================
        # 4. POLICY RULES & BRANCH PROTECTION GATES
        # =================================================================
        policy_passed = True
        risk_level = change.risk_level if change else "low"
        conflict_level = "none"

        if change:
            policy_decision = self.change_policy_service.evaluate(change)
            conflict_level = policy_decision.conflict_level
            if policy_decision.decision == ChangePolicyService.BLOCK:
                policy_passed = False
                failed.append(f"Change policy violation: {policy_decision.reason}")
            elif policy_decision.decision == ChangePolicyService.REVIEW:
                if risk_level in ("high", "critical"):
                    warnings.append(f"Change flagged with {risk_level.upper()} risk: requires explicit human review.")

            # Git Conflict check
            conflict_res = ConflictService(self.db).analyze(change)
            if conflict_res.level == ConflictService.LEVEL_CONFLICT:
                policy_passed = False
                failed.append("Git detected an actual merge conflict with the target branch.")
            elif conflict_res.level == ConflictService.LEVEL_POTENTIAL:
                warnings.append("Git conflict analysis detected potential overlapping modifications.")

        # Branch Protection Gate evaluation
        branch_failed_gates: List[str] = []
        required_approvals = 1
        if effective_branch_rule:
            required_approvals = effective_branch_rule.required_approvals
            bp_eval = self.branch_service.evaluate_pull_request(pr.id)
            if not bp_eval["passed"]:
                for gate in bp_eval.get("failed_gates", []):
                    if gate not in ("missing_change_review", "insufficient_approvals", "missing_or_failed_ci"):
                        branch_failed_gates.append(gate)
                        policy_passed = False
                        failed.append(f"Branch protection gate failed: {gate.replace('_', ' ')}.")
        else:
            # Check organization governance policy if exists
            org_id = getattr(repo, "organization_id", None)
            if org_id:
                org_policy = self.db.get(GovernancePolicy, org_id)
                if org_policy:
                    required_approvals = org_policy.minimum_pr_approvals

        # Check repository-configured PR policies
        repo_policies = (repo.settings or {}).get("policies", {})
        if repo_policies.get("min_approvals"):
            try:
                min_appr = int(repo_policies["min_approvals"])
                if min_appr > required_approvals:
                    required_approvals = min_appr
            except (ValueError, TypeError):
                pass

        if repo_policies.get("require_task_linkage"):
            if not task_id:
                policy_passed = False
                failed.append("Repository policy requires pull request to be linked to an active SUTRA Task.")
            else:
                passed.append(f"Repository policy satisfied: Linked to SUTRA Task #{task_id[:8]}.")

        if repo_policies.get("enforce_governed_provenance"):
            if not provenance_verified:
                policy_passed = False
                failed.append("Repository policy requires verified SUTRA author/agent provenance.")
            else:
                passed.append("Repository policy satisfied: SUTRA provenance verified.")

        if repo_policies.get("require_ci_passed") and not (effective_branch_rule and getattr(effective_branch_rule, "require_ci_passed", False)):
            if ci_status != "passed":
                policy_passed = False
                failed.append("Repository policy requires all automated CI checks to pass.")
            else:
                passed.append("Repository policy satisfied: Automated CI checks passed.")

        if repo_policies.get("require_agent_review") and not (effective_branch_rule and effective_branch_rule.require_agent_review):
            agent_svc = AgentReviewService(self.db)
            summary = agent_svc.get_agent_review_summary(pr.id, pr.author_id, is_agent=False)
            if summary.get("total_findings", 0) == 0 and summary.get("participating_agents_count", 0) == 0:
                policy_passed = False
                failed.append("Repository policy requires automated AI agent review.")
            else:
                passed.append("Repository policy satisfied: AI agent review participated.")

        if repo_policies.get("require_no_blocking_findings") and not (effective_branch_rule and effective_branch_rule.require_no_blocking_agent_findings):
            agent_svc = AgentReviewService(self.db)
            summary = agent_svc.get_agent_review_summary(pr.id, pr.author_id, is_agent=False)
            crit = summary.get("severity_distribution", {}).get("critical", 0)
            high = summary.get("severity_distribution", {}).get("high", 0)
            if crit > 0 or high > 0:
                policy_passed = False
                failed.append(f"Repository policy failed: {crit + high} unresolved critical/high agent findings.")
            else:
                passed.append("Repository policy satisfied: Zero blocking agent findings.")

        if policy_passed and not branch_failed_gates:
            passed.append("Change risk, conflict, and repository policies satisfied.")

        # =================================================================
        # 5. REVIEW REQUIREMENTS & CRITICAL SELF-REVIEW RULE
        # =================================================================
        reviews = self.db.scalars(
            select(ChangeReview).where(
                ChangeReview.change_id == pr.source_change_id,
                ChangeReview.status == "approved",
            )
        ).all()

        # Enforce Critical Self-Review Rule: Agent or author can NEVER approve their own work
        valid_reviews: List[ChangeReview] = []
        self_approval_prevented = False
        author_ids = {pr.author_id}
        if change:
            author_ids.add(change.actor_id)
        if agent_id:
            author_ids.add(agent_id)

        # HEAD SHA Safety: Invalidate approvals if PR HEAD has changed
        change_meta = {}
        if change and change.metadata_json:
            try:
                change_meta = json.loads(change.metadata_json)
            except Exception:
                pass
        reviewed_head_shas = change_meta.get("reviewed_head_shas", {})
        approved_head_sha = change_meta.get("approved_head_sha")

        for r in reviews:
            review_head = reviewed_head_shas.get(r.id, approved_head_sha)
            if r.reviewer_id in author_ids:
                self_approval_prevented = True
                warnings.append("Self-approval by author/agent is strictly prohibited and was excluded from approval count.")
            elif head_sha and review_head and review_head != head_sha:
                warnings.append(
                    f"Review by {r.reviewer_id[:8]} was approved for earlier commit {review_head[:8]} "
                    f"and does not authorize current HEAD {head_sha[:8]}. Fresh review required."
                )
            elif head_sha and not review_head:
                warnings.append(
                    f"Review by {r.reviewer_id[:8]} lacks commit binding for current HEAD {head_sha[:8]}. Fresh review required."
                )
            else:
                valid_reviews.append(r)

        unique_reviewers = {r.reviewer_id for r in valid_reviews if r.reviewer_id}
        actual_approvals = len(unique_reviewers)
        review_satisfied = (actual_approvals >= required_approvals)

        if head_sha and approved_head_sha and approved_head_sha != head_sha:
            warnings.append(
                f"Previous approval was for commit {approved_head_sha[:8]}; new commit {head_sha[:8]} requires fresh review."
            )
            review_satisfied = False
        elif head_sha and not approved_head_sha and pr.status == PullRequest.STATUS_APPROVED:
            warnings.append(
                f"PR approval is not bound to current HEAD commit {head_sha[:8]}. Fresh review required."
            )
            review_satisfied = False

        if review_satisfied:
            passed.append(f"Required reviews satisfied ({actual_approvals}/{required_approvals} approvals).")
        else:
            if required_approvals > 0:
                failed.append(f"Required reviews not satisfied: {actual_approvals} of {required_approvals} approvals recorded.")

        # =================================================================
        # 6. VERDICT DETERMINATION
        # =================================================================
        verdict = GovernanceVerdict.READY_FOR_APPROVAL

        # Priority 1: CI Blockers
        if ci_status == "failed":
            verdict = GovernanceVerdict.BLOCKED
        elif ci_status == "running":
            verdict = GovernanceVerdict.CI_PENDING
        elif ci_status == "missing" and require_ci_rule:
            verdict = GovernanceVerdict.BLOCKED

        # Priority 2: Change / Policy / Conflict Blockers
        elif not change or not change.resulting_commit or (pr.source_commit and change.resulting_commit and pr.source_commit != change.resulting_commit):
            verdict = GovernanceVerdict.BLOCKED
        elif not policy_passed:
            verdict = GovernanceVerdict.POLICY_FAILED
        elif not provenance_verified:
            verdict = GovernanceVerdict.BLOCKED

        # Priority 3: Review / Approval Requirements
        elif not review_satisfied:
            verdict = GovernanceVerdict.NEEDS_REVIEW
        elif pr.status in (PullRequest.STATUS_APPROVED, PullRequest.STATUS_MERGED):
            verdict = GovernanceVerdict.READY_FOR_MERGE
        else:
            verdict = GovernanceVerdict.READY_FOR_APPROVAL

        ready_for_approval = (verdict in (GovernanceVerdict.READY_FOR_APPROVAL, GovernanceVerdict.READY_FOR_MERGE))
        ready_for_merge = (verdict == GovernanceVerdict.READY_FOR_MERGE)

        # =================================================================
        # 7. AUDIT LOGGING
        # =================================================================
        if record_audit:
            self._record_governance_audit(
                pr=pr,
                verdict=verdict,
                ready_for_approval=ready_for_approval,
                head_sha=head_sha,
                actor_id=actor_id or pr.author_id,
                passed=passed,
                failed=failed,
                warnings=warnings,
            )

        return {
            "pull_request_id": pr.id,
            "repository_id": repo.id,
            "verdict": verdict,
            "ready_for_approval": ready_for_approval,
            "ready_for_merge": ready_for_merge,
            "eligible_for_merge": ready_for_merge,
            "head_sha": head_sha,
            "evaluated_at": datetime.now(timezone.utc).isoformat(),
            "passed": passed,
            "failed": failed,
            "warnings": warnings,
            "checks": {
                "verdict": checks_data.get("governance_verdict"),
                "overall_status": checks_data.get("overall_status"),
                "total": ci_total,
                "passed": ci_passed,
                "failed": ci_failed,
                "running": ci_running,
                "pending": ci_pending,
                "required_passed": (ci_failed == 0 and ci_running == 0 and (ci_total > 0 or not require_ci_rule)),
            },
            "provenance": {
                "verified": provenance_verified,
                "actor_type": "agent" if is_agent_author else "human",
                "agent_id": agent_id,
                "agent_name": agent_name,
                "session_id": session_id,
                "task_id": task_id,
                "task_title": task_title,
                "resulting_commit": change.resulting_commit if change else None,
            },
            "policy": {
                "passed": policy_passed,
                "risk_level": risk_level,
                "conflict_level": conflict_level,
                "branch_rule_matched": effective_branch_rule is not None,
                "branch_pattern": effective_branch_rule.branch_pattern if effective_branch_rule else None,
                "failed_gates": branch_failed_gates,
                "repo_policies": repo_policies,
            },
            "review": {
                "satisfied": review_satisfied,
                "required_approvals": required_approvals,
                "actual_approvals": actual_approvals,
                "self_approval_prevented": self_approval_prevented,
                "reviewers": sorted(list(unique_reviewers)),
            },
        }

    def _authorize_actor_access(self, actor_id: str, repository: Repository) -> None:
        if repository.owner_id == actor_id:
            return

        actor = self.db.scalar(select(Actor).where(Actor.id == actor_id))
        if not actor:
            user = self.db.scalar(select(User).where(User.id == actor_id))
            if not user:
                raise PermissionError("User or actor not found")
            actor = Actor(
                id=actor_id,
                owner_id=actor_id,
                type="human",
                name=user.username,
                capabilities='["repository.read", "change.review"]',
            )
            self.db.add(actor)
            self.db.flush()

        if repository.visibility == "private":
            auth_res = AuthorizationService.check(
                actor,
                repository,
                AuthorizationService.READ,
                db=self.db,
            )
            if not auth_res.allowed:
                raise PermissionError("Actor does not have access to this repository")

    def _record_governance_audit(
        self,
        pr: PullRequest,
        verdict: str,
        ready_for_approval: bool,
        head_sha: str,
        actor_id: str,
        passed: List[str],
        failed: List[str],
        warnings: List[str],
    ) -> ChangeEvent:
        """
        Records an immutable audit event for the governance evaluation, sanitized
        so that tokens and credentials cannot leak into persistent audit tables.
        """
        audit_meta = {
            "pull_request_id": pr.id,
            "repository_id": pr.repository_id,
            "verdict": verdict,
            "ready_for_approval": ready_for_approval,
            "head_sha": head_sha,
            "passed_rules_count": len(passed),
            "failed_rules_count": len(failed),
            "warnings_count": len(warnings),
            "failed_reasons": failed[:10],
        }

        event = ChangeEvent(
            change_id=pr.source_change_id,
            actor_id=actor_id,
            event_type="pull_request.governance_evaluated",
            from_status=None,
            to_status=verdict,
            reason=failed[0] if failed else "Governance evaluated successfully",
            metadata_json=json.dumps(audit_meta, separators=(",", ":"), sort_keys=True),
        )
        self.db.add(event)
        self.db.flush()
        return event

    def _get_default_github_provider(self) -> Optional[RepositoryProvider]:
        if getattr(settings, "github_app_id", None) and getattr(settings, "github_private_key_pem", None):
            try:
                from app.providers.github.auth import GitHubAppAuthService
                from app.providers.github.repository import GitHubRepositoryProvider

                auth_svc = GitHubAppAuthService(
                    app_id=settings.github_app_id,
                    private_key_pem=settings.github_private_key_pem,
                    base_url=settings.github_api_base_url,
                )
                return GitHubRepositoryProvider(auth_service=auth_svc, base_url=settings.github_api_base_url)
            except Exception as e:
                logger.warning(f"Failed to instantiate default GitHub provider: {e}")
        return None

    def sync_governance_check_to_github(
        self,
        pull_request_id: str,
        evaluation_result: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Synchronizes authoritative SUTRA Governance status as a GitHub check run
        named 'SUTRA Governance' on the PR HEAD commit.
        """
        pr = self.db.scalar(select(PullRequest).where(PullRequest.id == pull_request_id))
        if not pr:
            return None

        repo = self.db.scalar(
            select(Repository).where(
                Repository.id == pr.repository_id,
                Repository.deleted_at.is_(None),
            )
        )
        if not repo or repo.provider_type != "github" or not repo.provider_owner:
            return None

        head_sha = pr.source_commit
        if not head_sha:
            change = self.db.scalar(select(Change).where(Change.id == pr.source_change_id))
            head_sha = change.resulting_commit if change else None

        if not head_sha:
            return None

        eval_res = evaluation_result or self.evaluate_pull_request(pr.id, record_audit=False)
        verdict = eval_res.get("verdict")
        failed_reasons = eval_res.get("failed", [])

        if verdict == GovernanceVerdict.READY_FOR_MERGE:
            status_val = "completed"
            conclusion_val = "success"
            title = "SUTRA Governance: PASS"
            summary = "All governance policies, provenance verification, required reviews, and CI gates passed."
        elif verdict in (GovernanceVerdict.BLOCKED, GovernanceVerdict.CI_FAILED, GovernanceVerdict.POLICY_FAILED):
            status_val = "completed"
            conclusion_val = "failure"
            title = f"SUTRA Governance: {verdict}"
            summary = "; ".join(failed_reasons) if failed_reasons else f"Governance policy check failed ({verdict})."
        else:
            status_val = "in_progress"
            conclusion_val = None
            title = f"SUTRA Governance: {verdict}"
            summary = "Governance check in progress. Awaiting required independent human review or pending automated CI."

        provider = self.provider or self._get_default_github_provider()
        if not provider or not hasattr(provider, "create_check_run"):
            return None

        try:
            return provider.create_check_run(
                owner=repo.provider_owner,
                name=repo.name,
                check_name="SUTRA Governance",
                head_sha=head_sha,
                status=status_val,
                conclusion=conclusion_val,
                title=title,
                summary=summary,
                details_url=f"{settings.sutra_base_url}/repositories/{repo.slug}/pulls/{pr.id}",
            )
        except Exception as e:
            logger.warning(f"Could not synchronize SUTRA Governance check run to GitHub: {e}")
            return None
