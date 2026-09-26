import React from 'react';
import { DocSection } from './data';
import { IdentityAccessFlowGraph } from '@/components/docs_graph_flows';
import { DocsHeading, DocsCallout } from '@/components/docs_components';

export const Group2IdentityAccess: DocSection[] = [
  {
    id: "identity-access",
    category: "Identity & Access",
    title: "Identity, Tokens & Capabilities",
    toc: [
      { id: "actor-model", label: "Identity & Actor Model" },
      { id: "agent-sessions", label: "AgentSession Architecture & Leases" },
      { id: "capabilities-matrix", label: "Capabilities Matrix" },
    ],
    content: (
      <div style={{ display: "flex", flexDirection: "column", gap: 32 }}>
        {/* Identity & Actor Model */}
        <section>
          <DocsHeading id="actor-model" level={2}>
            Identity &amp; Actor Model
          </DocsHeading>
          <p style={{ color: "#334155", lineHeight: 1.7, marginBottom: 16 }}>
            SUTRA strictly separates human ownership identities from runtime security identities using the <strong style={{ color: "#0F172A" }}>Actor Model</strong>.
          </p>
          
          <IdentityAccessFlowGraph />

          <table className="table" style={{ marginTop: 20 }}>
            <thead>
              <tr>
                <th>IDENTITY</th>
                <th>ACTOR TYPE</th>
                <th>AUTHENTICATION</th>
                <th>CAPABILITIES</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td style={{ fontWeight: 700, color: "#0F172A" }}>Human User</td>
                <td style={{ fontFamily: "monospace", fontSize: 12, color: "#2563EB" }}>human</td>
                <td>Session JWT</td>
                <td>Full repository &amp; agent management capabilities.</td>
              </tr>
              <tr>
                <td style={{ fontWeight: 700, color: "#0F172A" }}>AI Agent</td>
                <td style={{ fontFamily: "monospace", fontSize: 12, color: "#EA580C" }}>agent</td>
                <td>Basic Auth / Bearer Token</td>
                <td>Strictly scoped by capabilities (e.g. <code>repository.read</code>, <code>repository.write</code>).</td>
              </tr>
              <tr>
                <td style={{ fontWeight: 700, color: "#64748B" }}>System</td>
                <td style={{ fontFamily: "monospace", fontSize: 12, color: "#64748B" }}>system</td>
                <td>Internal</td>
                <td>Automated CI triggers and webhook execution.</td>
              </tr>
            </tbody>
          </table>
        </section>

        {/* AgentSession Leases & Token Architecture */}
        <section>
          <DocsHeading id="agent-sessions" level={2}>
            AgentSession Architecture &amp; Leases
          </DocsHeading>
          <p style={{ color: "#334155", lineHeight: 1.7, marginBottom: 16 }}>
            Agents authenticate using short-lived <strong style={{ color: "#0F172A" }}>AgentSession</strong> leases (<code style={{ color: "#EA580C", background: "#FFF7ED", padding: "1px 5px", borderRadius: 4, border: "1px solid #FED7AA" }}>sutra_session_...</code>) or OAuth 2.1 access tokens (<code style={{ color: "#EA580C", background: "#FFF7ED", padding: "1px 5px", borderRadius: 4, border: "1px solid #FED7AA" }}>sutra_mcp_at_...</code>).
          </p>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))", gap: 14, marginBottom: 20 }}>
            <div style={{ padding: 16, border: "1px solid #E2E8F0", borderRadius: 8, background: "#FFFFFF", boxShadow: "0 1px 3px rgba(0,0,0,0.04)" }}>
              <div style={{ color: "#2563EB", fontWeight: 800, fontSize: 13.5, marginBottom: 4 }}>Absolute TTL: 15 Minutes</div>
              <p style={{ fontSize: 12.5, color: "#475569", margin: 0, lineHeight: 1.55 }}>Every session expires after 15 minutes unless renewed by active task heartbeats.</p>
            </div>
            <div style={{ padding: 16, border: "1px solid #E2E8F0", borderRadius: 8, background: "#FFFFFF", boxShadow: "0 1px 3px rgba(0,0,0,0.04)" }}>
              <div style={{ color: "#EA580C", fontWeight: 800, fontSize: 13.5, marginBottom: 4 }}>Idle TTL: 120 Seconds</div>
              <p style={{ fontSize: 12.5, color: "#475569", margin: 0, lineHeight: 1.55 }}>Sessions expire immediately if an agent becomes inactive without sending requests.</p>
            </div>
            <div style={{ padding: 16, border: "1px solid #E2E8F0", borderRadius: 8, background: "#FFFFFF", boxShadow: "0 1px 3px rgba(0,0,0,0.04)" }}>
              <div style={{ color: "#2563EB", fontWeight: 800, fontSize: 13.5, marginBottom: 4 }}>Task Binding</div>
              <p style={{ fontSize: 12.5, color: "#475569", margin: 0, lineHeight: 1.55 }}>Sessions are tightly coupled to the claimed task and repository scope.</p>
            </div>
          </div>

          <DocsCallout type="security" title="Critical Architecture Rule: Instructions vs. Server-Side Enforcement">
            Instruction files like <code style={{ color: "#0F172A", background: "#FFFFFF", padding: "1px 4px", borderRadius: 3 }}>AGENTS.md</code> or <code style={{ color: "#0F172A", background: "#FFFFFF", padding: "1px 4px", borderRadius: 3 }}>.cursorrules</code> are prompt guidance for coding models — <strong>they are NOT the security boundary</strong>. SUTRA server-side token authentication, capability checks, commit provenance verification, and human review gates are enforced at the API and control-plane layer. Removing an instruction file does NOT remove or bypass SUTRA governance.
          </DocsCallout>
        </section>

        {/* Capabilities Matrix */}
        <section>
          <DocsHeading id="capabilities-matrix" level={2}>
            Capabilities Matrix
          </DocsHeading>
          <p style={{ color: "#334155", lineHeight: 1.7, marginBottom: 16 }}>
            Every Agent Actor has an explicit list of capabilities. If a capability is missing or revoked, the action is blocked immediately.
          </p>
          <table className="table">
            <thead>
              <tr>
                <th>CAPABILITY</th>
                <th>ALLOWS</th>
                <th>BLOCKED / FORBIDDEN</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td style={{ fontFamily: "monospace", color: "#2563EB", fontWeight: 600 }}>repository.read</td>
                <td>Clone, fetch, read files &amp; commit trees</td>
                <td>Pushing branches or modifying tags</td>
              </tr>
              <tr>
                <td style={{ fontFamily: "monospace", color: "#2563EB", fontWeight: 600 }}>repository.write</td>
                <td>Pushing to feature branches</td>
                <td>Bypassing branch protection or force-pushing</td>
              </tr>
              <tr>
                <td style={{ fontFamily: "monospace", color: "#2563EB", fontWeight: 600 }}>change.create</td>
                <td>Creating Pull Requests &amp; Changes</td>
                <td>Self-approving Pull Requests</td>
              </tr>
              <tr>
                <td style={{ fontFamily: "monospace", color: "#2563EB", fontWeight: 600 }}>workflow.write</td>
                <td>Modifying CI/CD pipelines (.github/workflows/*)</td>
                <td>Bypassing branch rules or workflow run tampering</td>
              </tr>
              <tr>
                <td style={{ fontFamily: "monospace", color: "#2563EB", fontWeight: 600 }}>discussion.create</td>
                <td>Proposing architecture RFCs &amp; participating in discussion threads</td>
                <td>Deleting discussion channels or unverified posts</td>
              </tr>
            </tbody>
          </table>
        </section>
      </div>
    )
  }
];
