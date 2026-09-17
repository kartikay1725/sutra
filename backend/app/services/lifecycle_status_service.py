"""Canonical Engineering Lifecycle Status Service.

Aggregates Task -> AgentSession -> Change -> Commit -> PR -> CI -> Governance ->
Approval -> Merge -> Task completion into a single coherent lifecycle model consumed
by both the SUTRA MCP server and the SUTRA frontend.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
import logging
from typing import Any, Dict, List, Optional
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.actor import Actor
from app.models.agent import Agent
from app.models.agent_session import AgentSession
from app.models.change import Change
from app.models.change_review import ChangeReview
from app.models.pull_request import PullRequest
from app.models.repository import Repository
from app.models.task import Task
from app.models.user import User
from app.services.ci_service import CIService
from app.services.governance_service import GovernanceService, GovernanceVerdict

logger = logging.getLogger("sutra.services.lifecycle_status")


class LifecycleStage:
    TASK_CREATED = "task_created"
    TASK_ASSIGNED = "task_assigned"
    TASK_CLAIMED = "task_claimed"
    WORK_SUBMITTED = "work_submitted"
    PULL_REQUEST_OPENED = "pull_request_opened"
    CI_EVALUATING = "ci_evaluating"
    CI_FAILED = "ci_failed"
    GOVERNANCE_BLOCKED = "governance_blocked"
    AWAITING_HUMAN_APPROVAL = "awaiting_human_approval"
    READY_FOR_MERGE = "ready_for_merge"
    MERGED = "merged"
    TASK_COMPLETED = "task_completed"


class LifecycleOverallState:
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    BLOCKED_ON_CI = "blocked_on_ci"
    BLOCKED_ON_GOVERNANCE = "blocked_on_governance"
    AWAITING_HUMAN_APPROVAL = "awaiting_human_approval"
    READY_FOR_MERGE = "ready_for_merge"
    MERGED = "merged"
    COMPLETED = "completed"


class LifecycleNextActor:
    AGENT = "agent"
    HUMAN = "human"
    SYSTEM = "system"
    NONE = "none"


class LifecycleStatusService:
    """Canonical aggregation service for the governed engineering lifecycle.

    Resolves a coherent, authoritative lifecycle state for any engineering
    artifact (Task, Change, PullRequest) by joining across all SUTRA domains:
    Task → AgentSession → Change → Commit → PR → CI → Governance →
    Approval → Merge → Task completion.

    This service is the single source of truth consumed by:
    - The SUTRA MCP server (sutra_get_status tool)
    - The SUTRA frontend EngineeringTimeline component
    - The end-to-end governed workflow integration tests

    Agents and humans may only read lifecycle state through this service.
    State transitions are enforced by the individual domain services
    (CIService, GovernanceService, etc.) to preserve the 4-pillar governance
    policy: no code merges without CI passing, governance review, and explicit
    human approval.
    """

    def __init__(self, db: Session):
        self.db = db


    def get_lifecycle_status(
        self,
        task_id: Optional[str] = None,
        pull_request_id: Optional[str] = None,
        change_id: Optional[str] = None,
        actor_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Resolve and aggregate the authoritative engineering lifecycle state."""
        task: Optional[Task] = None
        change: Optional[Change] = None
        pr: Optional[PullRequest] = None
        repo: Optional[Repository] = None

        # 1. Bi-directional entity resolution
        if pull_request_id:
            pr = self.db.scalar(select(PullRequest).where(PullRequest.id == pull_request_id))
            if pr:
                change = self.db.scalar(select(Change).where(Change.id == pr.source_change_id))
                task = self.db.scalar(
                    select(Task).where(
                        (Task.resulting_pull_request_id == pr.id) |
                        (Task.resulting_change_id == pr.source_change_id)
                    )
                )
                repo = self.db.scalar(select(Repository).where(Repository.id == pr.repository_id))
        elif task_id:
            task = self.db.scalar(select(Task).where(Task.id == task_id))
            if task:
                if task.resulting_pull_request_id:
                    pr = self.db.scalar(select(PullRequest).where(PullRequest.id == task.resulting_pull_request_id))
                if task.resulting_change_id:
                    change = self.db.scalar(select(Change).where(Change.id == task.resulting_change_id))
                repo = self.db.scalar(select(Repository).where(Repository.id == task.repository_id))
        elif change_id:
            change = self.db.scalar(select(Change).where(Change.id == change_id))
            if change:
                pr = self.db.scalar(select(PullRequest).where(PullRequest.source_change_id == change.id))
                task = self.db.scalar(select(Task).where(Task.resulting_change_id == change.id))
                repo = self.db.scalar(select(Repository).where(Repository.id == change.repository_id))

        if not task and not change and not pr:
            return {
                "status": "not_found",
                "error": "No task, pull request, or change found matching the provided identifiers.",
            }

        # 2. Agent and Session attribution
        session: Optional[AgentSession] = None
        agent: Optional[Agent] = None
        if task and task.claimed_by_session_id:
            session = self.db.scalar(select(AgentSession).where(AgentSession.id == task.claimed_by_session_id))
        if session:
            agent = self.db.scalar(select(Agent).where(Agent.id == session.agent_id))
        elif task and task.assigned_agent_id:
            agent = self.db.scalar(select(Agent).where(Agent.id == task.assigned_agent_id))

        # 3. Resolve Change metadata
        change_meta: Dict[str, Any] = {}
        if change and change.metadata_json:
            try:
                change_meta = json.loads(change.metadata_json)
            except Exception:
                change_meta = {}

        # 4. Resolve CI & Governance
        ci_summary = {"total": 0, "passed": 0, "failed": 0, "pending": 0}
        checks_list: List[Dict[str, Any]] = []
        gov_verdict = "NOT_EVALUATED"
        ready_for_approval = False
        ready_for_merge = False
        passed_gates: List[str] = []
        failed_gates: List[str] = []
        warnings: List[str] = []

        if pr:
            ci_svc = CIService(self.db)
            ci_data = ci_svc.get_pr_checks(pr.id, actor_id=actor_id)
            ci_summary = ci_data.get("summary", ci_summary)
            checks_list = ci_data.get("checks", [])

            gov_svc = GovernanceService(self.db)
            gov_eval = gov_svc.evaluate_pull_request(pr.id, actor_id=actor_id, record_audit=False)
            gov_verdict = gov_eval.get("verdict", "NOT_EVALUATED")
            ready_for_approval = gov_eval.get("ready_for_approval", False)
            ready_for_merge = gov_eval.get("ready_for_merge", False)
            passed_gates = gov_eval.get("passed", [])
            failed_gates = gov_eval.get("failed", [])
            warnings = gov_eval.get("warnings", [])

        # 5. Resolve Human Approval State
        is_approved = False
        approved_by = change_meta.get("approved_by")
        approved_at = change_meta.get("approved_at")
        approved_head_sha = change_meta.get("approved_head_sha")

        if pr:
            if pr.status == PullRequest.STATUS_APPROVED:
                is_approved = True
            elif change:
                review = self.db.scalar(
                    select(ChangeReview)
                    .where(ChangeReview.change_id == change.id, ChangeReview.status == "approved")
                    .order_by(ChangeReview.created_at.desc())
                )
                if review:
                    is_approved = True
                    approved_by = approved_by or review.reviewer_id
                    approved_at = approved_at or review.created_at.isoformat()
                    # ChangeReview stores review identity and status; the commit
                    # binding is persisted in the change metadata.
                    approved_head_sha = approved_head_sha or change_meta.get("approved_head_sha")

        current_head = (pr.source_commit if pr else None) or (change.resulting_commit if change else None)
        head_changed_after_approval = bool(is_approved and approved_head_sha and current_head and approved_head_sha != current_head)

        # 6. Resolve Merge State
        is_merged = bool((pr and pr.status == PullRequest.STATUS_MERGED) or change_meta.get("merged"))
        merge_commit_sha = (pr.target_commit if pr else None) or change_meta.get("merge_commit_sha")
        merged_at = (pr.merged_at.isoformat() if pr and pr.merged_at else None) or change_meta.get("merged_at")
        merger_id = change_meta.get("merged_by")

        # 7. Compute Canonical Stage, State, Next Action, Next Actor, and Blockers
        current_stage = LifecycleStage.TASK_CREATED
        overall_state = LifecycleOverallState.PENDING
        next_action = "assign_task"
        next_actor = LifecycleNextActor.HUMAN
        blocked_reasons: List[str] = []

        if task and task.status == Task.STATUS_COMPLETED:
            current_stage = LifecycleStage.TASK_COMPLETED
            overall_state = LifecycleOverallState.COMPLETED
            next_action = "none"
            next_actor = LifecycleNextActor.NONE
        elif is_merged:
            current_stage = LifecycleStage.MERGED
            overall_state = LifecycleOverallState.MERGED
            next_action = "complete_task"
            next_actor = LifecycleNextActor.SYSTEM
        elif head_changed_after_approval:
            current_stage = LifecycleStage.AWAITING_HUMAN_APPROVAL
            overall_state = LifecycleOverallState.AWAITING_HUMAN_APPROVAL
            next_action = "human_approve"
            next_actor = LifecycleNextActor.HUMAN
            blocked_reasons.append("PR HEAD changed after previous human approval. Re-approval required for current HEAD.")
        elif ready_for_merge and is_approved and gov_verdict == GovernanceVerdict.READY_FOR_MERGE:
            current_stage = LifecycleStage.READY_FOR_MERGE
            overall_state = LifecycleOverallState.READY_FOR_MERGE
            next_action = "human_merge"
            next_actor = LifecycleNextActor.HUMAN
        elif pr:
            if ci_summary.get("failed", 0) > 0:
                current_stage = LifecycleStage.CI_FAILED
                overall_state = LifecycleOverallState.BLOCKED_ON_CI
                next_action = "fix_ci"
                next_actor = LifecycleNextActor.AGENT
                blocked_reasons.extend(failed_gates or [f"{ci_summary['failed']} CI check(s) failed."])
            elif gov_verdict in (GovernanceVerdict.BLOCKED, GovernanceVerdict.POLICY_FAILED):
                current_stage = LifecycleStage.GOVERNANCE_BLOCKED
                overall_state = LifecycleOverallState.BLOCKED_ON_GOVERNANCE
                next_action = "fix_governance"
                next_actor = LifecycleNextActor.AGENT
                blocked_reasons.extend(failed_gates or ["Governance policy check failed."])
            elif ci_summary.get("pending", 0) > 0:
                current_stage = LifecycleStage.CI_EVALUATING
                overall_state = LifecycleOverallState.IN_PROGRESS
                next_action = "wait_for_ci"
                next_actor = LifecycleNextActor.SYSTEM
            elif not is_approved:
                current_stage = LifecycleStage.AWAITING_HUMAN_APPROVAL
                overall_state = LifecycleOverallState.AWAITING_HUMAN_APPROVAL
                next_action = "human_approve"
                next_actor = LifecycleNextActor.HUMAN
                blocked_reasons.append("Awaiting independent human review and approval in SUTRA dashboard.")
            else:
                current_stage = LifecycleStage.PULL_REQUEST_OPENED
                overall_state = LifecycleOverallState.IN_PROGRESS
                next_action = "request_merge"
                next_actor = LifecycleNextActor.AGENT
        elif change and change.resulting_commit:
            current_stage = LifecycleStage.WORK_SUBMITTED
            overall_state = LifecycleOverallState.IN_PROGRESS
            next_action = "open_pull_request"
            next_actor = LifecycleNextActor.AGENT
        elif task:
            if task.status == Task.STATUS_IN_PROGRESS:
                current_stage = LifecycleStage.TASK_CLAIMED
                overall_state = LifecycleOverallState.IN_PROGRESS
                next_action = "submit_change"
                next_actor = LifecycleNextActor.AGENT
            elif task.status == Task.STATUS_ASSIGNED:
                current_stage = LifecycleStage.TASK_ASSIGNED
                overall_state = LifecycleOverallState.PENDING
                next_action = "claim_task"
                next_actor = LifecycleNextActor.AGENT
            else:
                current_stage = LifecycleStage.TASK_CREATED
                overall_state = LifecycleOverallState.PENDING
                next_action = "assign_task"
                next_actor = LifecycleNextActor.HUMAN

        # 8. Build Authoritative Timeline Nodes
        timeline: List[Dict[str, Any]] = []

        if task:
            timeline.append({
                "stage": LifecycleStage.TASK_CREATED,
                "title": "Task Created",
                "description": f"Task #{task.id[:8]} created: {task.title}",
                "status": "completed",
                "timestamp": task.created_at.isoformat() if task.created_at else None,
                "actor_type": "human",
                "actor_id": task.created_by,
            })

            if task.assigned_agent_id:
                timeline.append({
                    "stage": LifecycleStage.TASK_ASSIGNED,
                    "title": "Task Assigned",
                    "description": f"Assigned to Agent {agent.name if agent else task.assigned_agent_id[:8]}",
                    "status": "completed",
                    "timestamp": task.started_at.isoformat() if task.started_at else None,
                    "actor_type": "system",
                    "actor_id": task.assigned_agent_id,
                })

            if task.claimed_by_session_id:
                timeline.append({
                    "stage": LifecycleStage.TASK_CLAIMED,
                    "title": "Task Claimed",
                    "description": f"Exclusive execution lease locked under Session {task.claimed_by_session_id[:8]}",
                    "status": "completed",
                    "timestamp": session.created_at.isoformat() if session and session.created_at else None,
                    "actor_type": "agent",
                    "actor_id": agent.name if agent else (session.agent_id if session else "agent"),
                })

        if change and change.resulting_commit:
            commit_origin = change_meta.get("commit_origin", "unknown")
            is_governed = commit_origin == "sutra_governed"
            timeline.append({
                "stage": LifecycleStage.WORK_SUBMITTED,
                "title": "Governed Commit Recorded" if is_governed else "External Commit Observed",
                "description": (
                    f"Governed commit {change.resulting_commit[:8]} registered under SUTRA Change #{change.id[:8]}"
                    if is_governed else
                    f"Commit {change.resulting_commit[:8]} reconciled into Change #{change.id[:8]}"
                ),
                "status": "completed",
                "timestamp": change.created_at.isoformat() if change.created_at else None,
                "actor_type": "agent",
                "actor_id": agent.name if agent else "agent",
                "commit_sha": change.resulting_commit,
                "commit_origin": commit_origin,
            })

        if pr:
            gh_pr_num = change_meta.get("github_pr_number")
            pr_desc = f"Pull Request #{pr.id[:8]}"
            if gh_pr_num:
                pr_desc += f" (GitHub #{gh_pr_num})"
            pr_desc += f" targeting {pr.target_branch}"

            timeline.append({
                "stage": LifecycleStage.PULL_REQUEST_OPENED,
                "title": "Pull Request Created",
                "description": pr_desc,
                "status": "completed",
                "timestamp": pr.created_at.isoformat() if pr.created_at else None,
                "actor_type": "agent",
                "actor_id": agent.name if agent else "agent",
                "pull_request_id": pr.id,
                "pull_request_url": change_meta.get("github_html_url"),
            })

            # CI stage in timeline
            ci_status = "pending"
            if ci_summary.get("failed", 0) > 0:
                ci_status = "failed"
            elif ci_summary.get("total", 0) > 0 and ci_summary.get("pending", 0) == 0:
                ci_status = "passed"

            timeline.append({
                "stage": LifecycleStage.CI_EVALUATING,
                "title": "CI Automated Checks",
                "description": f"Passed: {ci_summary.get('passed', 0)}/{ci_summary.get('total', 0)} checks",
                "status": ci_status,
                "timestamp": None,
                "actor_type": "system",
                "actor_id": "CI Runner",
                "summary": ci_summary,
            })

            # Governance stage in timeline
            gov_status = "pending"
            if gov_verdict in (GovernanceVerdict.READY_FOR_APPROVAL, GovernanceVerdict.READY_FOR_MERGE):
                gov_status = "passed"
            elif gov_verdict in (GovernanceVerdict.BLOCKED, GovernanceVerdict.POLICY_FAILED, GovernanceVerdict.CI_FAILED):
                gov_status = "blocked"

            timeline.append({
                "stage": "governance_evaluation",
                "title": "SUTRA Governance Evaluation",
                "description": f"Governance verdict: {gov_verdict}",
                "status": gov_status,
                "timestamp": None,
                "actor_type": "system",
                "actor_id": "Governance Engine",
                "verdict": gov_verdict,
            })

            # Human Approval stage in timeline
            approval_status = "completed" if is_approved and not head_changed_after_approval else ("blocked" if head_changed_after_approval else "pending")
            timeline.append({
                "stage": LifecycleStage.AWAITING_HUMAN_APPROVAL,
                "title": "Human Review & Approval",
                "description": f"Approved by {approved_by}" if is_approved and not head_changed_after_approval else ("Approval invalidated: PR HEAD changed" if head_changed_after_approval else "Requires independent human repository owner approval"),
                "status": approval_status,
                "timestamp": approved_at,
                "actor_type": "human",
                "actor_id": approved_by,
            })

            # Governed Merge stage in timeline
            merge_status = "completed" if is_merged else ("active" if ready_for_merge and is_approved else "pending")
            timeline.append({
                "stage": LifecycleStage.MERGED,
                "title": "Governed Substrate Merge",
                "description": f"Merged commit {merge_commit_sha[:8]}" if is_merged and merge_commit_sha else "Awaiting human-authorized substrate merge",
                "status": merge_status,
                "timestamp": merged_at,
                "actor_type": "human",
                "actor_id": merger_id or approved_by,
                "merge_commit_sha": merge_commit_sha,
            })

        if task:
            timeline.append({
                "stage": LifecycleStage.TASK_COMPLETED,
                "title": "Task Completed",
                "description": f"Task #{task.id[:8]} marked completed after verified substrate merge",
                "status": "completed" if task.status == Task.STATUS_COMPLETED else "pending",
                "timestamp": task.completed_at.isoformat() if task.completed_at else None,
                "actor_type": "system",
                "actor_id": "SUTRA Control Plane",
            })

        # 9. Return Unified Canonical Lifecycle Representation
        return {
            "status": "success",
            "pull_request_id": pr.id if pr else None,
            "task_id": task.id if task else None,
            "change_id": change.id if change else None,
            "pr_status": pr.status if pr else None,
            "target_branch": pr.target_branch if pr else None,
            "head_commit": pr.source_commit if pr else None,
            "governance_verdict": gov_verdict,
            "ready_for_approval": ready_for_approval,
            "ready_for_merge": ready_for_merge,
            "passed_gates": passed_gates,
            "blocking_reasons": blocked_reasons,
            "warnings": warnings,
            "ci_summary": ci_summary,
            "checks": [
                {
                    "name": c.get("name"),
                    "status": c.get("status"),
                    "conclusion": c.get("conclusion"),
                    "sutra_state": c.get("sutra_state"),
                    "details_url": c.get("details_url") or c.get("html_url"),
                }
                for c in checks_list
            ],
            "current_stage": current_stage,
            "overall_state": overall_state,
            "blocked_reasons": blocked_reasons,
            "next_action": next_action,
            "next_actor": next_actor,
            "current_head_sha": current_head,
            "task": {
                "id": task.id if task else None,
                "title": task.title if task else None,
                "status": task.status if task else None,
                "priority": task.priority if task else None,
                "task_type": task.task_type if task else None,
                "repository_id": task.repository_id if task else None,
                "repository_slug": repo.slug if repo else None,
                "assigned_agent_id": task.assigned_agent_id if task else None,
                "claimed_by_session_id": task.claimed_by_session_id if task else None,
                "lease_expires_at": task.lease_expires_at.isoformat() if task and task.lease_expires_at else None,
                "created_at": task.created_at.isoformat() if task and task.created_at else None,
                "completed_at": task.completed_at.isoformat() if task and task.completed_at else None,
            } if task else None,
            "agent": {
                "id": agent.id if agent else None,
                "name": agent.name if agent else None,
                "session_id": session.id if session else (task.claimed_by_session_id if task else None),
                "status": agent.status if agent else None,
            } if agent or session else None,
            "change": {
                "id": change.id if change else None,
                "intent": change.intent if change else None,
                "status": change.status if change else None,
                "branch": change_meta.get("branch"),
                "base_branch": change_meta.get("base_branch"),
                "resulting_commit": change.resulting_commit if change else None,
                "created_at": change.created_at.isoformat() if change and change.created_at else None,
            } if change else None,
            "pull_request": {
                "id": pr.id if pr else None,
                "number": change_meta.get("github_pr_number"),
                "html_url": change_meta.get("github_html_url"),
                "title": pr.title if pr else None,
                "status": pr.status if pr else None,
                "target_branch": pr.target_branch if pr else None,
                "source_commit": pr.source_commit if pr else None,
                "target_commit": pr.target_commit if pr else None,
                "created_at": pr.created_at.isoformat() if pr and pr.created_at else None,
                "merged_at": pr.merged_at.isoformat() if pr and pr.merged_at else None,
            } if pr else None,
            "ci": {
                "summary": ci_summary,
                "checks": [
                    {
                        "name": c.get("name"),
                        "status": c.get("status"),
                        "conclusion": c.get("conclusion"),
                        "sutra_state": c.get("sutra_state"),
                        "details_url": c.get("details_url") or c.get("html_url"),
                    }
                    for c in checks_list
                ],
            },
            "governance": {
                "verdict": gov_verdict,
                "ready_for_approval": ready_for_approval,
                "ready_for_merge": ready_for_merge,
                "passed_gates": passed_gates,
                "failed_gates": failed_gates,
                "warnings": warnings,
            },
            "approval": {
                "is_approved": is_approved,
                "approved_by": approved_by,
                "approved_at": approved_at,
                "approved_head_sha": approved_head_sha,
                "head_changed_after_approval": head_changed_after_approval,
            },
            "merge": {
                "is_merged": is_merged,
                "merge_commit_sha": merge_commit_sha,
                "merged_at": merged_at,
                "merger_id": merger_id,
            },
            "timeline": timeline,
        }
