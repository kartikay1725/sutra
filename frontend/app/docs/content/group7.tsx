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
          <h2 className="text-xl font-bold mb-4">Security Model</h2>
          <p className="mb-4">SUTRA strictly enforces boundaries through Authentication, Authorization, Ownership, and Capability Checks. The system is designed under a Zero-Trust architecture for AI Agents.</p>
        </section>

        <section>
          <h3 className="text-lg font-bold mb-4">Agent Limits & Boundaries</h3>
          <p className="mb-4">The following actions are explicitly prohibited and cryptographically blocked by SUTRA:</p>
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
                <td className="font-mono text-red-400 text-xs">Cross-Owner Repository Access</td>
                <td>Actor isolation limits queries to explicitly authorized scopes.</td>
                <td>Returns a 404 Not Found (to prevent existence leakage).</td>
              </tr>
              <tr>
                <td className="font-mono text-red-400 text-xs">Force Push</td>
                <td>Git Pre-Receive Hook rejects all non-fast-forward updates.</td>
                <td>Git push is rejected with a fatal policy error.</td>
              </tr>
              <tr>
                <td className="font-mono text-red-400 text-xs">Self Approval</td>
                <td>AuthorizationService blocks agents from approving PRs they opened.</td>
                <td>API returns 403 Forbidden.</td>
              </tr>
            </tbody>
          </table>
        </section>

        <section>
          <h3 className="text-lg font-bold mb-4">Git Security & CI Isolation</h3>
          <p className="mb-4">All Git HTTP requests pass through <code>git_http.py</code>, which verifies credentials and validates <code>repository.read</code> and <code>repository.write</code> capabilities before invoking <code>git-http-backend</code>.</p>
          <p>CI pipelines run in isolated environments. SUTRA strips secrets from PRs submitted by agents until explicit human approval is granted.</p>
        </section>
      </div>
    ) 
  }
];
