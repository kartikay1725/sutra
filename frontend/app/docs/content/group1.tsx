import React from 'react';
import { DocSection } from './data';
import { ExecutionLifecycleGraph, IdentityAccessFlowGraph } from '@/components/docs_graph_flows';
import { ShieldCheck, Lock, GitBranch, Eye, Workflow, CheckCircle2 } from 'lucide-react';

export const Group1GettingStarted: DocSection[] = [
  {
    id: "getting-started",
    category: "Getting Started",
    title: "SUTRA Architecture & Overview",
    content: (
      <div style={{ display: "flex", flexDirection: "column", gap: 32 }}>
        {/* Overview Section */}
        <section>
          <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 8 }}>
            <span
              style={{
                fontSize: 12,
                fontWeight: 600,
                color: "#F97316",
                background: "rgba(249, 115, 22, 0.1)",
                border: "1px solid rgba(249, 115, 22, 0.25)",
                padding: "2px 8px",
                borderRadius: 4,
                textTransform: "uppercase",
                letterSpacing: "0.05em",
              }}
            >
              AchintAI Control Plane
            </span>
            <span style={{ fontSize: 13, color: "#737373" }}>v1.0 Production Architecture</span>
          </div>

          <h2 style={{ fontSize: 22, fontWeight: 700, color: "#F5F5F5", marginBottom: 12 }}>
            SUTRA — AI-Native Engineering Control Plane
          </h2>
          <p style={{ color: "#A3A3A3", lineHeight: 1.7, marginBottom: 16 }}>
            SUTRA is an <strong style={{ color: "#F5F5F5" }}>AI-Native Engineering Control Plane</strong> developed by <strong style={{ color: "#F5F5F5" }}>AchintAI</strong>.
            It gives autonomous AI coding agents bounded authority, cryptographic commit provenance, and an auditable path from task to merge.
          </p>
          <p style={{ color: "#A3A3A3", lineHeight: 1.7, marginBottom: 20 }}>
            AI agents can write code, run workspace tests, and formulate technical changes. SUTRA governs how they operate: enforcing short-lived session leases, evaluating automated CI verification, blocking self-approval, and ensuring that merge authority remains governed by human review.
          </p>

          {/* Interactive Graph Flow */}
          <ExecutionLifecycleGraph />
        </section>

        {/* Dual Identity Boundary */}
        <section>
          <h3 style={{ fontSize: 18, fontWeight: 700, color: "#F5F5F5", marginBottom: 12 }}>
            Actor & Identity Architecture
          </h3>
          <p style={{ color: "#A3A3A3", lineHeight: 1.7, marginBottom: 16 }}>
            SUTRA strictly separates human account management from autonomous agent execution. Agents operate through bounded, short-lived sessions (15-minute leases with idle timeouts) and cannot approve their own work or authorize merges.
          </p>

          <IdentityAccessFlowGraph />
        </section>

        {/* What SUTRA Controls Section */}
        <section>
          <h3 style={{ fontSize: 18, fontWeight: 700, color: "#F5F5F5", marginBottom: 16 }}>
            Control Plane vs. Substrate Model
          </h3>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))", gap: 14 }}>
            <div style={{ padding: 18, border: "1px solid #242424", borderRadius: 10, background: "#151515" }}>
              <div style={{ display: "flex", alignItems: "center", gap: 8, color: "#3B82F6", fontWeight: 700, marginBottom: 6 }}>
                <ShieldCheck size={16} />
                Agent Identity & Leases
              </div>
              <p style={{ fontSize: 12, color: "#A3A3A3", lineHeight: 1.6, margin: 0 }}>
                Issues temporary 15-minute <code>AgentSession</code> tokens tied to specific tasks with automatic heartbeat extensions.
              </p>
            </div>
            <div style={{ padding: 18, border: "1px solid #242424", borderRadius: 10, background: "#151515" }}>
              <div style={{ display: "flex", alignItems: "center", gap: 8, color: "#F97316", fontWeight: 700, marginBottom: 6 }}>
                <Lock size={16} />
                Capability-Bounded Access
              </div>
              <p style={{ fontSize: 12, color: "#A3A3A3", lineHeight: 1.6, margin: 0 }}>
                Restricts agent permissions via explicit grants (e.g. <code>repository.read</code>, <code>repository.write</code>, <code>change.create</code>).
              </p>
            </div>
            <div style={{ padding: 18, border: "1px solid #242424", borderRadius: 10, background: "#151515" }}>
              <div style={{ display: "flex", alignItems: "center", gap: 8, color: "#22C55E", fontWeight: 700, marginBottom: 6 }}>
                <Workflow size={16} />
                Changes & Commit Provenance
              </div>
              <p style={{ fontSize: 12, color: "#A3A3A3", lineHeight: 1.6, margin: 0 }}>
                Binds commit SHAs to the originating AgentSession and Task, distinguishing agent vs human authorship.
              </p>
            </div>
            <div style={{ padding: 18, border: "1px solid #242424", borderRadius: 10, background: "#151515" }}>
              <div style={{ display: "flex", alignItems: "center", gap: 8, color: "#F59E0B", fontWeight: 700, marginBottom: 6 }}>
                <Eye size={16} />
                Governed Merge Gate
              </div>
              <p style={{ fontSize: 12, color: "#A3A3A3", lineHeight: 1.6, margin: 0 }}>
                Enforces multi-pillar governance, CI check completion, and mandatory human approval before merge execution.
              </p>
            </div>
          </div>
        </section>

        {/* Quickstart Sequence */}
        <section>
          <h3 style={{ fontSize: 18, fontWeight: 700, color: "#F5F5F5", marginBottom: 14 }}>
            Quickstart: Connect and Run in 5 Steps
          </h3>
          <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
            {[
              { step: "1. Connect Repository", desc: "Link an existing GitHub repository from the SUTRA dashboard (/repositories)." },
              { step: "2. Configure MCP", desc: "Add SUTRA's native Streamable HTTP endpoint (/v1/mcp) to Cursor, Claude Code, or Antigravity." },
              { step: "3. Authenticate Agent", desc: "Authenticate via OAuth 2.1 PKCE or an agent session credential to acquire a lease." },
              { step: "4. Autonomous Execution", desc: "The agent claims tasks (sutra_start_task), declares changes, and pushes commits." },
              { step: "5. Human Review & Merge", desc: "Review the resulting pull request in SUTRA, verify CI checks, and approve the merge." },
            ].map((s) => (
              <div key={s.step} style={{ padding: "14px 18px", border: "1px solid #242424", borderRadius: 8, background: "#151515", display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: 8 }}>
                <span style={{ fontSize: 13, fontWeight: 700, color: "#F5F5F5" }}>{s.step}</span>
                <span style={{ fontSize: 13, color: "#A3A3A3" }}>{s.desc}</span>
              </div>
            ))}
          </div>
        </section>
      </div>
    )
  }
];
