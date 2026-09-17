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

function normalizeEntry(raw: any): ActivityEntry {
  const actorObj = raw.actor || {};
  const actorType = (actorObj.type || (raw.actor_type === "agent" ? "agent" : "human")) as "human" | "agent" | "system";
  const actorName = actorObj.name || raw.actor_name || "Unknown";
  const actorId = actorObj.id || raw.actor_id || "";

  return {
    id: raw.id || "",
    timestamp: raw.timestamp || new Date().toISOString(),
    action: raw.action || "activity",
    category: raw.category || "general",
    resource_type: raw.resource_type || "resource",
    resource_id: raw.resource_id || (raw.resource_name && raw.resource_name.includes(":") ? raw.resource_name.split(":")[1] : raw.resource_name) || "",
    actor: {
      id: actorId,
      name: actorName,
      type: actorType,
    },
    repository: raw.repository || (raw.resource_name && raw.resource_name.includes(":") ? raw.resource_name.split(":")[0] : null),
    metadata: raw.metadata || raw.metadata_json || {},
  };
}

function normalizeResponse(res: any, repo?: string): ActivityResponse {
  if (Array.isArray(res)) {
    return {
      total: res.length,
      items: res.map(normalizeEntry),
      repository: repo,
    };
  }
  if (res && Array.isArray(res.items)) {
    return {
      total: res.total ?? res.items.length,
      items: res.items.map(normalizeEntry),
      repository: res.repository || repo,
    };
  }
  return { total: 0, items: [], repository: repo };
}

export const activityService = {
  async getGlobalActivity(limit: number = 50): Promise<ActivityResponse> {
    const res = await apiAuth<any>(`/v1/activity?limit=${limit}`);
    return normalizeResponse(res);
  },

  async getAuditLogs(limit: number = 50): Promise<ActivityResponse> {
    const res = await apiAuth<any>(`/v1/audit-logs?limit=${limit}`);
    return normalizeResponse(res);
  },

  async getRepositoryActivity(owner: string, repo: string, limit: number = 50): Promise<ActivityResponse> {
    const res = await apiAuth<any>(`/v1/repositories/${owner}/${repo}/activity?limit=${limit}`);
    return normalizeResponse(res, repo);
  },
};
