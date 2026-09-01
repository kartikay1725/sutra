import { apiAuth } from "./api";

export interface RepositoryAgentAccess {
  id: string;
  agent_id: string;
  repository_id: string;
  agent_name: string;
  permissions: string[];
  enabled: boolean;
  created_at: string;
  updated_at: string;
}

export const repositoryAgentsService = {
  list(owner: string, repo: string) {
    return apiAuth<RepositoryAgentAccess[]>(
      `/v1/repositories/${encodeURIComponent(owner)}/${encodeURIComponent(repo)}/agents`,
    );
  },

  grant(
    owner: string,
    repo: string,
    agentId: string,
    permissions: string[],
    enabled = true,
  ) {
    return apiAuth<RepositoryAgentAccess>(
      `/v1/repositories/${encodeURIComponent(owner)}/${encodeURIComponent(repo)}/agents`,
      {
        method: "POST",
        body: JSON.stringify({
          agent_id: agentId,
          permissions,
          enabled,
        }),
      },
    );
  },

  revoke(owner: string, repo: string, agentId: string) {
    return apiAuth<void>(
      `/v1/repositories/${encodeURIComponent(owner)}/${encodeURIComponent(repo)}/agents/${encodeURIComponent(agentId)}`,
      { method: "DELETE" },
    );
  },
};
