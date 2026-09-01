import { apiAuth } from "./api";

export interface PullRequest {
  id: string;
  number?: number | string;
  repository_id: string;
  author_id: string;
  source_change_id: string;
  title: string;
  description: string | null;
  target_branch: string;
  source_commit: string | null;
  target_commit: string | null;
  status: "draft" | "open" | "approved" | "merged" | "closed" | "rejected";
  created_at: string;
  updated_at: string;
  merged_at: string | null;
  closed_at: string | null;
}

export interface PRReview {
  id: string;
  change_id: string;
  requested_by: string;
  reviewer_id: string | null;
  status: string;
  reason: string | null;
  created_at: string;
  reviewed_at: string | null;
}

export interface PRChange {
  id: string;
  repository_id: string;
  actor_id: string;
  intent: string;
  base_commit: string | null;
  resulting_commit: string | null;
  status: string;
  risk_level: string;
  additions?: number;
  deletions?: number;
  files_changed?: number;
  files?: {
    path: string;
    operation: string;
    additions: number;
    deletions: number;
  }[];
  created_at: string;
  updated_at: string;
}

export interface PREvent {
  id: string;
  pull_request_id: string;
  change_id: string;
  actor_id: string | null;
  event_type: string;
  from_status: string | null;
  to_status: string | null;
  reason: string | null;
  metadata: Record<string, unknown>;
  created_at: string;
}

export interface PRConflict {
  level: string;
  reason: string;
  paths: string[];
  related_change_ids: string[];
}

export interface PRMergeResult {
  status: string;
  pull_request_id: string;
  detail: string;
}

export const pullRequestService = {
  async createPR(payload: {
    repository_id: string;
    source_change_id: string;
    title: string;
    description: string | null;
    target_branch: string;
    is_draft: boolean;
  }): Promise<PullRequest> {
    return apiAuth<PullRequest>(`/v1/pull-requests`, {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  // Backend uses repository_id (UUID), but we resolve it from owner/name first
  async listPRs(repositoryId: string, statusFilter?: string): Promise<PullRequest[]> {
    const params = new URLSearchParams({ limit: "50" });
    if (statusFilter) params.set("status", statusFilter);
    return apiAuth<PullRequest[]>(`/v1/repositories/${repositoryId}/pull-requests?${params}`);
  },

  async getPR(prId: string): Promise<PullRequest> {
    return apiAuth<PullRequest>(`/v1/pull-requests/${prId}`);
  },

  async getPRChange(prId: string): Promise<PRChange> {
    return apiAuth<PRChange>(`/v1/pull-requests/${prId}/changes`);
  },

  async getPRReviews(prId: string): Promise<PRReview[]> {
    return apiAuth<PRReview[]>(`/v1/pull-requests/${prId}/reviews`);
  },

  async getPREvents(prId: string): Promise<PREvent[]> {
    return apiAuth<PREvent[]>(`/v1/pull-requests/${prId}/events`);
  },

  async approvePR(prId: string, reason?: string): Promise<PullRequest> {
    return apiAuth<PullRequest>(`/v1/pull-requests/${prId}/approve`, {
      method: "POST",
      body: JSON.stringify({ reason: reason || null }),
    });
  },

  async mergePR(prId: string): Promise<PRMergeResult> {
    return apiAuth<PRMergeResult>(`/v1/pull-requests/${prId}/merge`, { method: "POST" });
  },

  async closePR(prId: string, reason?: string): Promise<PullRequest> {
    return apiAuth<PullRequest>(`/v1/pull-requests/${prId}/close`, {
      method: "POST",
      body: JSON.stringify({ reason: reason || null }),
    });
  },

  async requestReview(prId: string): Promise<PRReview> {
    return apiAuth<PRReview>(`/v1/pull-requests/${prId}/reviews`, {
      method: "POST",
      body: JSON.stringify({}),
    });
  },
};
