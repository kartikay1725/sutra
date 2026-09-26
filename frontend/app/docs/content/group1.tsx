import React from 'react';
import { DocSection } from './data';
import { ExecutionLifecycleGraph, IdentityAccessFlowGraph } from '@/components/docs_graph_flows';
import {
  ShieldCheck,
  Lock,
  GitBranch,
  Eye,
  Workflow,
  CheckCircle2,
  ArrowRight,
  Terminal,
  Cpu,
  Layers,
  Sparkles,
  ExternalLink,
  FileCode,
} from 'lucide-react';
import { DocsHeading, DocsCallout, DocsCodeBlock } from '@/components/docs_components';

export const Group1GettingStarted: DocSection[] = [
  {
    id: "getting-started",
    category: "Getting Started",
    title: "SUTRA Architecture & Overview",
    toc: [
      { id: "overview", label: "Architecture Overview" },
      { id: "control-plane", label: "Control Plane vs. Substrate" },
      { id: "identity-boundary", label: "Actor & Identity Model" },
      { id: "quickstart", label: "Quickstart in 5 Steps" },
      { id: "next-steps", label: "Next Steps" },
    ],
    content: (
      <div style={{ display: "flex", flexDirection: "column", gap: 36 }}>
        {/* Top Hero Banner & Architecture Tag */}
        <section>
          <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 12 }}>
            <span
              style={{
                fontSize: 11,
                fontWeight: 700,
                color: "#F97316",
                background: "rgba(249, 115, 22, 0.1)",
                border: "1px solid rgba(249, 115, 22, 0.25)",
                padding: "3px 9px",
                borderRadius: 4,
                textTransform: "uppercase",
                letterSpacing: "0.06em",
              }}
            >
              AchintAI Control Plane
            </span>
            <span style={{ fontSize: 12, color: "#64748B" }}>v1.0 Production Architecture</span>
          </div>

          <DocsHeading id="overview" level={2} style={{ marginTop: 0 }}>
            SUTRA — AI-Native Engineering Control Plane
          </DocsHeading>

          <p style={{ color: "#334155", fontSize: 14.5, lineHeight: 1.7, marginBottom: 16 }}>
            SUTRA is an <strong style={{ color: "#0F172A" }}>AI-Native Engineering Control Plane</strong> developed by <strong style={{ color: "#0F172A" }}>AchintAI</strong>.
            It provides autonomous AI coding agents with bounded authority, cryptographic commit provenance, and an auditable path from task to merge.
          </p>
          <p style={{ color: "#475569", lineHeight: 1.7, marginBottom: 20 }}>
            Autonomous agents excel at writing code, running local tests, and formulating technical solutions. SUTRA governs how they operate within your engineering organization: enforcing short-lived session leases, evaluating automated CI verification, blocking self-approval, and ensuring that merge authority remains governed by human review.
          </p>

          {/* 4 Architectural Guarantee Cards */}
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))",
              gap: 12,
              marginBottom: 24,
            }}
          >
            {[
              {
                title: "15m Lease TTL",
                desc: "Ephemeral AgentSession tokens with 120-second idle timeouts.",
                badge: "Session Security",
                color: "#2563EB",
                icon: ShieldCheck,
              },
              {
                title: "Zero Self-Approval",
                desc: "Agents cannot approve their own pull requests or trigger merges.",
                badge: "Human Gate",
                color: "#EA580C",
                icon: Lock,
              },
              {
                title: "Commit Provenance",
                desc: "Cryptographic linkage between Git commits, AgentSessions, and Tasks.",
                badge: "Audit Chain",
                color: "#2563EB",
                icon: Workflow,
              },
              {
                title: "Protected Merge",
                desc: "Multi-pillar checks and human owner sign-off required for branch merge.",
                badge: "Governance Gate",
                color: "#EA580C",
                icon: Eye,
              },
            ].map((card) => {
              const Icon = card.icon;
              return (
                <div
                  key={card.title}
                  style={{
                    background: "#FFFFFF",
                    border: "1px solid #E2E8F0",
                    borderRadius: 8,
                    padding: "16px 18px",
                    display: "flex",
                    flexDirection: "column",
                    justifyContent: "space-between",
                    boxShadow: "0 1px 3px rgba(0, 0, 0, 0.04)",
                  }}
                >
                  <div>
                    <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 8 }}>
                      <div
                        style={{
                          width: 30,
                          height: 30,
                          borderRadius: 6,
                          background: `${card.color}15`,
                          border: `1px solid ${card.color}30`,
                          display: "flex",
                          alignItems: "center",
                          justifyContent: "center",
                          color: card.color,
                        }}
                      >
                        <Icon size={15} />
                      </div>
                      <span
                        style={{
                          fontSize: 10,
                          fontWeight: 700,
                          color: card.color,
                          textTransform: "uppercase",
                          letterSpacing: "0.04em",
                        }}
                      >
                        {card.badge}
                      </span>
                    </div>
                    <div style={{ fontSize: 14, fontWeight: 800, color: "#0F172A", marginBottom: 4 }}>
                      {card.title}
                    </div>
                    <p style={{ fontSize: 12, color: "#475569", lineHeight: 1.55, margin: 0 }}>
                      {card.desc}
                    </p>
                  </div>
                </div>
              );
            })}
          </div>

          {/* Interactive Graph Flow */}
          <ExecutionLifecycleGraph />
        </section>

        {/* Control Plane vs. Code Substrate */}
        <section>
          <DocsHeading id="control-plane" level={2}>
            Control Plane vs. Code Substrate Model
          </DocsHeading>
          <p style={{ color: "#334155", lineHeight: 1.7, marginBottom: 16 }}>
            A critical architectural distinction in SUTRA is the boundary between the <strong style={{ color: "#0F172A" }}>Control Plane</strong> and the <strong style={{ color: "#0F172A" }}>Code Substrate</strong>. SUTRA does not replace GitHub; SUTRA governs what autonomous agents do across GitHub.
          </p>

          {/* Substrate Comparison Table / Cards */}
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))",
              gap: 14,
              marginBottom: 20,
            }}
          >
            {/* GitHub Substrate */}
            <div
              style={{
                background: "#FFFFFF",
                border: "1px solid #E2E8F0",
                borderRadius: 10,
                padding: "18px 20px",
                boxShadow: "0 1px 3px rgba(0, 0, 0, 0.04)",
              }}
            >
              <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 12 }}>
                <div
                  style={{
                    width: 34,
                    height: 34,
                    borderRadius: 8,
                    background: "#EFF6FF",
                    border: "1px solid #BFDBFE",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    color: "#2563EB",
                  }}
                >
                  <GitBranch size={16} />
                </div>
                <div>
                  <div style={{ fontSize: 14, fontWeight: 800, color: "#0F172A" }}>GitHub (Code Substrate)</div>
                  <div style={{ fontSize: 11.5, color: "#64748B" }}>Storage &amp; Version Control Foundation</div>
                </div>
              </div>

              <div style={{ display: "flex", flexDirection: "column", gap: 8, fontSize: 12.5, color: "#334155" }}>
                <div style={{ display: "flex", alignItems: "flex-start", gap: 8 }}>
                  <span style={{ color: "#2563EB", fontWeight: 700 }}>•</span>
                  <span>Hosts Git repositories, branches, commits, and AST trees.</span>
                </div>
                <div style={{ display: "flex", alignItems: "flex-start", gap: 8 }}>
                  <span style={{ color: "#2563EB", fontWeight: 700 }}>•</span>
                  <span>Provides workspace clone URLs and pull request diff views.</span>
                </div>
                <div style={{ display: "flex", alignItems: "flex-start", gap: 8 }}>
                  <span style={{ color: "#2563EB", fontWeight: 700 }}>•</span>
                  <span>Executes GitHub Actions workflows and dispatches check webhooks.</span>
                </div>
              </div>
            </div>

            {/* SUTRA Control Plane */}
            <div
              style={{
                background: "#FFFFFF",
                border: "1px solid #E2E8F0",
                borderRadius: 10,
                padding: "18px 20px",
                boxShadow: "0 1px 3px rgba(0, 0, 0, 0.04)",
              }}
            >
              <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 12 }}>
                <div
                  style={{
                    width: 34,
                    height: 34,
                    borderRadius: 8,
                    background: "#FFF7ED",
                    border: "1px solid #FED7AA",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    color: "#EA580C",
                  }}
                >
                  <ShieldCheck size={16} />
                </div>
                <div>
                  <div style={{ fontSize: 14, fontWeight: 800, color: "#0F172A" }}>SUTRA (Control Plane)</div>
                  <div style={{ fontSize: 11.5, color: "#64748B" }}>Policy, Provenance &amp; Merge Authority</div>
                </div>
              </div>

              <div style={{ display: "flex", flexDirection: "column", gap: 8, fontSize: 12.5, color: "#334155" }}>
                <div style={{ display: "flex", alignItems: "flex-start", gap: 8 }}>
                  <span style={{ color: "#EA580C", fontWeight: 700 }}>•</span>
                  <span>Provisions bounded tasks, short-lived session leases, and capability grants.</span>
                </div>
                <div style={{ display: "flex", alignItems: "flex-start", gap: 8 }}>
                  <span style={{ color: "#EA580C", fontWeight: 700 }}>•</span>
                  <span>Records cryptographic commit provenance linking commits to specific agent sessions.</span>
                </div>
                <div style={{ display: "flex", alignItems: "flex-start", gap: 8 }}>
                  <span style={{ color: "#EA580C", fontWeight: 700 }}>•</span>
                  <span>Enforces four-pillar governance rules and strictly blocks agent self-approval.</span>
                </div>
              </div>
            </div>
          </div>

          {/* 4 Architectural Pillar Cards */}
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))", gap: 14 }}>
            <div style={{ padding: 18, border: "1px solid #E2E8F0", borderRadius: 10, background: "#FFFFFF", boxShadow: "0 1px 3px rgba(0, 0, 0, 0.04)" }}>
              <div style={{ display: "flex", alignItems: "center", gap: 8, color: "#2563EB", fontWeight: 700, marginBottom: 6 }}>
                <ShieldCheck size={16} />
                <span style={{ color: "#0F172A", fontWeight: 700 }}>Agent Identity &amp; Leases</span>
              </div>
              <p style={{ fontSize: 12.5, color: "#475569", lineHeight: 1.6, margin: 0 }}>
                Issues temporary 15-minute <code style={{ color: "#2563EB", background: "#EFF6FF", padding: "1px 5px", borderRadius: 4, border: "1px solid #BFDBFE" }}>AgentSession</code> tokens tied to specific tasks with automatic heartbeat extensions.
              </p>
            </div>

            <div style={{ padding: 18, border: "1px solid #E2E8F0", borderRadius: 10, background: "#FFFFFF", boxShadow: "0 1px 3px rgba(0, 0, 0, 0.04)" }}>
              <div style={{ display: "flex", alignItems: "center", gap: 8, color: "#EA580C", fontWeight: 700, marginBottom: 6 }}>
                <Lock size={16} />
                <span style={{ color: "#0F172A", fontWeight: 700 }}>Capability-Bounded Access</span>
              </div>
              <p style={{ fontSize: 12.5, color: "#475569", lineHeight: 1.6, margin: 0 }}>
                Restricts agent permissions via explicit grants (e.g. <code style={{ color: "#EA580C", background: "#FFF7ED", padding: "1px 5px", borderRadius: 4, border: "1px solid #FED7AA" }}>repository.read</code>, <code style={{ color: "#EA580C", background: "#FFF7ED", padding: "1px 5px", borderRadius: 4, border: "1px solid #FED7AA" }}>repository.write</code>).
              </p>
            </div>

            <div style={{ padding: 18, border: "1px solid #E2E8F0", borderRadius: 10, background: "#FFFFFF", boxShadow: "0 1px 3px rgba(0, 0, 0, 0.04)" }}>
              <div style={{ display: "flex", alignItems: "center", gap: 8, color: "#2563EB", fontWeight: 700, marginBottom: 6 }}>
                <Workflow size={16} />
                <span style={{ color: "#0F172A", fontWeight: 700 }}>Changes &amp; Commit Provenance</span>
              </div>
              <p style={{ fontSize: 12.5, color: "#475569", lineHeight: 1.6, margin: 0 }}>
                Binds commit SHAs to the originating AgentSession and Task, distinguishing agent vs. human authorship.
              </p>
            </div>

            <div style={{ padding: 18, border: "1px solid #E2E8F0", borderRadius: 10, background: "#FFFFFF", boxShadow: "0 1px 3px rgba(0, 0, 0, 0.04)" }}>
              <div style={{ display: "flex", alignItems: "center", gap: 8, color: "#EA580C", fontWeight: 700, marginBottom: 6 }}>
                <Eye size={16} />
                <span style={{ color: "#0F172A", fontWeight: 700 }}>Governed Merge Gate</span>
              </div>
              <p style={{ fontSize: 12.5, color: "#475569", lineHeight: 1.6, margin: 0 }}>
                Enforces multi-pillar governance, CI check completion, and mandatory human approval before merge execution.
              </p>
            </div>
          </div>
        </section>

        {/* Dual Identity Boundary */}
        <section>
          <DocsHeading id="identity-boundary" level={2}>
            Actor &amp; Identity Architecture
          </DocsHeading>
          <p style={{ color: "#334155", lineHeight: 1.7, marginBottom: 16 }}>
            SUTRA strictly enforces separate runtime identities for human engineers and autonomous agents. Agents operate through bounded, short-lived sessions (15-minute leases with idle timeouts) and cannot approve their own work or authorize merges.
          </p>

          <DocsCallout type="security" title="Critical Architecture Invariant: Prompt Guidance vs. Server-Side Enforcement">
            Instruction files such as <code style={{ color: "#F0F6FC" }}>AGENTS.md</code> or <code style={{ color: "#F0F6FC" }}>.cursorrules</code> provide prompt guidance for coding models — <strong>they are NOT the security boundary</strong>. SUTRA server-side token authentication, capability checks, commit provenance verification, and human review gates are enforced at the API and control-plane layer. Removing an instruction file does NOT remove or bypass SUTRA governance.
          </DocsCallout>

          <IdentityAccessFlowGraph />
        </section>

        {/* Redesigned Quickstart Sequence */}
        <section>
          <DocsHeading id="quickstart" level={2}>
            Quickstart: Connect and Run in 5 Steps
          </DocsHeading>
          <p style={{ color: "#475569", lineHeight: 1.7, marginBottom: 18 }}>
            Follow this 5-step sequence to link your repository, connect your autonomous coding agent via Model Context Protocol (MCP), and execute governed engineering workflows.
          </p>

          <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
            {/* Step 1 */}
            <div
              style={{
                background: "#FFFFFF",
                border: "1px solid #E2E8F0",
                borderRadius: 10,
                padding: "18px 20px",
                boxShadow: "0 1px 3px rgba(0, 0, 0, 0.04)",
              }}
            >
              <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 8 }}>
                <span
                  style={{
                    fontSize: 11,
                    fontWeight: 700,
                    fontFamily: "var(--font-mono, monospace)",
                    padding: "2px 7px",
                    borderRadius: 4,
                    background: "#FFF7ED",
                    border: "1px solid #FED7AA",
                    color: "#EA580C",
                  }}
                >
                  STEP 01
                </span>
                <span style={{ fontSize: 14.5, fontWeight: 800, color: "#0F172A" }}>
                  Link Repository in SUTRA
                </span>
              </div>
              <p style={{ fontSize: 13, color: "#334155", lineHeight: 1.6, margin: "0 0 10px 0" }}>
                Navigate to the SUTRA Repositories page (<code style={{ color: "#0284C7", background: "#EFF6FF", padding: "1px 5px", borderRadius: 4, border: "1px solid #BFDBFE" }}>/repositories</code>) and select an authorized GitHub repository. SUTRA indexes branch protection settings, establishes webhook listeners for CI checks, and prepares the audit log.
              </p>
              <div style={{ fontSize: 11.5, color: "#64748B" }}>
                Target: <span style={{ color: "#0F172A", fontWeight: 600 }}>https://sutra.sudarshanai.com/repositories</span>
              </div>
            </div>

            {/* Step 2 */}
            <div
              style={{
                background: "#FFFFFF",
                border: "1px solid #E2E8F0",
                borderRadius: 10,
                padding: "18px 20px",
                boxShadow: "0 1px 3px rgba(0, 0, 0, 0.04)",
              }}
            >
              <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 8 }}>
                <span
                  style={{
                    fontSize: 11,
                    fontWeight: 700,
                    fontFamily: "var(--font-mono, monospace)",
                    padding: "2px 7px",
                    borderRadius: 4,
                    background: "#EFF6FF",
                    border: "1px solid #BFDBFE",
                    color: "#2563EB",
                  }}
                >
                  STEP 02
                </span>
                <span style={{ fontSize: 14.5, fontWeight: 800, color: "#0F172A" }}>
                  Configure Model Context Protocol (MCP) in IDE / Agent
                </span>
              </div>
              <p style={{ fontSize: 13, color: "#334155", lineHeight: 1.6, margin: "0 0 10px 0" }}>
                Add SUTRA's native Streamable HTTP MCP endpoint to your coding agent configuration (e.g., Cursor, Claude Code, Antigravity, or Cline).
              </p>
              <DocsCodeBlock
                code={`{
  "mcpServers": {
    "sutra": {
      "url": "https://api.sutra.sudarshanai.com/v1/mcp"
    }
  }
}`}
                language="json"
                filename="mcp_config.json"
                style={{ margin: "10px 0 0 0" }}
              />
            </div>

            {/* Step 3 */}
            <div
              style={{
                background: "#FFFFFF",
                border: "1px solid #E2E8F0",
                borderRadius: 10,
                padding: "18px 20px",
                boxShadow: "0 1px 3px rgba(0, 0, 0, 0.04)",
              }}
            >
              <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 8 }}>
                <span
                  style={{
                    fontSize: 11,
                    fontWeight: 700,
                    fontFamily: "var(--font-mono, monospace)",
                    padding: "2px 7px",
                    borderRadius: 4,
                    background: "#FFF7ED",
                    border: "1px solid #FED7AA",
                    color: "#EA580C",
                  }}
                >
                  STEP 03
                </span>
                <span style={{ fontSize: 14.5, fontWeight: 800, color: "#0F172A" }}>
                  Authenticate Agent &amp; Receive Session Lease
                </span>
              </div>
              <p style={{ fontSize: 13, color: "#334155", lineHeight: 1.6, margin: "0 0 10px 0" }}>
                The agent initiates OAuth 2.1 PKCE against <code style={{ color: "#0284C7", background: "#EFF6FF", padding: "1px 5px", borderRadius: 4, border: "1px solid #BFDBFE" }}>/oauth/token</code> or authenticates via an Agent Token to receive a temporary 15-minute <code style={{ color: "#EA580C", background: "#FFF7ED", padding: "1px 5px", borderRadius: 4, border: "1px solid #FED7AA" }}>AgentSession</code> lease.
              </p>
              <div style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 11.5, color: "#64748B" }}>
                <span>Bearer Token: <code style={{ color: "#EA580C" }}>sutra_session_...</code></span>
                <span>•</span>
                <span>Idle Timeout: <strong style={{ color: "#0F172A" }}>120s</strong></span>
                <span>•</span>
                <span>Absolute TTL: <strong style={{ color: "#0F172A" }}>15m</strong></span>
              </div>
            </div>

            {/* Step 4 */}
            <div
              style={{
                background: "#FFFFFF",
                border: "1px solid #E2E8F0",
                borderRadius: 10,
                padding: "18px 20px",
                boxShadow: "0 1px 3px rgba(0, 0, 0, 0.04)",
              }}
            >
              <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 8 }}>
                <span
                  style={{
                    fontSize: 11,
                    fontWeight: 700,
                    fontFamily: "var(--font-mono, monospace)",
                    padding: "2px 7px",
                    borderRadius: 4,
                    background: "#EFF6FF",
                    border: "1px solid #BFDBFE",
                    color: "#2563EB",
                  }}
                >
                  STEP 04
                </span>
                <span style={{ fontSize: 14.5, fontWeight: 800, color: "#0F172A" }}>
                  Autonomous Governed Execution Flow
                </span>
              </div>
              <p style={{ fontSize: 13, color: "#334155", lineHeight: 1.6, margin: "0 0 10px 0" }}>
                The agent claims the task objective via SUTRA MCP tools, makes code modifications locally, and submits commits with cryptographic provenance:
              </p>
              <DocsCodeBlock
                code={`sutra_start_task         # Auto-allocates feature branch & locks session lease
sutra_declare_change     # Registers engineering work block & file impact scope
sutra_push_commit        # Pushes signed git commits bound to AgentSession SHA
sutra_open_pull_request  # Opens GitHub pull request and triggers automated CI`}
                language="bash"
                filename="MCP Tool Workflow Chain"
                style={{ margin: "10px 0 0 0" }}
              />
            </div>

            {/* Step 5 */}
            <div
              style={{
                background: "#FFFFFF",
                border: "1px solid #E2E8F0",
                borderRadius: 10,
                padding: "18px 20px",
                boxShadow: "0 1px 3px rgba(0, 0, 0, 0.04)",
              }}
            >
              <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 8 }}>
                <span
                  style={{
                    fontSize: 11,
                    fontWeight: 700,
                    fontFamily: "var(--font-mono, monospace)",
                    padding: "2px 7px",
                    borderRadius: 4,
                    background: "#FFF7ED",
                    border: "1px solid #FED7AA",
                    color: "#EA580C",
                  }}
                >
                  STEP 05
                </span>
                <span style={{ fontSize: 14.5, fontWeight: 800, color: "#0F172A" }}>
                  Human Review &amp; Governed Merge Execution
                </span>
              </div>
              <p style={{ fontSize: 13, color: "#334155", lineHeight: 1.6, margin: "0 0 10px 0" }}>
                When all automated CI checks pass, the agent transitions the PR to the human review queue. The human owner verifies diff evidence, resolves any open discussion threads, and authorizes the merge.
              </p>
              <div style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 12, color: "#EA580C" }}>
                <ShieldCheck size={14} />
                <span>Strict Invariant: Merge authority is exclusively reserved for human repository owners.</span>
              </div>
            </div>
          </div>
        </section>

        {/* Next Steps Deep-Links Grid */}
        <section>
          <DocsHeading id="next-steps" level={2}>
            Next Steps &amp; Detailed Guides
          </DocsHeading>
          <p style={{ color: "#475569", lineHeight: 1.7, marginBottom: 16 }}>
            Explore in-depth documentation modules to configure your coding environments, inspect the tool schema catalog, and review security policies.
          </p>

          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))",
              gap: 14,
            }}
          >
            {[
              {
                title: "MCP Integration Guide",
                desc: "Step-by-step setup for Cursor, Claude Code, Cline, and Antigravity IDE.",
                href: "#mcp-integration",
                color: "#2563EB",
              },
              {
                title: "AI Agent Protocol",
                desc: "Detailed operational workflows, lease heartbeats, and 21 MCP tool schemas.",
                href: "#ai-agent-guide",
                color: "#EA580C",
              },
              {
                title: "API Reference",
                desc: "REST endpoints, request/response payloads, and authentication headers.",
                href: "#api-reference",
                color: "#2563EB",
              },
              {
                title: "Security & Governance",
                desc: "Four-pillar review engine, cryptographic provenance, and human gate rules.",
                href: "#security-governance",
                color: "#EA580C",
              },
            ].map((item) => (
              <a
                key={item.title}
                href={item.href}
                style={{
                  textDecoration: "none",
                  background: "#FFFFFF",
                  border: "1px solid #E2E8F0",
                  borderRadius: 8,
                  padding: "16px 18px",
                  display: "flex",
                  flexDirection: "column",
                  justifyContent: "space-between",
                  boxShadow: "0 1px 3px rgba(0, 0, 0, 0.04)",
                  transition: "all 0.15s ease",
                }}
              >
                <div>
                  <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 6 }}>
                    <span style={{ fontSize: 14, fontWeight: 800, color: "#0F172A" }}>
                      {item.title}
                    </span>
                    <ArrowRight size={14} style={{ color: item.color }} />
                  </div>
                  <p style={{ fontSize: 12, color: "#475569", lineHeight: 1.5, margin: 0 }}>
                    {item.desc}
                  </p>
                </div>
              </a>
            ))}
          </div>
        </section>
      </div>
    ),
  },
];
