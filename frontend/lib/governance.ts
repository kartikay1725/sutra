import { apiAuth } from "./api";

export interface GovernanceEvaluation {
  pull_request_id: string;
  repository_id: string;
  verdict: "READY_FOR_APPROVAL" | "BLOCKED" | "NEEDS_REVIEW" | "CI_PENDING" | "CI_FAILED" | "POLICY_FAILED" | string;
  ready_for_approval: boolean;
  head_sha: string;
  evaluated_at: string;
  passed: string[];
  failed: string[];
  warnings: string[];
  checks: {
    verdict?: string | null;
    overall_status?: string | null;
    total: number;
    passed: number;
    failed: number;
    running: number;
    pending: number;
    required_passed: boolean;
  };
  provenance: {
    verified: boolean;
    actor_type: "agent" | "human" | string;
    agent_id?: string | null;
    agent_name?: string | null;
    session_id?: string | null;
    task_id?: string | null;
    task_title?: string | null;
    resulting_commit?: string | null;
  };
  policy: {
    passed: boolean;
    risk_level: string;
    conflict_level: string;
    branch_rule_matched: boolean;
    branch_pattern?: string | null;
    failed_gates: string[];
  };
  review: {
    satisfied: boolean;
    required_approvals: number;
    actual_approvals: number;
    self_approval_prevented: boolean;
    reviewers: string[];
  };
}

export const governanceService = {
  async getPRGovernance(pullRequestId: string): Promise<GovernanceEvaluation> {
    return apiAuth<GovernanceEvaluation>(`/v1/pull-requests/${pullRequestId}/governance`);
  },

  async evaluatePRGovernance(pullRequestId: string): Promise<GovernanceEvaluation> {
    return apiAuth<GovernanceEvaluation>(`/v1/pull-requests/${pullRequestId}/governance/evaluate`, {
      method: "POST",
    });
  },
};
