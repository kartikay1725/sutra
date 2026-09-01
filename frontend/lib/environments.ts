import { apiAuth } from "./api";

export interface Environment {
  id: string;
  repository_id: string;
  name: string;
  description: string | null;
  created_at: string;
}

export interface Deployment {
  id: string;
  environment_id: string;
  repository_id: string;
  commit_sha: string;
  change_id: string | null;
  actor_id: string;
  status: string;
  log_output: string | null;
  created_at: string;
}

export const environmentService = {
  async listEnvironments(username: string, repo: string): Promise<Environment[]> {
    return apiAuth<Environment[]>(`/v1/repositories/${username}/${repo}/environments`);
  },

  async listDeployments(envId: string): Promise<Deployment[]> {
    return apiAuth<Deployment[]>(`/v1/environments/${envId}/deployments`);
  }
};
