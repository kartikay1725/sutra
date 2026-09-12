import { apiAuth, apiPublic } from "./api";

export type LifecycleStage =
  | "task_created"
  | "task_assigned"
  | "task_claimed"
  | "work_submitted"
  | "pull_request_opened"
  | "ci_evaluating"
  | "ci_passed"
  | "ci_failed"
  | "governance_evaluating"
  | "governance_passed"
  | "governance_blocked"
  | "awaiting_human_approval"
  | "ready_for_merge"
  | "merged"
  | "task_completed"
  | "TASK_CREATED"
  | "TASK_ASSIGNED"
  | "TASK_CLAIMED"
  | "WORK_SUBMITTED"
  | "PULL_REQUEST_OPENED"
  | "CI_EVALUATING"
  | "CI_PASSED"
  | "CI_FAILED"
  | "GOVERNANCE_BLOCKED"
  | "AWAITING_HUMAN_APPROVAL"
  | "READY_FOR_MERGE"
  | "MERGED"
  | "TASK_COMPLETED"
  | string;

export type LifecycleOverallState =
  | "pending"
  | "in_progress"
  | "blocked_on_ci"
  | "blocked_on_governance"
  | "awaiting_human_approval"
  | "ready_for_merge"
  | "merged"
  | "completed"
  | "PENDING"
  | "IN_PROGRESS"
  | "ACTIVE"
  | "BLOCKED_ON_CI"
  | "BLOCKED_ON_GOVERNANCE"
  | "AWAITING_HUMAN_APPROVAL"
  | "READY_FOR_MERGE"
  | "MERGED"
  | "COMPLETED"
  | string;

export type LifecycleNextActor = "HUMAN" | "AGENT" | "SYSTEM" | "NONE";

export interface TimelineNode {
  stage: string;
  label: string;
  status: "completed" | "active" | "pending" | "blocked" | "failed";
  timestamp: string | null;
  actor_type: "human" | "agent" | "system";
  actor_id: string | null;
  details: Record<string, any>;
}

export interface LifecycleStatusResponse {
  current_stage: LifecycleStage;
  overall_state: LifecycleOverallState;
  next_action: string;
  next_actor: LifecycleNextActor;
  blocked_reasons: string[];
  timeline: TimelineNode[];
  task?: {
    id: string;
    status: string;
    title: string;
    priority: string;
    assigned_agent_id: string | null;
    claimed_by_session_id: string | null;
  } | null;
  session?: {
    id: string;
    agent_id: string;
    status: string;
    lease_expires_at: string | null;
  } | null;
  change?: {
    id: string;
    status: string;
    commit_sha: string | null;
    base_commit: string | null;
    branch: string | null;
    intent: string | null;
  } | null;
  pull_request?: {
    id: string;
    status: string;
    title: string;
    source_branch: string | null;
    target_branch: string | null;
    source_commit: string | null;
    target_commit: string | null;
    merged_at: string | null;
    merged_by: string | null;
  } | null;
  ci?: {
    status: string;
    summary: {
      total: number;
      passed: number;
      failed: number;
      pending: number;
    };
    checks: Array<{
      id: string;
      name: string;
      status: string;
      conclusion: string | null;
    }>;
  } | null;
  governance?: {
    verdict: string;
    passed: boolean;
    blocking_reasons: string[];
  } | null;
  approval?: {
    is_approved: boolean;
    required_approvals: number;
    current_approvals: number;
    approved_by: string[];
    head_changed_after_approval: boolean;
  } | null;
  merge?: {
    is_merged: boolean;
    can_merge: boolean;
    blocking_reasons: string[];
    merge_commit_sha: string | null;
  } | null;
  task_completion?: {
    is_completed: boolean;
    completed_at: string | null;
  } | null;
  // Backward-compatible fields
  pull_request_id?: string | null;
  task_id?: string | null;
  change_id?: string | null;
  governance_verdict?: string | null;
  ready_for_merge?: boolean;
  eligible_for_merge?: boolean;
}

export const lifecycleService = {
  async getStatus(params: {
    taskId?: string;
    pullRequestId?: string;
    changeId?: string;
  }): Promise<LifecycleStatusResponse> {
    const query = new URLSearchParams();
    if (params.taskId) query.set("task_id", params.taskId);
    if (params.pullRequestId) query.set("pull_request_id", params.pullRequestId);
    if (params.changeId) query.set("change_id", params.changeId);

    const queryString = query.toString();
    const endpoint = `/v1/lifecycle/status${queryString ? `?${queryString}` : ""}`;
    return apiAuth<LifecycleStatusResponse>(endpoint);
  },
};
