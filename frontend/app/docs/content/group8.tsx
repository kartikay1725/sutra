import React from 'react';
import { DocSection } from './data';
import { DocsHeading } from '@/components/docs_components';

export const Group8Reference: DocSection[] = [
  { 
    id: "reference", 
    category: "Reference", 
    title: "Reference", 
    toc: [
      { id: "lifecycle-states", label: "Engineering Lifecycle & States" },
      { id: "terminology", label: "Terminology & Concepts" },
      { id: "troubleshooting", label: "Troubleshooting & Common Issues" },
      { id: "limitations", label: "Current Implementation Limits" },
    ],
    content: (
      <div className="flex flex-col gap-10">
        <section>
          <DocsHeading id="lifecycle-states" level={2}>
            Engineering Lifecycle & States
          </DocsHeading>
          <table className="table mt-4">
            <thead>
              <tr>
                <th>STATE</th>
                <th>MEANING</th>
                <th>ALLOWED NEXT STATES</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td className="font-mono text-xs">Open</td>
                <td>PR is actively being worked on.</td>
                <td>Reviewing, Closed</td>
              </tr>
              <tr>
                <td className="font-mono text-xs">Reviewing</td>
                <td>Human/Agent is reviewing code.</td>
                <td>Approved, Blocked (Changes Requested)</td>
              </tr>
              <tr>
                <td className="font-mono text-xs">Merged</td>
                <td>Cryptographic merge executed.</td>
                <td>Terminal state.</td>
              </tr>
            </tbody>
          </table>
        </section>

        <section>
          <DocsHeading id="terminology" level={2}>
            Terminology
          </DocsHeading>
          <div className="flex flex-col gap-4">
            <div>
              <h4 className="font-bold text-[var(--accent)]">Actor vs User</h4>
              <p className="text-sm opacity-80 mt-1">A User is a human database identity. An Actor is the runtime security context that SUTRA uses to authorize API calls. Agents have Actors but are not Users.</p>
            </div>
            <div>
              <h4 className="font-bold text-[var(--accent)]">Commit vs Change</h4>
              <p className="text-sm opacity-80 mt-1">A Commit is raw Git data. A Change is a SUTRA entity that links commits to PRs, Reviews, and CI Jobs.</p>
            </div>
          </div>
        </section>

        <section>
          <DocsHeading id="troubleshooting" level={2}>
            Troubleshooting & Common Issues
          </DocsHeading>
          <table className="table mt-4">
            <thead>
              <tr>
                <th>ISSUE</th>
                <th>ROOT CAUSE</th>
                <th>RESOLUTION</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td className="font-mono text-xs text-orange-400">MCP 401 on tool invocation</td>
                <td>OAuth token or AgentSession lease expired after 15 minutes.</td>
                <td>Re-trigger OAuth authorization in client or refresh via <code>/oauth/token</code>.</td>
              </tr>
              <tr>
                <td className="font-mono text-xs text-orange-400">PR merge button disabled</td>
                <td>Governance verdict is not <code>READY_FOR_MERGE</code> (e.g. failing CI or missing human approval).</td>
                <td>Inspect <code>/pull-requests/[id]</code> governance card for active blockers.</td>
              </tr>
              <tr>
                <td className="font-mono text-xs text-orange-400">Approval invalidated</td>
                <td>A new commit was pushed to the branch, changing the HEAD SHA.</td>
                <td>Re-review the latest diff and click Approve again in SUTRA.</td>
              </tr>
            </tbody>
          </table>
        </section>

        <section>
          <DocsHeading id="limitations" level={2}>
            Current Limitations
          </DocsHeading>
          <p className="mb-4">This section outlines verified limitations in the current implementation to maintain transparency.</p>
          <table className="table mt-4">
            <thead>
              <tr>
                <th>CAPABILITY</th>
                <th>STATUS</th>
                <th>LIMITATION</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td className="font-mono text-xs text-orange-400">Agent Token Rotation</td>
                <td>API ONLY</td>
                <td>No UI currently exists in the dashboard to rotate tokens. You must use the API.</td>
              </tr>
              <tr>
                <td className="font-mono text-xs text-orange-400">Substrate Support</td>
                <td>GITHUB NATIVE</td>
                <td>GitHub is the primary production substrate. GitLab and Bitbucket adapters are in development.</td>
              </tr>
            </tbody>
          </table>
        </section>
      </div>
    ) 
  }
];
