
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

export interface CommitProvenance {
  source: "sutra" | "github" | string;
  tracked: boolean;
  identity_type: "agent" | "human" | "external" | "unknown" | string;
  actor_id?: string | null;
  actor_name?: string | null;
  agent?: {
    id: string;
    name: string;
    provider?: string;
    model?: string;
  } | null;
  session?: {
    id: string;
    status?: string;
    expires_at?: string;
  } | null;
  task?: {
    id: string;
    title?: string;
    status?: string;
    task_type?: string;
  } | null;
}

export interface CommitDetail {
  sha: string;
  message?: string | null;
  author_name?: string | null;
  author_email?: string | null;
  committed_at?: string | null;
  provenance?: CommitProvenance | null;
}

export interface Change {
  id: string;
  repository_id: string;
  repository_name?: string | null;
  title?: string | null;
  description?: string | null;
  intent?: string;
  status: string;

  actor_id: string;
  actor_type?: "human" | "agent";
  actor_name?: string;

  task_id?: string | null;
  task_title?: string | null;
  agent_id?: string | null;
  agent_name?: string | null;
  agent_session_id?: string | null;
  agent_run_duration?: string;

  branch?: string | null;
  base_branch?: string | null;

  risk_level?: string;

  base_commit?: string | null;
  resulting_commit?: string | null;

  files_changed?: number;
  additions?: number;
  deletions?: number;

  commits?: CommitDetail[];
  checks?: ChangeCheck[];
  reviews?: ChangeReview[];

  pull_request_id?: string | null;
  pull_request_title?: string | null;
  pull_request_status?: string | null;
  github_pr_number?: number | null;
  github_pr_url?: string | null;

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
  async getAllChanges(options?: {
    actor_type?: string;
    status?: string;
    risk_level?: string;
    search?: string;
    agent_id?: string;
  }): Promise<Change[]> {
    const params = new URLSearchParams();
    if (options?.actor_type && options.actor_type !== "all") params.set("actor_type", options.actor_type);
    if (options?.status && options.status !== "all") params.set("status", options.status);
    if (options?.risk_level && options.risk_level !== "all") params.set("risk_level", options.risk_level);
    if (options?.search?.trim()) params.set("search", options.search.trim());
    if (options?.agent_id) params.set("agent_id", options.agent_id);
    const qs = params.toString();
    return apiAuth<Change[]>(qs ? `/v1/changes?${qs}` : "/v1/changes");
  },

  async listChanges(
    username?: string,
    repo?: string,
    queryParams?: Record<string, string>,
  ): Promise<Change[]> {
    const params = new URLSearchParams(queryParams || {});
    if (username) params.set("owner", username);
    if (repo) params.set("repo", repo);
    const qs = params.toString();
    return apiAuth<Change[]>(qs ? `/v1/changes?${qs}` : "/v1/changes");
  },

  async getChange(
    username: string,
    repo: string,
    changeId: string,
  ): Promise<Change> {
    return apiAuth<Change>(`/v1/changes/${changeId}`);
  },

  async getChangeById(changeId: string): Promise<Change> {
    return apiAuth<Change>(`/v1/changes/${changeId}`);
  },

  async getChangeFiles(
    username: string,
    repo: string,
    changeId: string,
  ): Promise<ChangeFile[]> {
    return apiAuth<ChangeFile[]>(`/v1/changes/${changeId}/files`);
  },

  async getChangeReviews(
    changeId: string,
  ): Promise<AuthoritativeReview[]> {
    return apiAuth<AuthoritativeReview[]>(
      `/v1/changes/${changeId}/reviews`,
    );
  },
};