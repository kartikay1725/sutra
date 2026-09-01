import { apiAuth } from "./api";

export interface InsightsData {
  deployments_per_week: number;
  lead_time_minutes: number;
  ci_pass_rate: number;
  agent_changes_percent: number;
  human_changes_percent: number;
  agent_lead_time_minutes: number;
  human_lead_time_minutes: number;
  actionable_signal: string;
  actionable_signal_details: string;
}

export const insightsService = {
  async getInsights(username: string, repo: string): Promise<InsightsData> {
    return apiAuth<InsightsData>(`/v1/repositories/${username}/${repo}/insights`);
  }
};
