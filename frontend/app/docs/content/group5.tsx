import React from 'react';
import { DocSection } from './data';

export const Group5AgentContract: DocSection[] = [
  { 
    id: "agent-contract", 
    category: "Agent Contract", 
    title: "Agent Contract", 
    content: (
      <div className="flex flex-col gap-10">
        <section>
          <h2 className="text-xl font-bold mb-4">SUTRA Agent Contract</h2>
          <p className="mb-4">This section is intentionally concise and machine-readable for AI agents. It describes the guaranteed workflows within SUTRA.</p>
          <pre className="bg-[#111111] text-[#A3A3A3] border border-[var(--line)] p-6 rounded-lg overflow-x-auto text-xs font-mono leading-loose">
{`sutra_agent_contract:
  identity:
    type: "agent"
    auth_methods:
      - "OAuth 2.1 PKCE (/oauth/authorize -> /oauth/token -> sutra_mcp_at_...)"
      - "Session-bound Bearer (Authorization: Bearer sutra_session_...)"
    lease:
      absolute_ttl_seconds: 900
      idle_timeout_seconds: 120
      heartbeat_renewal: "POST /v1/agent/tasks/{id}/heartbeat"

  mcp_interface:
    endpoint: "https://api.sutra.sudarshanai.com/v1/mcp"
    transport: "Streamable HTTP (RFC 9728)"
    core_tools:
      context: "sutra_get_context"
      task_initiation: "sutra_start_task"
      change_declaration: "sutra_declare_change"
      code_submission: "sutra_push_commit"
      pull_request: "sutra_open_pull_request"
      status_check: "sutra_get_status"
      governance_check: "sutra_get_governance"
      provenance_audit: "sutra_get_provenance"
      merge_request: "sutra_request_merge"
      task_finalization: "sutra_complete_task"
      ci_inspection: "sutra_get_ci_logs"
      knowledge_search: "sutra_search_knowledge"

  governance_invariants:
    agent_merge: false
    agent_self_approval: false
    head_sha_invalidation: true
    merge_authority: "Mandatory human approval on SUTRA control plane."`}
          </pre>
        </section>
      </div>
    ) 
  }
];
