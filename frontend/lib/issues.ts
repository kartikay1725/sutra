import { apiAuth } from "./api";

export interface Issue {
  id: string;
  repository_id: string;
  number?: number;
  title: string;
  body: string;
  state?: "open" | "closed";
  status: "open" | "closed";
  author_id: string;
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
  ): Promise<Issue[]> {
    return apiAuth<Issue[]>(
      `/v1/repositories/${username}/${repo}/issues`,
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
    return apiAuth<Issue>(
      `/v1/repositories/${username}/${repo}/issues`,
      {
        method: "POST",
        body: JSON.stringify(payload),
      },
    );
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
    return apiAuth(
      `/v1/repositories/${username}/${repo}/issues/${issueId}/status`,
      {
        method: "PATCH",
        body: JSON.stringify(payload),
      },
    );
  },

  async deleteIssue(
    username: string,
    repo: string,
    issueId: string,
  ): Promise<any> {
    return apiAuth(
      `/v1/repositories/${username}/${repo}/issues/${issueId}`,
      {
        method: "DELETE",
      },
    );
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