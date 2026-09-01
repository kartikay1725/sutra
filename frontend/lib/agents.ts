import { apiAuth } from "./api";

export interface Agent {
  id: string;
  name: string;
  description: string | null;
  provider: string | null;
  model: string | null;
  status: string;
  is_active: boolean;
  token_prefix: string;
}

export interface AgentCreated extends Agent {
  token: string;
}

export interface CreateAgentPayload {
  name: string;
  description?: string;
  provider?: string;
  model?: string;
}

export interface AgentSession {
  session_id: string;
  agent_id: string;
  token_prefix: string;
  status: string;
  created_at: string;
  expires_at: string;
  last_seen_at: string;
  revoked_at: string | null;
}

export interface AgentRegistration {
  id: string;
  agent_name: string;
  agent_description: string | null;
  provider: string | null;
  model: string | null;
  status: string;
  created_at: string;
  expires_at: string;
  requested_capabilities: string[];
  requested_repo_name: string | null;
  new_repo: boolean;
}

export interface AgentRepositoryAccess {
  id: string;
  repository_id: string;
  repository_name: string;
  repository_slug: string;
  repository_owner: string;
  permissions: string[];
  enabled: boolean;
}

export const agentService = {
  async listAgents(): Promise<Agent[]> {
    return apiAuth<Agent[]>(`/v1/agents`);
  },

  async createAgent(payload: CreateAgentPayload): Promise<AgentCreated> {
    return apiAuth<AgentCreated>(`/v1/agents`, {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  async listSessions(agentId: string): Promise<AgentSession[]> {
    return apiAuth<AgentSession[]>(
      `/v1/agents/${encodeURIComponent(agentId)}/sessions`,
    );
  },

  async revokeSession(sessionId: string): Promise<void> {
    await apiAuth<void>(
      `/v1/agents/sessions/${encodeURIComponent(sessionId)}/revoke`,
      { method: "POST" },
    );
  },

  async revokeAgent(agentId: string): Promise<void> {
    await apiAuth<void>(`/v1/agents/${agentId}`, { method: "DELETE" });
  },

  async listPendingRegistrations(): Promise<AgentRegistration[]> {
    return apiAuth<AgentRegistration[]>(`/v1/agents/registrations/pending`);
  },

  async approveRegistration(id: string): Promise<void> {
    await apiAuth<void>(`/v1/agents/registrations/${id}/approve`, {
      method: "POST",
    });
  },

  async rejectRegistration(id: string): Promise<void> {
    await apiAuth<void>(`/v1/agents/registrations/${id}/reject`, {
      method: "POST",
    });
  },

  async listRepositoryAccess(agentId: string): Promise<AgentRepositoryAccess[]> {
    return apiAuth<AgentRepositoryAccess[]>(`/v1/agents/${encodeURIComponent(agentId)}/repository-access`);
  },

  async grantRepositoryAccess(
    agentId: string,
    repositoryId: string,
    permissions: string[],
    enabled: boolean = true,
  ): Promise<AgentRepositoryAccess> {
    return apiAuth<AgentRepositoryAccess>(`/v1/agents/${encodeURIComponent(agentId)}/repository-access`, {
      method: "POST",
      body: JSON.stringify({ repository_id: repositoryId, permissions, enabled }),
    });
  },

  async updateRepositoryAccess(
    agentId: string,
    repositoryId: string,
    permissions: string[],
    enabled: boolean,
  ): Promise<AgentRepositoryAccess> {
    return apiAuth<AgentRepositoryAccess>(`/v1/agents/${encodeURIComponent(agentId)}/repository-access/${encodeURIComponent(repositoryId)}`, {
      method: "PUT",
      body: JSON.stringify({ permissions, enabled }),
    });
  },

  async revokeRepositoryAccess(agentId: string, repositoryId: string): Promise<void> {
    await apiAuth<void>(`/v1/agents/${encodeURIComponent(agentId)}/repository-access/${encodeURIComponent(repositoryId)}`, {
      method: "DELETE",
    });
  },
};
