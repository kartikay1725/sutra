import { apiAuth } from "./api";

export interface GitHubStatus {
  connected: boolean;
  account: string | null;
  target_type: string | null;
  installation_id: number | null;
  repo_count: number;
}

export interface GitHubSyncResult {
  status: string;
  synced_count: number;
  account: string;
}

export const integrationService = {
  /**
   * Get the current user's GitHub integration status.
   * Returns connected=false if no installation exists.
   */
  async getGitHubStatus(): Promise<GitHubStatus> {
    return apiAuth<GitHubStatus>("/v1/integrations/github");
  },

  /**
   * Get the GitHub App installation URL to redirect the user to.
   * The backend generates a signed CSRF state token.
   */
  async getGitHubConnectUrl(): Promise<{ redirect_url: string }> {
    return apiAuth<{ redirect_url: string }>("/v1/integrations/github/connect");
  },

  /**
   * Disconnect the user's GitHub integration.
   */
  async disconnectGitHub(): Promise<{ status: string }> {
    return apiAuth<{ status: string }>("/v1/integrations/github", {
      method: "DELETE",
    });
  },

  /**
   * Trigger a manual sync of GitHub repositories.
   */
  async syncGitHub(): Promise<GitHubSyncResult> {
    return apiAuth<GitHubSyncResult>("/v1/integrations/github/sync", {
      method: "POST",
    });
  },
};
