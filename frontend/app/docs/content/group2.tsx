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
          <h2 style={{ fontSize: 20, fontWeight: 700, color: "#F2F5F8", marginBottom: 12 }}>
            Identity & Actor Model
          </h2>
          <p style={{ color: "#A8B1BD", lineHeight: 1.7, marginBottom: 16 }}>
            SUTRA strictly separates human ownership identities from runtime security identities using the <strong style={{ color: "#F2F5F8" }}>Actor Model</strong>.
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
                <td style={{ fontWeight: 700, color: "#F2F5F8" }}>Human User</td>
                <td style={{ fontFamily: "monospace", fontSize: 12, color: "#60A5FA" }}>human</td>
                <td>Session JWT</td>
                <td>Full repository & agent management capabilities.</td>
              </tr>
              <tr>
                <td style={{ fontWeight: 700, color: "#F2F5F8" }}>AI Agent</td>
                <td style={{ fontFamily: "monospace", fontSize: 12, color: "#818CF8" }}>agent</td>
                <td>Basic Auth / Bearer Token</td>
                <td>Strictly scoped by capabilities (e.g. <code>repository.read</code>, <code>repository.write</code>).</td>
              </tr>
              <tr>
                <td style={{ fontWeight: 700, color: "#707A88" }}>System</td>
                <td style={{ fontFamily: "monospace", fontSize: 12, color: "#707A88" }}>system</td>
                <td>Internal</td>
                <td>Automated CI triggers and webhook execution.</td>
              </tr>
            </tbody>
          </table>
        </section>

        {/* Git HTTP Flow */}
        <section>
          <h3 style={{ fontSize: 18, fontWeight: 700, color: "#F2F5F8", marginBottom: 12 }}>
            Session-Bound Git HTTP Protocol
          </h3>
          <p style={{ color: "#A8B1BD", lineHeight: 1.7, marginBottom: 16 }}>
            When an external AI agent runs git operations against a SUTRA repository, authentication is validated per HTTP request against the agent's active session and repository permissions.
          </p>

          <GitWorkflowGraph />
        </section>

        {/* Capabilities Matrix */}
        <section>
          <h3 style={{ fontSize: 18, fontWeight: 700, color: "#F2F5F8", marginBottom: 12 }}>
            Capabilities Matrix
          </h3>
          <p style={{ color: "#A8B1BD", lineHeight: 1.7, marginBottom: 16 }}>
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
                <td style={{ fontFamily: "monospace", color: "#60A5FA" }}>repository.read</td>
                <td>Clone, fetch, read files & commit trees</td>
                <td>Pushing branches or modifying tags</td>
              </tr>
              <tr>
                <td style={{ fontFamily: "monospace", color: "#60A5FA" }}>repository.write</td>
                <td>Pushing to feature branches</td>
                <td>Bypassing branch protection or force-pushing</td>
              </tr>
              <tr>
                <td style={{ fontFamily: "monospace", color: "#60A5FA" }}>changes.create</td>
                <td>Creating Pull Requests & Changes</td>
                <td>Self-approving Pull Requests</td>
              </tr>
            </tbody>
          </table>
        </section>
      </div>
    )
  }
];
