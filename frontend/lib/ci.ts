import { apiAuth } from "./api";

export interface CIJob {
  id: string;
  pull_request_id: string;
  repository_id: string;
  change_id: string;
  commit_sha: string;
  target_branch: string;
  status: string; // "pending" | "running" | "passed" | "failed" | "cancelled"
  trigger: string; // "manual" | "pr_opened" | "pr_updated" etc.
  runner_type: string;
  exit_code: number | null;
  failure_reason: string | null;
  worker_id: string | null;
  started_at: string | null;
  completed_at: string | null;
  cancelled_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface CILog {
  job_id: string;
  status: string;
  output_log: string | null;
}

export const ciService = {
  /** List all CI jobs for a given Pull Request. */
  async listJobsForPR(prId: string): Promise<CIJob[]> {
    return apiAuth<CIJob[]>(`/v1/pull-requests/${prId}/ci`);
  },

  /** Get a single CI job. */
  async getJob(prId: string, jobId: string): Promise<CIJob> {
    return apiAuth<CIJob>(`/v1/pull-requests/${prId}/ci/${jobId}`);
  },

  /** Get raw log output for a CI job. */
  async getLogs(prId: string, jobId: string): Promise<CILog> {
    return apiAuth<CILog>(`/v1/pull-requests/${prId}/ci/${jobId}/logs`);
  },

  /** Cancel a running CI job. */
  async cancelJob(prId: string, jobId: string): Promise<CIJob> {
    return apiAuth<CIJob>(`/v1/pull-requests/${prId}/ci/${jobId}/cancel`, {
      method: "POST",
    });
  },

  /** Trigger a new CI run for a Pull Request. */
  async triggerRun(prId: string): Promise<CIJob> {
    return apiAuth<CIJob>(`/v1/pull-requests/${prId}/ci`, {
      method: "POST",
    });
  },

  /** List CI pipelines for a repository. */
  async listPipelines(username: string, repo: string): Promise<any[]> {
    try {
      return await apiAuth<any[]>(`/v1/repositories/${username}/${repo}/ci`);
    } catch {
      return [];
    }
  },
};
