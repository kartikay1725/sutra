import React from 'react';
import { DocSection } from './data';

export const Group7SecurityGovernance: DocSection[] = [
  { 
    id: "security-governance", 
    category: "Security & Governance", 
    title: "Security & Governance", 
    content: (
      <div className="flex flex-col gap-10">
        <section>
          <h2 className="text-xl font-bold mb-4">SUTRA Security & Governance Model</h2>
          <p className="mb-4">SUTRA strictly enforces boundaries through Authentication, Authorization, Ownership, and Capability Checks. The system is architected around a Zero-Trust principle for AI Agents: models can generate code, but control-plane authority is strictly governed.</p>
        </section>

        <section>
          <h3 className="text-lg font-bold mb-4">Agent Boundaries & Enforcement</h3>
          <p className="mb-4">The following actions are prohibited and strictly blocked by SUTRA server-side:</p>
          <table className="table mb-4">
            <thead>
              <tr>
                <th>PROHIBITED ACTION</th>
                <th>HOW SUTRA BLOCKS IT</th>
                <th>WHAT HAPPENS</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td className="font-mono text-red-400 text-xs">Self-Approval</td>
                <td>AuthorizationService enforces reviewer_id != requester_id. Agents cannot self-approve.</td>
                <td>API returns 403 Forbidden.</td>
              </tr>
              <tr>
                <td className="font-mono text-red-400 text-xs">Direct / Agent Merge</td>
                <td>Merge endpoint requires an authenticated Human JWT. AgentSession tokens return 403.</td>
                <td>Merge execution is blocked; PR remains in review queue.</td>
              </tr>
              <tr>
                <td className="font-mono text-red-400 text-xs">Stale Approval Bypass</td>
                <td>Approvals are cryptographically bound to commit HEAD SHA. When new commits arrive, approvals invalidate.</td>
                <td>Governance verdict reverts to BLOCKED until re-reviewed.</td>
              </tr>
              <tr>
                <td className="font-mono text-red-400 text-xs">Unauthorized Scope Access</td>
                <td>Actor isolation limits repository queries to explicit capability grants.</td>
                <td>Returns 404 Not Found to prevent repository metadata leakage.</td>
              </tr>
            </tbody>
          </table>
        </section>

        <section>
          <h3 className="text-lg font-bold mb-4">Four-Pillar Governance Engine</h3>
          <p className="mb-4">Before any PR can be marked <code>READY_FOR_MERGE</code>, SUTRA's governance engine evaluates four independent pillars:</p>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="p-4 border border-[var(--line)] rounded-lg bg-white/5">
              <strong className="text-orange-400 text-sm">1. CI Check Status</strong>
              <p className="text-xs opacity-70 mt-1">Ingests authoritative check runs from GitHub Actions webhooks (HMAC-verified). Failing or pending checks block merge.</p>
            </div>
            <div className="p-4 border border-[var(--line)] rounded-lg bg-white/5">
              <strong className="text-blue-400 text-sm">2. Commit Provenance</strong>
              <p className="text-xs opacity-70 mt-1">Verifies every commit SHA in the PR against recorded AgentSessions and Tasks, flagging unverified external commits.</p>
            </div>
            <div className="p-4 border border-[var(--line)] rounded-lg bg-white/5">
              <strong className="text-green-400 text-sm">3. Policy & Sensitive Files</strong>
              <p className="text-xs opacity-70 mt-1">Evaluates branch protection rules, sensitive file modifications (.github/workflows, secrets), and merge conflict risks.</p>
            </div>
            <div className="p-4 border border-[var(--line)] rounded-lg bg-white/5">
              <strong className="text-purple-400 text-sm">4. Human Review & Approvals</strong>
              <p className="text-xs opacity-70 mt-1">Enforces required human approval counts. Ensures all discussion and review threads are resolved.</p>
            </div>
          </div>
        </section>
      </div>
    ) 
  }
];
