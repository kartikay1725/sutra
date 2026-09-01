import { apiAuth } from "./api";

export const ciDeployService = {
  async listJobs(repoId: string): Promise<any[]> {
    return apiAuth<any[]>(`/v1/repositories/${repoId}/ci/jobs`).catch(() => []);
  },
  async getJob(repoId: string, jobId: string): Promise<any> {
    return apiAuth<any>(`/v1/repositories/${repoId}/ci/jobs/${jobId}`).catch(() => null);
  },
  async listEnvironments(repoId: string): Promise<any[]> {
    return apiAuth<any[]>(`/v1/repositories/${repoId}/environments`).catch(() => []);
  },
  async listDeployments(repoId: string): Promise<any[]> {
    return apiAuth<any[]>(`/v1/repositories/${repoId}/deployments`).catch(() => []);
  }
};
