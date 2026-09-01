import { apiAuth } from "./api";

export interface PullRequest {
  id: string;
  repository_id: string;
  title: string;
  description: string;
  state: string; // 'open', 'closed', 'merged'
  source_branch: string;
  target_branch: string;
  author_id: string;
  created_at: string;
  updated_at: string;
}

export const pullRequestService = {
  async listPullRequests(username: string, repo: string): Promise<PullRequest[]> {
    return apiAuth<PullRequest[]>(`/v1/repositories/${username}/${repo}/pulls`);
  },

  async getPullRequest(username: string, repo: string, prId: string): Promise<PullRequest> {
    return apiAuth<PullRequest>(`/v1/repositories/${username}/${repo}/pulls/${prId}`);
  }
};
