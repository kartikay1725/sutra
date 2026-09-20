import React from 'react';
import { DocSection } from './data';
import { IdentityAccessFlowGraph, GitWorkflowGraph } from '@/components/docs_graph_flows';
import { ShieldCheck, Cpu, Key, Lock, Terminal } from 'lucide-react';

export const Group2IdentityAccess: DocSection[] = [
  {
    id: "identity-access",
    category: "Identity & Access",
    title: "Identity, Tokens & Capabilities",
    content: (
      <div style={{ display: "flex", flexDirection: "column", gap: 32 }}>
        {/* Identity & Actor Model */}
        <section>
          <h2 style={{ fontSize: 20, fontWeight: 700, color: "#F5F5F5", marginBottom: 12 }}>
            Identity & Actor Model
          </h2>
          <p style={{ color: "#A3A3A3", lineHeight: 1.7, marginBottom: 16 }}>
            SUTRA strictly separates human ownership identities from runtime security identities using the <strong style={{ color: "#F5F5F5" }}>Actor Model</strong>.
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
                <td style={{ fontWeight: 700, color: "#F5F5F5" }}>Human User</td>
                <td style={{ fontFamily: "monospace", fontSize: 12, color: "#3B82F6" }}>human</td>
                <td>Session JWT</td>
                <td>Full repository & agent management capabilities.</td>
              </tr>
              <tr>
                <td style={{ fontWeight: 700, color: "#F5F5F5" }}>AI Agent</td>
                <td style={{ fontFamily: "monospace", fontSize: 12, color: "#F97316" }}>agent</td>
                <td>Basic Auth / Bearer Token</td>
                <td>Strictly scoped by capabilities (e.g. <code>repository.read</code>, <code>repository.write</code>).</td>
              </tr>
              <tr>
                <td style={{ fontWeight: 700, color: "#737373" }}>System</td>
                <td style={{ fontFamily: "monospace", fontSize: 12, color: "#737373" }}>system</td>
                <td>Internal</td>
                <td>Automated CI triggers and webhook execution.</td>
              </tr>
            </tbody>
          </table>
        </section>

        {/* AgentSession Leases & Token Architecture */}
        <section>
          <h3 style={{ fontSize: 18, fontWeight: 700, color: "#F5F5F5", marginBottom: 12 }}>
            AgentSession Architecture & Leases
          </h3>
          <p style={{ color: "#A3A3A3", lineHeight: 1.7, marginBottom: 16 }}>
            Agents authenticate using short-lived <strong style={{ color: "#F5F5F5" }}>AgentSession</strong> leases (<code style={{ color: "#F97316" }}>sutra_session_...</code>) or OAuth 2.1 access tokens (<code style={{ color: "#F97316" }}>sutra_mcp_at_...</code>).
          </p>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))", gap: 14, marginBottom: 20 }}>
            <div style={{ padding: 16, border: "1px solid #242424", borderRadius: 8, background: "#151515" }}>
              <div style={{ color: "#3B82F6", fontWeight: 700, fontSize: 13, marginBottom: 4 }}>Absolute TTL: 15 Minutes</div>
              <p style={{ fontSize: 12, color: "#A3A3A3", margin: 0 }}>Every session expires after 15 minutes unless renewed by active task heartbeats.</p>
            </div>
            <div style={{ padding: 16, border: "1px solid #242424", borderRadius: 8, background: "#151515" }}>
              <div style={{ color: "#F97316", fontWeight: 700, fontSize: 13, marginBottom: 4 }}>Idle TTL: 120 Seconds</div>
              <p style={{ fontSize: 12, color: "#A3A3A3", margin: 0 }}>Sessions expire immediately if an agent becomes inactive without sending requests.</p>
            </div>
            <div style={{ padding: 16, border: "1px solid #242424", borderRadius: 8, background: "#151515" }}>
              <div style={{ color: "#22C55E", fontWeight: 700, fontSize: 13, marginBottom: 4 }}>Task Binding</div>
              <p style={{ fontSize: 12, color: "#A3A3A3", margin: 0 }}>Sessions are tightly coupled to the claimed task and repository scope.</p>
            </div>
          </div>
          <div style={{ padding: 16, border: "1px solid rgba(239, 68, 68, 0.3)", borderRadius: 8, background: "rgba(239, 68, 68, 0.05)", marginBottom: 16 }}>
            <div style={{ color: "#EF4444", fontWeight: 700, fontSize: 13, marginBottom: 4 }}>
              Critical Architecture Rule: Instructions vs. Server-Side Enforcement
            </div>
            <p style={{ fontSize: 12, color: "#A3A3A3", lineHeight: 1.6, margin: 0 }}>
              Instruction files like <code style={{ color: "#F5F5F5" }}>AGENTS.md</code> or <code style={{ color: "#F5F5F5" }}>.cursorrules</code> are prompt guidance for coding models — <strong>they are NOT the security boundary</strong>. SUTRA server-side token authentication, capability checks, commit provenance verification, and human review gates are enforced at the API and control-plane layer. Removing an instruction file does NOT remove or bypass SUTRA governance.
            </p>
          </div>
        </section>

        {/* Capabilities Matrix */}
        <section>
          <h3 style={{ fontSize: 18, fontWeight: 700, color: "#F5F5F5", marginBottom: 12 }}>
            Capabilities Matrix
          </h3>
          <p style={{ color: "#A3A3A3", lineHeight: 1.7, marginBottom: 16 }}>
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
                <td style={{ fontFamily: "monospace", color: "#3B82F6" }}>repository.read</td>
                <td>Clone, fetch, read files & commit trees</td>
                <td>Pushing branches or modifying tags</td>
              </tr>
              <tr>
                <td style={{ fontFamily: "monospace", color: "#3B82F6" }}>repository.write</td>
                <td>Pushing to feature branches</td>
                <td>Bypassing branch protection or force-pushing</td>
              </tr>
              <tr>
                <td style={{ fontFamily: "monospace", color: "#3B82F6" }}>change.create</td>
                <td>Creating Pull Requests & Changes</td>
                <td>Self-approving Pull Requests</td>
              </tr>
              <tr>
                <td style={{ fontFamily: "monospace", color: "#3B82F6" }}>workflow.write</td>
                <td>Modifying CI/CD pipelines (.github/workflows/*)</td>
                <td>Bypassing branch rules or workflow run tampering</td>
              </tr>
              <tr>
                <td style={{ fontFamily: "monospace", color: "#3B82F6" }}>discussion.create</td>
                <td>Proposing architecture RFCs & participating in discussion threads</td>
                <td>Deleting discussion channels or unverified posts</td>
              </tr>
            </tbody>
          </table>
        </section>
      </div>
    )
  }
];
