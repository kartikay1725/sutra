import React from 'react';
import { DocSection } from './data';

export const Group4AgentGuide: DocSection[] = [
  { 
    id: "ai-agent-guide", 
    category: "AI Agent Guide", 
    title: "AI Agent Guide", 
    content: (
      <div className="flex flex-col gap-10">
        
        {/* Agent Operating Manual */}
        <section>
          <h2 className="text-xl font-bold mb-4">AI Agent Operating Manual</h2>
          <p className="mb-4">You are an AI engineering agent operating inside SUTRA. This manual defines your identity, credentials, permissions, and limitations.</p>
          <div className="bg-orange-500/10 border-l-4 border-orange-500 p-4 rounded-r-lg mb-4">
            <h4 className="font-bold text-sm text-orange-400">CORE GOVERNANCE RULE</h4>
            <p className="text-xs mt-2 opacity-80">
              AI agents operate under bounded capability grants and short-lived <code>AgentSession</code> leases. All code modifications pass through SUTRA governance, CI verification, and branch protection requirements. Agents cannot approve their own pull requests or execute merges.
            </p>
          </div>
        </section>

        {/* Real MCP-Driven Workflow */}
        <section>
          <h3 className="text-lg font-bold mb-4">Governed Engineering Workflow (MCP-Driven)</h3>
          <p className="mb-4">Follow this standard execution path when working on SUTRA-governed repositories:</p>
          <div className="flex flex-col gap-3">
            <div className="p-4 border border-[var(--line)] rounded-lg bg-white/5">
              <strong>STEP 1: Discover Identity & Scope</strong><br/>
              <span className="text-xs opacity-70">Call <code>sutra_get_context</code> to discover your agent identity, assigned repository, capability grants, and lease status.</span>
            </div>
            <div className="p-4 border border-[var(--line)] rounded-lg bg-white/5">
              <strong>STEP 2: Claim or Start Task</strong><br/>
              <span className="text-xs opacity-70">Call <code>sutra_start_task</code> with the engineering prompt. This auto-provisions a task, allocates a feature branch, and locks your session lease.</span>
            </div>
            <div className="p-4 border border-[var(--line)] rounded-lg bg-white/5">
              <strong>STEP 3: Inspect Codebase & Formulate Solution</strong><br/>
              <span className="text-xs opacity-70">Use workspace tools for reading/editing files and running local tests. Optionally query <code>sutra_search_knowledge</code> for semantic architecture insights.</span>
            </div>
            <div className="p-4 border border-[var(--line)] rounded-lg bg-white/5">
              <strong>STEP 4: Declare Change & Push Commit</strong><br/>
              <span className="text-xs opacity-70">Call <code>sutra_declare_change</code> to register your work block, then submit commits via <code>sutra_push_commit</code> to bind cryptographic agent provenance.</span>
            </div>
            <div className="p-4 border border-[var(--line)] rounded-lg bg-white/5">
              <strong>STEP 5: Open Pull Request & Hand Over</strong><br/>
              <span className="text-xs opacity-70">Call <code>sutra_open_pull_request</code> to create the GitHub PR and trigger CI checks. When checks pass, call <code>sutra_request_merge</code> to queue the PR for human review.</span>
            </div>
          </div>
        </section>

        {/* Failure & Recovery */}
        <section>
          <h3 className="text-lg font-bold mb-4">Agent Failure & Recovery</h3>
          <p className="mb-4">When a tool or API call fails, use this recovery matrix:</p>
          <table className="table mb-4">
            <thead>
              <tr>
                <th>WHAT HAPPENED</th>
                <th>WHY</th>
                <th>RECOVERY</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td className="font-mono text-red-400">401 Unauthorized / Token Expired</td>
                <td>AgentSession 15-minute lease or idle timeout expired.</td>
                <td>Re-authenticate via OAuth 2.1 PKCE or request a fresh AgentSession token.</td>
              </tr>
              <tr>
                <td className="font-mono text-red-400">403 Forbidden</td>
                <td>Missing required capability (e.g. <code>repository.write</code> or <code>change.create</code>).</td>
                <td>Halt operation. The repository owner must grant the capability via SUTRA dashboard.</td>
              </tr>
              <tr>
                <td className="font-mono text-red-400">Self-Approval Blocked</td>
                <td>Agent attempted to approve its own PR or execute a merge.</td>
                <td>Forbidden by design. Queue PR for human owner review via <code>sutra_request_merge</code>.</td>
              </tr>
              <tr>
                <td className="font-mono text-red-400">CI Failure</td>
                <td>Automated tests or checks failed on your commit SHA.</td>
                <td>Fetch logs using <code>sutra_get_ci_logs</code>, fix the issue locally, commit, and push again.</td>
              </tr>
            </tbody>
          </table>
        </section>

      </div>
    ) 
  }
];
