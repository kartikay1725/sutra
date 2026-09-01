import { apiAuth } from "./api";

export interface MyWorkItem {
  id: string;
  title: string;
  type: string;
  repo_name: string;
  status: string;
  updated_at: string;
}

export interface ActivityItem {
  id: string;
  actor_name: string;
  action: string;
  target: string;
  repo_name: string;
  created_at: string;
}

export interface StatsItem {
  ci_pass_rate: number;
  ci_jobs_total: number;
  agent_changes: number;
  human_changes: number;
  median_lead_time_minutes: number;
  security_findings: number;
}

export const meService = {
  async getWork(): Promise<MyWorkItem[]> {
    return apiAuth<MyWorkItem[]>("/v1/me/work");
  },

  async reorderWork(taskIds: string[]): Promise<void> {
    return apiAuth<void>("/v1/me/work/reorder", {
      method: "POST",
      body: JSON.stringify({ task_ids: taskIds })
    });
  },

  async getActivity(): Promise<ActivityItem[]> {
    return apiAuth<ActivityItem[]>("/v1/me/activity");
  },

  async getStats(): Promise<StatsItem> {
    return apiAuth<StatsItem>("/v1/me/stats");
  }
};
