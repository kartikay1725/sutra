import { apiAuth } from "./api";
import { clientCache, CACHE_TTL } from "./cache";

export interface Issue {
  id: string;
  repository_id: string;
  number?: number;
  github_issue_id?: string | null;
  github_issue_number?: number | null;
  github_html_url?: string | null;
  github_author_login?: string | null;
  source_type?: string;
  agent_id?: string | null;
  agent_session_id?: string | null;
  task_id?: string | null;
  title: string;
  body: string;
  state?: "open" | "closed";
  status: "open" | "closed";
  author_id?: string | null;
  author_name?: string | null;
  author_type?: string | null;
  created_at: string;
  updated_at: string;
  closed_at: string | null;
}

export type IssueResolution =
  | "completed"
  | "not_planned"
  | "duplicate";

export interface IssueStatusPayload {
  status: "open" | "closed";
  resolution?: IssueResolution;
  comment?: string;
}

export const issueService = {
  async listIssues(
    username: string,
    repo: string,
    options?: { forceRefresh?: boolean }
  ): Promise<Issue[]> {
    const key = `issues:${username.toLowerCase()}/${repo.toLowerCase()}`;
    return clientCache.fetch<Issue[]>(
      key,
      () =>
        apiAuth<Issue[]>(
          `/v1/repositories/${username}/${repo}/issues`,
        ),
      {
        ...CACHE_TTL.ISSUES,
        forceRefresh: options?.forceRefresh,
      }
    );
  },

  async createIssue(
    username: string,
    repo: string,
    payload: {
      title: string;
      body: string;
    },
  ): Promise<Issue> {
    const res = await apiAuth<Issue>(
      `/v1/repositories/${username}/${repo}/issues`,
      {
        method: "POST",
        body: JSON.stringify(payload),
      },
    );
    clientCache.delete(`issues:${username.toLowerCase()}/${repo.toLowerCase()}`);
    return res;
  },

  async updateIssueStatus(
    username: string,
    repo: string,
    issueId: string,
    payload: IssueStatusPayload,
  ): Promise<{
    status: string;
    issue_status: "open" | "closed";
    resolution: IssueResolution | null;
  }> {
    const res = await apiAuth<{
      status: string;
      issue_status: "open" | "closed";
      resolution: IssueResolution | null;
    }>(
      `/v1/repositories/${username}/${repo}/issues/${issueId}/status`,
      {
        method: "PATCH",
        body: JSON.stringify(payload),
      },
    );
    clientCache.delete(`issues:${username.toLowerCase()}/${repo.toLowerCase()}`);
    return res;
  },

  async deleteIssue(
    username: string,
    repo: string,
    issueId: string,
  ): Promise<any> {
    const res = await apiAuth(
      `/v1/repositories/${username}/${repo}/issues/${issueId}`,
      {
        method: "DELETE",
      },
    );
    clientCache.delete(`issues:${username.toLowerCase()}/${repo.toLowerCase()}`);
    return res;
  },


  async getIssue(
    username: string,
    repo: string,
    issueId: string,
  ): Promise<Issue> {
    return apiAuth<Issue>(
      `/v1/repositories/${username}/${repo}/issues/${issueId}`,
    );
  },

  async getComments(
    username: string,
    repo: string,
    issueId: string,
  ): Promise<any[]> {
    return apiAuth<any[]>(
      `/v1/repositories/${username}/${repo}/issues/${issueId}/comments`,
    );
  },

  async addComment(
    username: string,
    repo: string,
    issueId: string,
    body: string,
  ): Promise<any> {
    return apiAuth(
      `/v1/repositories/${username}/${repo}/issues/${issueId}/comments`,
      {
        method: "POST",
        body: JSON.stringify({ body }),
      },
    );
  },
};