import { apiAuth } from "./api";
import { clientCache, CACHE_TTL } from "./cache";

export interface Repository {
  id: string;
  name: string;
  description: string | null;
  visibility: "public" | "private";
  is_private: boolean;
  default_branch: string;
  owner?: string;
  provider_owner?: string;
  provider_type?: string;
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
  async listRepositories(options?: { forceRefresh?: boolean }): Promise<Repository[]> {
    return clientCache.fetch<Repository[]>(
      "repos:list",
      async () => {
        const rows = await apiAuth<any[]>("/v1/repositories");
        return rows.map(normalizeRepository);
      },
      {
        ...CACHE_TTL.REPOSITORIES,
        forceRefresh: options?.forceRefresh,
      }
    );
  },

  async createRepository(name: string, description: string, is_private: boolean = false): Promise<Repository> {
    const row = await apiAuth<any>("/v1/repositories", {
      method: "POST",
      body: JSON.stringify({ name, description, visibility: is_private ? "private" : "public" }),
    });
    clientCache.delete("repos:list");
    return normalizeRepository(row);
  },

  async getTrending(since: string = "daily"): Promise<Repository[]> {
    const rows = await apiAuth<any[]>(`/v1/explore/trending/repositories?since=${since}`);
    return rows.map(normalizeRepository);
  },

  async getRepository(username: string, repo: string, options?: { forceRefresh?: boolean }): Promise<Repository> {
    const key = `repo:${username.toLowerCase()}/${repo.toLowerCase()}`;
    return clientCache.fetch<Repository>(
      key,
      async () => {
        const row = await apiAuth<any>(`/v1/repositories/${username}/${repo}`);
        return normalizeRepository(row);
      },
      {
        ...CACHE_TTL.REPO_DETAIL,
        forceRefresh: options?.forceRefresh,
      }
    );
  },

  async getBranches(
    username: string,
    repo: string,
    options?: { forceRefresh?: boolean }
  ): Promise<{
    repository_id: string;
    default_branch: string;
    branches: Array<{
      name: string;
      commit: string;
      protected?: boolean;
    }>;
  }> {
    const key = `repo:${username.toLowerCase()}/${repo.toLowerCase()}:branches`;
    return clientCache.fetch(
      key,
      () =>
        apiAuth<{
          repository_id: string;
          default_branch: string;
          branches: Array<{
            name: string;
            commit: string;
            protected?: boolean;
          }>;
        }>(`/v1/repositories/${username}/${repo}/branches`),
      {
        ...CACHE_TTL.BRANCHES,
        forceRefresh: options?.forceRefresh,
      }
    );
  },

  async updateSettings(
    username: string,
    repo: string,
    data: { settings?: Record<string, any>; name?: string; description?: string; default_branch?: string },
  ): Promise<any> {
    const res = await apiAuth<any>(`/v1/repositories/${username}/${repo}/settings`, {
      method: "PATCH",
      body: JSON.stringify(data),
    });
    clientCache.delete("repos:list");
    clientCache.invalidatePrefix(`repo:${username.toLowerCase()}/${repo.toLowerCase()}`);
    return res;
  },

  async updateVisibility(username: string, repo: string, visibility: "public" | "private"): Promise<any> {
    const row = await apiAuth<any>(`/v1/repositories/${username}/${repo}/visibility`, {
      method: "PATCH",
      body: JSON.stringify({ visibility }),
    });
    clientCache.delete("repos:list");
    clientCache.invalidatePrefix(`repo:${username.toLowerCase()}/${repo.toLowerCase()}`);
    return row;
  },

  async transferRepository(username: string, repo: string, new_owner: string): Promise<any> {
    const res = await apiAuth<any>(`/v1/repositories/${username}/${repo}/transfer`, {
      method: "POST",
      body: JSON.stringify({ new_owner }),
    });
    clientCache.delete("repos:list");
    clientCache.invalidatePrefix(`repo:${username.toLowerCase()}/${repo.toLowerCase()}`);
    return res;
  },

  async deleteRepository(username: string, repo: string): Promise<any> {
    const res = await apiAuth<any>(`/v1/repositories/${username}/${repo}`, {
      method: "DELETE",
    });
    clientCache.delete("repos:list");
    clientCache.invalidatePrefix(`repo:${username.toLowerCase()}/${repo.toLowerCase()}`);
    return res;
  },
};

export const repositoriesService = {
  list: repositoryService.listRepositories,
  ...repositoryService,
};

