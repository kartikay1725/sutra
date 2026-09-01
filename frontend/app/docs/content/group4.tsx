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
          <div className="bg-red-500/10 border-l-4 border-red-500 p-4 rounded-r-lg mb-4">
            <h4 className="font-bold text-sm text-red-400">CRITICAL RULE</h4>
            <p className="text-xs mt-2 opacity-80">
              You do NOT have bypass capabilities. All your code modifications must pass through the Git pre-receive hook, CI pipelines, and branch protection requirements. You cannot approve your own changes.
            </p>
          </div>
        </section>

        {/* Quick Start & Workflow */}
        <section>
          <h3 className="text-lg font-bold mb-4">Agent Quick Start Workflow</h3>
          <p className="mb-4">Do not infer workflows. Follow these exact steps:</p>
          <div className="flex flex-col gap-3">
            <div className="p-4 border border-[var(--line)] rounded-lg bg-white/5">
              <strong>STEP 1: Identify & Discover</strong><br/>
              <span className="text-xs opacity-70">Use <code>GET /v1/me</code> and <code>GET /v1/repositories</code> to discover authorized scopes.</span>
            </div>
            <div className="p-4 border border-[var(--line)] rounded-lg bg-white/5">
              <strong>STEP 2: Clone & Inspect</strong><br/>
              <span className="text-xs opacity-70">Execute <code>git clone http://localhost:8000/git/&lt;owner&gt;/&lt;repo&gt;.git</code> using Basic Auth. <strong>IMPORTANT:</strong> You MUST use a short-lived <code>AgentSession</code> token (obtained via <code>POST /v1/agents/session</code>) as your Git password. Your long-lived credential will be rejected. Format: <code>prefix:session_token</code>.</span>
            </div>
            <div className="p-4 border border-[var(--line)] rounded-lg bg-white/5">
              <strong>STEP 3: Modify & Push</strong><br/>
              <span className="text-xs opacity-70">Commit changes and push. The SUTRA pre-receive hook will automatically generate a Change record.</span>
            </div>
            <div className="p-4 border border-[var(--line)] rounded-lg bg-white/5">
              <strong>STEP 4: Pull Request</strong><br/>
              <span className="text-xs opacity-70">Use the API to open a PR for your Change. Wait for CI to run.</span>
            </div>
            <div className="p-4 border border-[var(--line)] rounded-lg bg-white/5">
              <strong>STEP 5: Review & Merge</strong><br/>
              <span className="text-xs opacity-70">If a human requests changes, push new commits. If approved and CI passes, a human must merge it.</span>
            </div>
          </div>
        </section>

        {/* Failure & Recovery */}
        <section>
          <h3 className="text-lg font-bold mb-4">Agent Failure & Recovery</h3>
          <p className="mb-4">When a push or API call fails, use this recovery matrix instead of guessing.</p>
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
                <td className="font-mono text-red-400">Force Push Rejection</td>
                <td>Agents cannot rewrite history (git push -f).</td>
                <td>Pull latest changes, resolve conflicts locally, and do a standard push.</td>
              </tr>
              <tr>
                <td className="font-mono text-red-400">403 Forbidden</td>
                <td>Missing explicit <code>repository.write</code> capability.</td>
                <td>Halt operation. The human owner must grant the capability via SUTRA dashboard.</td>
              </tr>
              <tr>
                <td className="font-mono text-red-400">CI Failure</td>
                <td>Tests failed on your commit.</td>
                <td>Fetch the CI logs, fix the failing code, commit, and push again.</td>
              </tr>
            </tbody>
          </table>
        </section>

      </div>
    ) 
  }
];
