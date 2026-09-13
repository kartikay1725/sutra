import { apiAuth } from "./api";
import { clientCache, CACHE_TTL } from "./cache";

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

  // Enriched SUTRA & Substrate Provenance Context
  repository_name?: string | null;
  head_branch?: string | null;
  base_branch?: string | null;
  github_pr_number?: number | null;
  github_html_url?: string | null;
  task_id?: string | null;
  task_title?: string | null;
  agent_id?: string | null;
  agent_name?: string | null;
  agent_session_id?: string | null;
  actor_name?: string | null;
  actor_type?: string | null;
  checks_summary?: {
    total: number;
    passed: number;
    failed: number;
    running: number;
    pending: number;
  } | null;
  checks_verdict?: string | null;
  governance_verdict?: string | null;
  ready_for_approval?: boolean | null;
  ready_for_merge?: boolean | null;
  eligible_for_merge?: boolean | null;
  approved?: boolean | null;
  reviewer?: {
    id: string;
    username: string;
    name: string;
    reviewed_at?: string;
  } | null;
  required_approvals?: number | null;
  actual_valid_approvals?: number | null;
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
    const res = await apiAuth<PullRequest>(`/v1/pull-requests`, {
      method: "POST",
      body: JSON.stringify(payload),
    });
    clientCache.invalidatePrefix("prs:");
    return res;
  },

  // Backend uses repository_id (UUID), but we resolve it from owner/name first
  async listPRs(repositoryId: string, statusFilter?: string, options?: { forceRefresh?: boolean }): Promise<PullRequest[]> {
    const params = new URLSearchParams({ limit: "50" });
    if (statusFilter) params.set("status", statusFilter);
    const key = `prs:repo:${repositoryId}:${statusFilter || "all"}`;
    return clientCache.fetch<PullRequest[]>(
      key,
      () => apiAuth<PullRequest[]>(`/v1/repositories/${repositoryId}/pull-requests?${params}`),
      {
        ...CACHE_TTL.PULL_REQUESTS,
        forceRefresh: options?.forceRefresh,
      }
    );
  },

  async getPR(prId: string, options?: { forceRefresh?: boolean }): Promise<PullRequest> {
    const key = `prs:detail:${prId}`;
    return clientCache.fetch<PullRequest>(
      key,
      () => apiAuth<PullRequest>(`/v1/pull-requests/${prId}`),
      {
        ...CACHE_TTL.PULL_REQUESTS,
        forceRefresh: options?.forceRefresh,
      }
    );
  },

  async getPRChange(prId: string): Promise<PRChange> {
    return clientCache.fetch<PRChange>(
      `prs:change:${prId}`,
      () => apiAuth<PRChange>(`/v1/pull-requests/${prId}/changes`),
      CACHE_TTL.PULL_REQUESTS
    );
  },

  async getPRReviews(prId: string): Promise<PRReview[]> {
    return clientCache.fetch<PRReview[]>(
      `prs:reviews:${prId}`,
      () => apiAuth<PRReview[]>(`/v1/pull-requests/${prId}/reviews`),
      CACHE_TTL.PULL_REQUESTS
    );
  },

  async getPREvents(prId: string): Promise<PREvent[]> {
    return clientCache.fetch<PREvent[]>(
      `prs:events:${prId}`,
      () => apiAuth<PREvent[]>(`/v1/pull-requests/${prId}/events`),
      CACHE_TTL.PULL_REQUESTS
    );
  },

  async approvePR(prId: string, reason?: string): Promise<PullRequest> {
    const res = await apiAuth<PullRequest>(`/v1/pull-requests/${prId}/approve`, {
      method: "POST",
      body: JSON.stringify({ reason: reason || null }),
    });
    clientCache.invalidatePrefix("prs:");
    return res;
  },

  async mergePR(prId: string): Promise<PRMergeResult> {
    const res = await apiAuth<PRMergeResult>(`/v1/pull-requests/${prId}/merge`, {
      method: "POST",
    });
    clientCache.invalidatePrefix("prs:");
    clientCache.invalidatePrefix("commits:");
    return res;
  },

  async closePR(prId: string, reason?: string): Promise<PullRequest> {
    const res = await apiAuth<PullRequest>(`/v1/pull-requests/${prId}/close`, {
      method: "POST",
      body: JSON.stringify({ reason: reason || null }),
    });
    clientCache.invalidatePrefix("prs:");
    return res;
  },

  async rejectPR(prId: string, reason?: string): Promise<PullRequest> {
    const res = await apiAuth<PullRequest>(`/v1/pull-requests/${prId}/reject`, {
      method: "POST",
      body: JSON.stringify({ reason: reason || null }),
    });
    clientCache.invalidatePrefix("prs:");
    return res;
  },

  async requestReview(prId: string): Promise<PRReview> {
    const res = await apiAuth<PRReview>(`/v1/pull-requests/${prId}/request-review`, {
      method: "POST",
    });
    clientCache.invalidatePrefix(`prs:reviews:${prId}`);
    return res;
  },
};
