import { apiAuth } from "./api";

export interface Discussion {
  id: string;
  repository_id: string;
  title: string;
  body: string;
  category: string;
  author_id: string;
  created_at: string;
  updated_at: string;
}

export const discussionService = {
  async listDiscussions(username: string, repo: string, category?: string): Promise<Discussion[]> {
    const query = category ? `?category=${encodeURIComponent(category)}` : '';
    return apiAuth<Discussion[]>(`/v1/repositories/${username}/${repo}/discussions${query}`);
  },
  async createDiscussion(username: string, repo: string, payload: { title: string, body: string, category: string }): Promise<Discussion> {
    return apiAuth<Discussion>(`/v1/repositories/${username}/${repo}/discussions`, {
      method: 'POST',
      body: JSON.stringify(payload)
    });
  },
  async getDiscussion(username: string, repo: string, discussionId: string): Promise<Discussion> {
    return apiAuth<Discussion>(`/v1/repositories/${username}/${repo}/discussions/${discussionId}`);
  },
  async getComments(username: string, repo: string, discussionId: string): Promise<any[]> {
    return apiAuth<any[]>(`/v1/repositories/${username}/${repo}/discussions/${discussionId}/comments`);
  },
  async addComment(username: string, repo: string, discussionId: string, body: string): Promise<any> {
    return apiAuth(`/v1/repositories/${username}/${repo}/discussions/${discussionId}/comments`, {
      method: 'POST',
      body: JSON.stringify({ body })
    });
  }
};
