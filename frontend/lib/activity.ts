import { apiAuth } from "./api";

export interface ActivityActor {
  id: string;
  name: string;
  type: "human" | "agent" | "system";
}

export interface ActivityEntry {
  id: string;
  timestamp: string;
  action: string;
  category: string;
  resource_type: string;
  resource_id: string;
  actor: ActivityActor;
  repository?: string | null;
  metadata: Record<string, any>;
}

export interface ActivityResponse {
  total: number;
  items: ActivityEntry[];
  repository?: string;
}

export const activityService = {
  async getGlobalActivity(limit: number = 50): Promise<ActivityResponse> {
    return apiAuth<ActivityResponse>(`/v1/activity?limit=${limit}`);
  },

  async getAuditLogs(limit: number = 50): Promise<ActivityResponse> {
    return apiAuth<ActivityResponse>(`/v1/audit-logs?limit=${limit}`);
  },

  async getRepositoryActivity(owner: string, repo: string, limit: number = 50): Promise<ActivityResponse> {
    return apiAuth<ActivityResponse>(`/v1/repositories/${owner}/${repo}/activity?limit=${limit}`);
  },
};
