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
          <h2 style={{ fontSize: 20, fontWeight: 700, color: "#F5F5F5", marginBottom: 12 }}>
            The engineering execution system for humans and AI agents.
          </h2>
          <p style={{ color: "#A3A3A3", lineHeight: 1.7, marginBottom: 16 }}>
            SUTRA is an <strong style={{ color: "#F5F5F5" }}>Engineering Execution System</strong> designed to coordinate software development flows across human engineers, automated CI/CD environments, and agentic AI systems.
          </p>
          <p style={{ color: "#A3A3A3", lineHeight: 1.7, marginBottom: 20 }}>
            Code generation alone is insufficient for production software engineering. Engineering requires execution: testing, reviewing, verifying policy, and merging safely. SUTRA ensures every participant follows the exact same verification lifecycle.
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
            SUTRA strictly separates human account management from autonomous agent execution. Agents operate through bounded, short-lived sessions and cannot approve their own work.
          </p>

          <IdentityAccessFlowGraph />
        </section>

        {/* What SUTRA Controls Section */}
        <section>
          <h3 style={{ fontSize: 18, fontWeight: 700, color: "#F5F5F5", marginBottom: 16 }}>
            What SUTRA Controls
          </h3>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))", gap: 14 }}>
            <div style={{ padding: 18, border: "1px solid #242424", borderRadius: 10, background: "#151515" }}>
              <div style={{ display: "flex", alignItems: "center", gap: 8, color: "#3B82F6", fontWeight: 700, marginBottom: 6 }}>
                <ShieldCheck size={16} />
                Identity Scoping
              </div>
              <p style={{ fontSize: 12, color: "#A3A3A3", lineHeight: 1.6, margin: 0 }}>
                Differentiates Human vs Agent Actors securely with cryptographic tokens.
              </p>
            </div>
            <div style={{ padding: 18, border: "1px solid #242424", borderRadius: 10, background: "#151515" }}>
              <div style={{ display: "flex", alignItems: "center", gap: 8, color: "#F97316", fontWeight: 700, marginBottom: 6 }}>
                <Lock size={16} />
                Repository Authority
              </div>
              <p style={{ fontSize: 12, color: "#A3A3A3", lineHeight: 1.6, margin: 0 }}>
                Strict boundaries on clone, branch, and push per Actor capability.
              </p>
            </div>
            <div style={{ padding: 18, border: "1px solid #242424", borderRadius: 10, background: "#151515" }}>
              <div style={{ display: "flex", alignItems: "center", gap: 8, color: "#22C55E", fontWeight: 700, marginBottom: 6 }}>
                <Workflow size={16} />
                Changes & PRs
              </div>
              <p style={{ fontSize: 12, color: "#A3A3A3", lineHeight: 1.6, margin: 0 }}>
                Abstracts atomic Git commits into reviewable work blocks with evidence.
              </p>
            </div>
            <div style={{ padding: 18, border: "1px solid #242424", borderRadius: 10, background: "#151515" }}>
              <div style={{ display: "flex", alignItems: "center", gap: 8, color: "#F59E0B", fontWeight: 700, marginBottom: 6 }}>
                <Eye size={16} />
                Branch Protection
              </div>
              <p style={{ fontSize: 12, color: "#A3A3A3", lineHeight: 1.6, margin: 0 }}>
                Enforces rules on merging via automated CI checks and human sign-off.
              </p>
            </div>
          </div>
        </section>

        {/* Quickstart Sequence */}
        <section>
          <h3 style={{ fontSize: 18, fontWeight: 700, color: "#F5F5F5", marginBottom: 14 }}>
            Operating Your First Engineering Loop
          </h3>
          <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
            {[
              { step: "1. Authenticate", desc: "Create an account, verify email OTP, and sign in." },
              { step: "2. Repository Setup", desc: "Create or clone a repository. Your human identity grants Owner capabilities." },
              { step: "3. Agent Session", desc: "Register an AI agent and approve bounded repository permissions." },
              { step: "4. Git Execution", desc: "Push commits over HTTP and observe automated Change evidence creation." },
              { step: "5. Review & Merge", desc: "Satisfy branch protection policies and complete the merge." },
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
