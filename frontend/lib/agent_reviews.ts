import { apiAuth } from "./api";

export interface AgentFinding {
  id: string;
  pull_request_id: string;
  agent_id: string;
  severity: string; // 'critical', 'high', 'medium', 'low', 'info'
  category: string; // 'security', 'performance', 'bug', 'style'
  message: string;
  path?: string;
  line_number?: number;
  diff_side?: string;
  suggested_fix?: string;
  status: string; // 'active', 'resolved', 'ignored'
  created_at: string;
}

export interface AgentComment {
  id: string;
  pull_request_id: string;
  agent_id: string;
  body: string;
  path?: string;
  diff_side?: string;
  line_number?: number;
  status: string; // 'active', 'resolved'
  created_at: string;
}

export interface AgentReviewSummary {
  participating_agents_count: number;
  total_findings: number;
  total_comments: number;
  severity_distribution: Record<string, number>;
  agents: Record<string, { findings: number; comments: number }>;
  latest_findings: AgentFinding[];
  latest_comments: AgentComment[];
}

export const agentReviewService = {
  async getSummary(prId: string): Promise<AgentReviewSummary> {
    return apiAuth<AgentReviewSummary>(`/v1/pull-requests/${prId}/agent-reviews`);
  }
};
