import { apiAuth } from "./api";

export interface BranchProtectionRule {
  id: string;
  repository_id: string;
  branch_pattern: string;
  enabled: boolean;
  required_approvals: number;
  require_change_review: boolean;
  require_clean_conflict: boolean;
  require_resolved_threads: boolean;
  require_agent_review: boolean;
  require_no_blocking_agent_findings: boolean;
  allow_author_self_approval: boolean;
  require_ci_passed: boolean;
  created_by: string;
  updated_by: string;
  created_at: string;
  updated_at: string;
}

export type BranchProtectionWrite = Omit<
  BranchProtectionRule,
  "id" | "repository_id" | "created_by" | "updated_by" | "created_at" | "updated_at"
>;

export const branchProtectionService = {
  async list(repositoryId: string): Promise<BranchProtectionRule[]> {
    return apiAuth(`/v1/repositories/${repositoryId}/branch-protection`);
  },

  async create(repositoryId: string, payload: BranchProtectionWrite): Promise<BranchProtectionRule> {
    return apiAuth(`/v1/repositories/${repositoryId}/branch-protection`, {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  async update(repositoryId: string, ruleId: string, payload: Partial<BranchProtectionWrite>): Promise<BranchProtectionRule> {
    return apiAuth(`/v1/repositories/${repositoryId}/branch-protection/${ruleId}`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    });
  },

  async remove(repositoryId: string, ruleId: string): Promise<void> {
    await apiAuth(`/v1/repositories/${repositoryId}/branch-protection/${ruleId}`, { method: "DELETE" });
  },
};
