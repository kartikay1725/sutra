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
          <pre className="bg-[#050c12] text-[#8fb1bd] border border-[var(--line)] p-6 rounded-lg overflow-x-auto text-xs font-mono leading-loose">
{`sutra_agent_contract:
  identity:
    type: "agent"
    auth_method: "session-bound basic"
    session_acquisition: "POST /v1/agents/session"
    header: "Authorization: Basic <base64(prefix:session_token)>"

  discovery:
    profile: "GET /v1/me"
    repositories: "GET /v1/repositories"

  git:
    clone_url: "http://localhost:8000/git/<owner>/<repo>.git"
    push: "Restricted to granted capabilities. Triggers pre-receive hook."
    force_push: "REJECTED (Hard limit)"

  changes_and_pull_requests:
    change_creation: "POST /v1/repositories/<owner>/<repo>/changes"
    pr_creation: "POST /v1/repositories/<owner>/<repo>/pull-requests"
    
  ci:
    trigger: "POST /v1/repositories/<owner>/<repo>/ci/jobs"
    status: "GET /v1/repositories/<owner>/<repo>/ci/jobs/<id>"

  merge:
    allowed: false
    reason: "Agents cannot approve their own changes or bypass Branch Protection. A Human Owner must perform the merge."`}
          </pre>
        </section>
      </div>
    ) 
  }
];
