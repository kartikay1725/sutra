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

        {/* Git HTTP Flow */}
        <section>
          <h3 style={{ fontSize: 18, fontWeight: 700, color: "#F5F5F5", marginBottom: 12 }}>
            Session-Bound Git HTTP Protocol
          </h3>
          <p style={{ color: "#A3A3A3", lineHeight: 1.7, marginBottom: 16 }}>
            When an external AI agent runs git operations against a SUTRA repository, authentication is validated per HTTP request against the agent's active session and repository permissions.
          </p>

          <GitWorkflowGraph />
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
                <td style={{ fontFamily: "monospace", color: "#3B82F6" }}>changes.create</td>
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
