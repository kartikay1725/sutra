import { apiAuth } from "./api";

export interface Repository {
  id: string;
  name: string;
  description: string | null;
  visibility: "public" | "private";
  is_private: boolean;
  default_branch: string;
  owner?: string;
  clone_url?: string;
  settings?: Record<string, any>;
  created_at: string;
  updated_at: string;
}

function normalizeRepository(input: any): Repository {
  const visibility = input.visibility || (input.is_private ? "private" : "public");
  return {
    ...input,
    visibility,
    is_private: visibility === "private",
  };
}

export const repositoryService = {
  async listRepositories(): Promise<Repository[]> {
    const rows = await apiAuth<any[]>("/v1/repositories");
    return rows.map(normalizeRepository);
  },

  async createRepository(name: string, description: string, is_private: boolean = false): Promise<Repository> {
    const row = await apiAuth<any>("/v1/repositories", {
      method: "POST",
      body: JSON.stringify({ name, description, visibility: is_private ? "private" : "public" }),
    });
    return normalizeRepository(row);
  },

  async getTrending(since: string = "daily"): Promise<Repository[]> {
    const rows = await apiAuth<any[]>(`/v1/explore/trending/repositories?since=${since}`);
    return rows.map(normalizeRepository);
  },

  async getRepository(username: string, repo: string): Promise<Repository> {
    const row = await apiAuth<any>(`/v1/repositories/${username}/${repo}`);
    return normalizeRepository(row);
  },
  async getBranches(
    username: string,
    repo: string,
  ): Promise<{
    repository_id: string;
    default_branch: string;
    branches: Array<{
      name: string;
      commit: string;
      protected?: boolean;
    }>;
  }> {
    return apiAuth<{
      repository_id: string;
      default_branch: string;
      branches: Array<{
        name: string;
        commit: string;
        protected?: boolean;
      }>;
    }>(
      `/v1/repositories/${username}/${repo}/branches`,
    );
  },
  async updateSettings(
    username: string,
    repo: string,
    data: { settings?: Record<string, any>; name?: string; description?: string; default_branch?: string },
  ): Promise<any> {
    return apiAuth<any>(`/v1/repositories/${username}/${repo}/settings`, {
      method: "PATCH",
      body: JSON.stringify(data),
    });
  },

  async updateVisibility(username: string, repo: string, visibility: "public" | "private"): Promise<any> {
    const row = await apiAuth<any>(`/v1/repositories/${username}/${repo}/visibility`, {
      method: "PATCH",
      body: JSON.stringify({ visibility }),
    });
    return row;
  },

  async transferRepository(username: string, repo: string, new_owner: string): Promise<any> {
    return apiAuth<any>(`/v1/repositories/${username}/${repo}/transfer`, {
      method: "POST",
      body: JSON.stringify({ new_owner }),
    });
  },

  async deleteRepository(username: string, repo: string): Promise<any> {
    return apiAuth<any>(`/v1/repositories/${username}/${repo}`, {
      method: "DELETE",
    });
  },
};

export const repositoriesService = {
  list: repositoryService.listRepositories,
  ...repositoryService,
};
