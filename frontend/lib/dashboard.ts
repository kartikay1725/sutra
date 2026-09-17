import { apiAuth } from "./api";
import { clientCache, CACHE_TTL } from "./cache";

export interface DashboardActivity {
  id: string;
  actor_name: string;
  action: string;
  target: string;
  repo_name: string;
  created_at: string;
}

export interface DashboardData {
  repository_count: number;
  open_changes: number;
  changes_needing_review: number;
  blocked_changes?: number;
  blocked_tasks?: number;
  failed_ci_jobs?: number;
  agent_changes: number;
  human_changes: number;
  median_lead_time_minutes: number | null;
  active_agent_sessions: number;
  ci: {
    jobs_total: number;
    passed: number;
    failed: number;
    running: number;
    pass_rate: number | null;
  };
  security: {
    open_findings: number;
    critical: number;
    high: number;
    medium: number;
    low: number;
  };
  deployments: {
    total: number;
    successful: number;
    failed: number;
    running: number;
    last_status: string | null;
    last_created_at: string | null;
  };
  activity: DashboardActivity[];
}

export const dashboardService = {
  async get(options?: { forceRefresh?: boolean }): Promise<DashboardData> {
    return clientCache.fetch<DashboardData>(
      "overview:workspace_dashboard",
      () => apiAuth<DashboardData>("/v1/me/dashboard"),
      {
        ...CACHE_TTL.OVERVIEW,
        forceRefresh: options?.forceRefresh,
      }
    );
  },
};

