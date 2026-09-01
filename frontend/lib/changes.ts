
import { apiAuth } from "./api";

export interface ChangeCheck {
  name: string;
  status: "passed" | "failed" | "running" | "pending";
  duration?: string;
  details?: string;
}

export interface ChangeReview {
  reviewer_name: string;
  status:
    | "approved"
    | "changes_requested"
    | "pending"
    | "commented";
}

export interface Change {
  id: string;
  repository_id: string;
  title?: string;
  description?: string;
  intent?: string;
  status: string;

  actor_id: string;
  actor_type?: "human" | "agent";
  actor_name?: string;

  task_id?: string;
  task_title?: string;
  agent_id?: string;
  agent_name?: string;
  agent_run_duration?: string;

  risk_level?: string;

  base_commit?: string;
  resulting_commit?: string;

  files_changed?: number;
  additions?: number;
  deletions?: number;

  checks?: ChangeCheck[];
  reviews?: ChangeReview[];

  pull_request_id?: string | null;
  pull_request_title?: string | null;
  pull_request_status?: string | null;

  created_at: string;
  updated_at: string;
}

export interface AuthoritativeReview {
  id: string;
  change_id: string;
  requested_by: string;
  reviewer_id?: string | null;
  status: "pending" | "approved" | "rejected" | string;
  reason?: string | null;
  created_at: string;
  reviewed_at?: string | null;
}

export interface ChangeFile {
  path?: string;
  filename?: string;
  status?: string;
  operation?: string;
  additions: number;
  deletions: number;
  patch?: string;
}

export const changeService = {
  async listChanges(
    username: string,
    repo: string,
    queryParams?: Record<string, string>,
  ): Promise<Change[]> {
    const params = new URLSearchParams(
      queryParams || {},
    );
    params.set("owner", username);
    params.set("repo", repo);

    return apiAuth<Change[]>(
      `/v1/changes?${params.toString()}`,
    );
  },

  async getChange(
    username: string,
    repo: string,
    changeId: string,
  ): Promise<Change> {
    return apiAuth<Change>(
      `/v1/changes/${changeId}`,
    );
  },

  async getChangeFiles(
    username: string,
    repo: string,
    changeId: string,
  ): Promise<ChangeFile[]> {
    return apiAuth<ChangeFile[]>(
      `/v1/changes/${changeId}/files`,
    );
  },

  async getChangeReviews(
    changeId: string,
  ): Promise<AuthoritativeReview[]> {
    return apiAuth<AuthoritativeReview[]>(
      `/v1/changes/${changeId}/reviews`,
    );
  },
};