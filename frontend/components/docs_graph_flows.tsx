'use client';

import React, { useState, useEffect } from 'react';
import {
  Terminal,
  Cpu,
  GitBranch,
  FileCode,
  CheckCircle2,
  Eye,
  CheckCheck,
  ShieldCheck,
  Lock,
  Workflow,
  ArrowRight,
  Server,
  Layers,
  Database,
  Key,
  FolderGit2,
  AlertCircle,
  Play,
  RotateCcw,
  Sparkles
} from 'lucide-react';

/**
 * 1. Interactive Animated Node-and-Edge Execution Canvas (Light Theme Native)
 */
export function ExecutionLifecycleGraph() {
  const [activeStep, setActiveStep] = useState(0);
  const [isPlaying, setIsPlaying] = useState(false);

  const steps = [
    {
      id: "task",
      label: "1. Intent Task",
      actor: "Human Owner",
      type: "Policy Origin",
      desc: "Assigns bounded engineering objective, selects target repository, and defines approval constraints.",
      icon: Terminal,
      color: "#2563EB",
      payload: '{ "task_id": "task_8f91", "repo": "sutra-core", "scope": ["read", "write"] }',
      rule: "Human identity holds root governance authority."
    },
    {
      id: "agent",
      label: "2. Agent Auth",
      actor: "AI Agent",
      type: "Token Broker",
      desc: "Authenticates via Agent Token and receives a short-lived 15-minute AgentSession JWT.",
      icon: Cpu,
      color: "#2563EB",
      payload: '{ "session_token": "sat_99a1...", "expires_in": 900, "capabilities": ["repository.write"] }',
      rule: "Possession of token is bound strictly to target repository."
    },
    {
      id: "git",
      label: "3. Git Engine",
      actor: "Git Engine & Substrate",
      type: "Version Control",
      desc: "Accepts session-bound git push or coordinates branch updates with upstream Git substrate (e.g., GitHub). Validates token per-request.",
      icon: GitBranch,
      color: "#0284C7",
      payload: "git push http://sat_99a1...@sutra.sudarshanai.com/repo.git feature/xyz",
      rule: "Direct force-pushes to protected branches are rejected by policy."
    },
    {
      id: "change",
      label: "4. Change Evidence",
      actor: "Evidence Core",
      type: "Audit Chain",
      desc: "System creates an authoritative Change record tracking commit SHA, changed files, and AST diffs.",
      icon: FileCode,
      color: "#2563EB",
      payload: '{ "change_id": "chg_4e12", "additions": 48, "deletions": 12, "files": 3 }',
      rule: "Evidence cannot be altered or bypassed."
    },
    {
      id: "ci",
      label: "5. Automated CI",
      actor: "CI Runner",
      type: "Verification Engine",
      desc: "Executes automated test suites, linting, and policy checks against the exact commit SHA.",
      icon: CheckCircle2,
      color: "#2563EB",
      payload: '{ "ci_status": "passed", "tests_passed": 19, "coverage": "94.2%" }',
      rule: "100% required checks must pass for branch protection clearance."
    },
    {
      id: "review",
      label: "6. Human Sign-off",
      actor: "Human Reviewer",
      type: "Authoritative Review",
      desc: "Human reviews diff evidence, resolves inline threads, and provides authoritative approval.",
      icon: Eye,
      color: "#EA580C",
      payload: '{ "review_status": "approved", "reviewer": "human_owner", "threads_open": 0 }',
      rule: "AI Agents CANNOT approve their own Pull Requests."
    },
    {
      id: "merge",
      label: "7. Protected Merge",
      actor: "Merge Controller",
      type: "Completion",
      desc: "Executes verified merge into target branch via substrate API/gateway after human approval, records commit SHA, and revokes session.",
      icon: CheckCheck,
      color: "#EA580C",
      payload: '{ "merge_status": "merged", "target_commit": "c81a9f02", "session": "revoked" }',
      rule: "Protected branches only accept verified, human-approved merges."
    }
  ];

  // Auto-play animation cycle
  useEffect(() => {
    let timer: any;
    if (isPlaying) {
      timer = setInterval(() => {
        setActiveStep((prev) => (prev + 1) % steps.length);
      }, 2400);
    }
    return () => clearInterval(timer);
  }, [isPlaying, steps.length]);

  return (
    <div
      style={{
        background: "#FFFFFF",
        border: "1px solid #E2E8F0",
        borderRadius: 10,
        padding: "18px 20px",
        margin: "20px 0",
        position: "relative",
        boxShadow: "0 1px 3px rgba(0, 0, 0, 0.04)",
      }}
      aria-label="SUTRA Execution Lifecycle Flow"
    >
      {/* Top Header */}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 16, flexWrap: "wrap", gap: 10 }}>
        <div>
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <span style={{ width: 7, height: 7, borderRadius: "50%", background: "#EA580C" }} />
            <span style={{ fontSize: 11.5, fontWeight: 800, letterSpacing: "0.08em", textTransform: "uppercase", color: "#EA580C" }}>
              Execution Lifecycle Flow
            </span>
          </div>
          <div style={{ fontSize: 12.5, color: "#475569", marginTop: 3 }}>
            Intent Task → Agent Auth → Git Engine → Change Evidence → Automated CI → Human Sign-off → Protected Merge
          </div>
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <button
            onClick={() => setIsPlaying(!isPlaying)}
            style={{
              height: 30,
              padding: "0 12px",
              fontSize: 11.5,
              fontWeight: 700,
              background: isPlaying ? "rgba(234, 88, 12, 0.1)" : "#FFFFFF",
              border: `1px solid ${isPlaying ? "#EA580C" : "#CBD5E1"}`,
              color: isPlaying ? "#EA580C" : "#0F172A",
              borderRadius: 6,
              cursor: "pointer",
              display: "flex",
              alignItems: "center",
              gap: 6,
              boxShadow: "0 1px 2px rgba(0,0,0,0.05)",
              transition: "all 150ms ease",
            }}
          >
            {isPlaying ? (
              <>
                <Sparkles size={12} />
                <span>Simulating...</span>
              </>
            ) : (
              <>
                <Play size={12} />
                <span>Simulate Flow</span>
              </>
            )}
          </button>
          <button
            onClick={() => { setIsPlaying(false); setActiveStep(0); }}
            style={{
              height: 30,
              padding: "0 10px",
              fontSize: 11.5,
              background: "#FFFFFF",
              border: "1px solid #CBD5E1",
              color: "#64748B",
              borderRadius: 6,
              cursor: "pointer",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              boxShadow: "0 1px 2px rgba(0,0,0,0.05)",
            }}
            title="Reset to Step 1"
            aria-label="Reset to Step 1"
          >
            <RotateCcw size={12} />
          </button>
        </div>
      </div>

      {/* Compact Interactive Node Stepper */}
      <div
        className="no-scrollbar"
        style={{
          position: "relative",
          marginBottom: 18,
          overflowX: "auto",
          paddingBottom: 6,
          scrollbarWidth: "none",
          msOverflowStyle: "none",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", minWidth: 640, width: "100%", justifyContent: "space-between", position: "relative" }}>
          {/* Track Line */}
          <div
            style={{
              position: "absolute",
              top: 18,
              left: 28,
              right: 28,
              height: 3,
              background: "#E2E8F0",
              zIndex: 1,
            }}
          >
            <div
              style={{
                height: "100%",
                background: "#2563EB",
                width: `${(activeStep / (steps.length - 1)) * 100}%`,
                transition: "width 0.25s ease-out",
              }}
            />
          </div>

          {/* Nodes */}
          {steps.map((s, idx) => {
            const isActive = activeStep === idx;
            const isPassed = activeStep > idx;
            const Icon = s.icon;
            return (
              <button
                key={s.id}
                onClick={() => { setIsPlaying(false); setActiveStep(idx); }}
                style={{
                  position: "relative",
                  zIndex: 2,
                  display: "flex",
                  flexDirection: "column",
                  alignItems: "center",
                  background: "none",
                  border: "none",
                  cursor: "pointer",
                  flex: 1,
                  minWidth: 80,
                  padding: 0,
                }}
                aria-current={isActive ? "step" : undefined}
                aria-label={s.label}
              >
                <div
                  style={{
                    width: 36,
                    height: 36,
                    borderRadius: "50%",
                    background: isActive ? s.color : isPassed ? "#EFF6FF" : "#FFFFFF",
                    border: `2px solid ${isActive ? s.color : isPassed ? s.color : "#CBD5E1"}`,
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    color: isActive ? "#FFFFFF" : isPassed ? s.color : "#64748B",
                    transition: "all 0.18s ease-out",
                    marginBottom: 6,
                    boxShadow: isActive ? "0 2px 8px rgba(37, 99, 235, 0.35)" : "0 1px 2px rgba(0,0,0,0.05)",
                  }}
                >
                  <Icon size={15} />
                </div>
                <div
                  style={{
                    fontSize: 11,
                    fontWeight: isActive ? 800 : isPassed ? 600 : 500,
                    color: isActive ? "#0F172A" : isPassed ? "#334155" : "#64748B",
                    textAlign: "center",
                    whiteSpace: "nowrap",
                  }}
                >
                  {s.label}
                </div>
              </button>
            );
          })}
        </div>
      </div>

      {/* Active Step Details Card */}
      <div
        style={{
          background: "#F8FAFC",
          border: "1px solid #E2E8F0",
          borderRadius: 8,
          padding: "16px 18px",
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(260px, 1fr))",
          gap: 16,
        }}
      >
        <div>
          <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 8 }}>
            <span
              style={{
                fontSize: 10.5,
                fontWeight: 700,
                background: `${steps[activeStep].color}18`,
                color: steps[activeStep].color,
                border: `1px solid ${steps[activeStep].color}35`,
                padding: "2px 7px",
                borderRadius: 4,
                textTransform: "uppercase",
              }}
            >
              {steps[activeStep].type}
            </span>
            <span style={{ fontSize: 11.5, color: "#64748B" }}>
              Actor: <strong style={{ color: "#0F172A" }}>{steps[activeStep].actor}</strong>
            </span>
          </div>

          <h4 style={{ fontSize: 15, fontWeight: 800, color: "#0F172A", margin: "0 0 6px 0" }}>
            {steps[activeStep].label}
          </h4>

          <p style={{ fontSize: 13, lineHeight: 1.6, color: "#334155", margin: "0 0 10px 0" }}>
            {steps[activeStep].desc}
          </p>

          <div style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 12, color: "#EA580C" }}>
            <ShieldCheck size={14} style={{ flexShrink: 0 }} />
            <span><strong>Rule:</strong> {steps[activeStep].rule}</span>
          </div>
        </div>

        {/* Payload Box (Developer Dark Code Snippet) */}
        <div>
          <div style={{ fontSize: 10.5, fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.06em", color: "#64748B", marginBottom: 6 }}>
            Runtime Telemetry &amp; Payload
          </div>
          <div
            style={{
              background: "#09090B",
              border: "1px solid #27272A",
              borderRadius: 6,
              padding: "10px 14px",
              fontFamily: "var(--font-mono, monospace)",
              fontSize: 11.5,
              color: "#38BDF8",
              overflowX: "auto",
              whiteSpace: "pre-wrap",
              lineHeight: 1.5,
            }}
          >
            {steps[activeStep].payload}
          </div>
        </div>
      </div>

      {/* Static Fallback for Search Engines, Bots & Reduced-Motion Users */}
      <details
        style={{
          marginTop: 14,
          paddingTop: 10,
          borderTop: "1px solid #E2E8F0",
          fontSize: 12.5,
          color: "#475569",
        }}
      >
        <summary style={{ cursor: "pointer", fontWeight: 600, color: "#EA580C" }}>
          View all 7 lifecycle steps in static text format
        </summary>
        <ol style={{ margin: "10px 0 0 20px", padding: 0, display: "flex", flexDirection: "column", gap: 6 }}>
          {steps.map((s) => (
            <li key={s.id} style={{ fontSize: 12.5, color: "#334155" }}>
              <strong style={{ color: "#0F172A" }}>{s.label} ({s.actor})</strong>: {s.desc} <em>Rule: {s.rule}</em>
            </li>
          ))}
        </ol>
      </details>
    </div>
  );
}

/**
 * 2. Identity & Capability Guard Architecture
 */
export function IdentityAccessFlowGraph() {
  return (
    <div style={{ background: "#FFFFFF", border: "1px solid #E2E8F0", borderRadius: 10, padding: "18px 20px", margin: "20px 0", boxShadow: "0 1px 3px rgba(0,0,0,0.04)" }}>
      <div style={{ fontSize: 11.5, fontWeight: 800, letterSpacing: "0.08em", textTransform: "uppercase", color: "#EA580C", marginBottom: 14 }}>
        Dual-Identity Security Boundary Architecture
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(260px, 1fr))", gap: 14 }}>
        {/* Human Actor */}
        <div style={{ background: "#F8FAFC", border: "1px solid #E2E8F0", borderRadius: 8, padding: "16px 18px" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 12 }}>
            <div style={{ width: 34, height: 34, borderRadius: 8, background: "#EFF6FF", border: "1px solid #BFDBFE", display: "flex", alignItems: "center", justifyContent: "center", color: "#2563EB" }}>
              <ShieldCheck size={18} />
            </div>
            <div>
              <div style={{ fontSize: 14, fontWeight: 800, color: "#0F172A" }}>Human Owner Actor</div>
              <div style={{ fontSize: 11.5, color: "#64748B" }}>Session JWT • Governance Authority</div>
            </div>
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: 6, fontSize: 12.5, color: "#334155" }}>
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <span style={{ color: "#2563EB", fontWeight: 700 }}>✓</span> Full repository administration
            </div>
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <span style={{ color: "#2563EB", fontWeight: 700 }}>✓</span> Agent registration &amp; scope approval
            </div>
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <span style={{ color: "#2563EB", fontWeight: 700 }}>✓</span> Authoritative Pull Request approval &amp; merge
            </div>
          </div>
        </div>

        {/* AI Agent Actor */}
        <div style={{ background: "#F8FAFC", border: "1px solid #E2E8F0", borderRadius: 8, padding: "16px 18px" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 12 }}>
            <div style={{ width: 34, height: 34, borderRadius: 8, background: "#FFF7ED", border: "1px solid #FED7AA", display: "flex", alignItems: "center", justifyContent: "center", color: "#EA580C" }}>
              <Cpu size={18} />
            </div>
            <div>
              <div style={{ fontSize: 14, fontWeight: 800, color: "#0F172A" }}>AI Agent Actor</div>
              <div style={{ fontSize: 11.5, color: "#64748B" }}>AgentSession • Capability Bounded</div>
            </div>
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: 6, fontSize: 12.5, color: "#334155" }}>
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <span style={{ color: "#2563EB", fontWeight: 700 }}>✓</span> Bounded Git operations &amp; push to feature branch
            </div>
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <span style={{ color: "#DC2626", fontWeight: 700 }}>✕</span> Cannot self-approve changes or merge
            </div>
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <span style={{ color: "#DC2626", fontWeight: 700 }}>✕</span> Access blocked upon token expiration
            </div>
          </div>
        </div>
      </div>

      {/* Gateway bar */}
      <div style={{ marginTop: 14, padding: "12px 16px", background: "#FFF7ED", border: "1px solid #FED7AA", borderRadius: 8, display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: 10 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 12.5, color: "#9A3412", fontWeight: 700 }}>
          <Lock size={14} style={{ color: "#EA580C" }} />
          SUTRA HTTP Git &amp; API Gateway
        </div>
        <div style={{ fontSize: 11.5, color: "#9A3412" }}>
          Validates capability tokens per HTTP request before disk or git-receive-pack execution
        </div>
      </div>
    </div>
  );
}

/**
 * 3. Session-Bound Git HTTP Workflow Graph
 */
export function GitWorkflowGraph() {
  return (
    <div style={{ background: "#FFFFFF", border: "1px solid #E2E8F0", borderRadius: 10, padding: "18px 20px", margin: "20px 0", boxShadow: "0 1px 3px rgba(0,0,0,0.04)" }}>
      <div style={{ fontSize: 11.5, fontWeight: 800, letterSpacing: "0.08em", textTransform: "uppercase", color: "#EA580C", marginBottom: 14 }}>
        Session-Bound Git Protocol Flow
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: 12 }}>
        {[
          { step: "1. Token Issue", cmd: "POST /v1/agents/sessions", note: "Yields scoped JWT session" },
          { step: "2. Git Clone", cmd: "git clone https://github.com/owner/repo.git", note: "Authenticates via Git substrate / PAT" },
          { step: "3. Branch & Commit", cmd: "git checkout -b feature/xyz", note: "Real signed git commits" },
          { step: "4. Git Push Hook", cmd: "git push origin feature/xyz", note: "Gateway records Change evidence" },
        ].map((item) => (
          <div key={item.step} style={{ background: "#F8FAFC", border: "1px solid #E2E8F0", borderRadius: 8, padding: "14px 16px" }}>
            <div style={{ fontSize: 13, fontWeight: 700, color: "#0F172A", marginBottom: 6 }}>{item.step}</div>
            <div style={{ fontFamily: "var(--font-mono, monospace)", fontSize: 11.5, color: "#0284C7", background: "#FFFFFF", border: "1px solid #E2E8F0", padding: "6px 8px", borderRadius: 4, marginBottom: 6, wordBreak: "break-all" }}>
              {item.cmd}
            </div>
            <div style={{ fontSize: 11.5, color: "#475569" }}>{item.note}</div>
          </div>
        ))}
      </div>
    </div>
  );
}

/**
 * 4. Knowledge Graph Semantic Architecture
 */
export function KnowledgeGraphFlow() {
  return (
    <div style={{ background: "#FFFFFF", border: "1px solid #E2E8F0", borderRadius: 10, padding: "18px 20px", margin: "20px 0", boxShadow: "0 1px 3px rgba(0,0,0,0.04)" }}>
      <div style={{ fontSize: 11.5, fontWeight: 800, letterSpacing: "0.08em", textTransform: "uppercase", color: "#EA580C", marginBottom: 14 }}>
        Knowledge Graph AST &amp; Impact Pipeline
      </div>

      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 10, flexWrap: "wrap" }}>
        {[
          { title: "Source Files", desc: "AST Tree Parsing", icon: FolderGit2 },
          { title: "Symbol Nodes", desc: "Classes & Functions", icon: Layers },
          { title: "Graph Index", desc: "Dependency Edges", icon: Database },
          { title: "Impact Analysis", desc: "Blast-radius queries", icon: Workflow },
        ].map((node, i, arr) => {
          const Icon = node.icon;
          return (
            <React.Fragment key={node.title}>
              <div style={{ flex: 1, minWidth: 130, background: "#F8FAFC", border: "1px solid #E2E8F0", borderRadius: 8, padding: "14px 12px", textAlign: "center" }}>
                <div style={{ width: 34, height: 34, borderRadius: "50%", background: "#FFF7ED", border: "1px solid #FED7AA", display: "flex", alignItems: "center", justifyContent: "center", color: "#EA580C", margin: "0 auto 8px" }}>
                  <Icon size={16} />
                </div>
                <div style={{ fontSize: 13, fontWeight: 700, color: "#0F172A" }}>{node.title}</div>
                <div style={{ fontSize: 11.5, color: "#475569", marginTop: 2 }}>{node.desc}</div>
              </div>
              {i < arr.length - 1 && (
                <div style={{ color: "#94A3B8", display: "flex", alignItems: "center" }}>
                  <ArrowRight size={14} />
                </div>
              )}
            </React.Fragment>
          );
        })}
      </div>
    </div>
  );
}

/**
 * 5. CI Pipeline & Branch Gatekeeper Architecture
 */
export function CIPipelineGraph() {
  return (
    <div style={{ background: "#FFFFFF", border: "1px solid #E2E8F0", borderRadius: 10, padding: "18px 20px", margin: "20px 0", boxShadow: "0 1px 3px rgba(0,0,0,0.04)" }}>
      <div style={{ fontSize: 11.5, fontWeight: 800, letterSpacing: "0.08em", textTransform: "uppercase", color: "#EA580C", marginBottom: 14 }}>
        Automated CI &amp; Branch Gatekeeper Pipeline
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))", gap: 12 }}>
        {[
          { title: "1. Push Hook", status: "Triggered", icon: GitBranch, color: "#EA580C", desc: "Receives commit SHA" },
          { title: "2. Test Runner", status: "Automated", icon: CheckCircle2, color: "#2563EB", desc: "Runs unit & integration suites" },
          { title: "3. Lint & Audit", status: "Verified", icon: FileCode, color: "#2563EB", desc: "Static analysis & vulnerability scan" },
          { title: "4. Policy Gate", status: "Enforced", icon: ShieldCheck, color: "#EA580C", desc: "Requires 100% checks passing" },
        ].map((stage) => {
          const Icon = stage.icon;
          return (
            <div key={stage.title} style={{ background: "#F8FAFC", border: "1px solid #E2E8F0", borderRadius: 8, padding: "14px 16px" }}>
              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 10 }}>
                <div style={{ width: 30, height: 30, borderRadius: 6, background: `${stage.color}18`, display: "flex", alignItems: "center", justifyContent: "center", color: stage.color }}>
                  <Icon size={15} />
                </div>
                <span style={{ fontSize: 10, background: `${stage.color}12`, color: stage.color, border: `1px solid ${stage.color}35`, padding: "2px 7px", borderRadius: 4, fontWeight: 700 }}>
                  {stage.status}
                </span>
              </div>
              <div style={{ fontSize: 13, fontWeight: 700, color: "#0F172A" }}>{stage.title}</div>
              <div style={{ fontSize: 11.5, color: "#475569", marginTop: 2 }}>{stage.desc}</div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

/**
 * 6. Pull Request Review State Machine
 */
export function PRReviewStateGraph() {
  return (
    <div style={{ background: "#FFFFFF", border: "1px solid #E2E8F0", borderRadius: 10, padding: "18px 20px", margin: "20px 0", boxShadow: "0 1px 3px rgba(0,0,0,0.04)" }}>
      <div style={{ fontSize: 11.5, fontWeight: 800, letterSpacing: "0.08em", textTransform: "uppercase", color: "#EA580C", marginBottom: 14 }}>
        Authoritative Pull Request &amp; Review State Machine
      </div>

      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 8, flexWrap: "wrap" }}>
        {[
          { state: "Open PR", desc: "Change proposed", color: "#2563EB" },
          { state: "Active Threads", desc: "Inline comments open", color: "#EA580C" },
          { state: "Threads Resolved", desc: "All discussions closed", color: "#2563EB" },
          { state: "Human Approval", desc: "Sign-off recorded", color: "#EA580C" },
          { state: "Merged", desc: "Fast-forward into main", color: "#2563EB" },
        ].map((node, i, arr) => (
          <React.Fragment key={node.state}>
            <div style={{ flex: 1, minWidth: 120, background: "#F8FAFC", border: "1px solid #E2E8F0", borderRadius: 8, padding: "12px 14px", textAlign: "center" }}>
              <div style={{ fontSize: 12.5, fontWeight: 800, color: node.color }}>{node.state}</div>
              <div style={{ fontSize: 11, color: "#475569", marginTop: 3 }}>{node.desc}</div>
            </div>
            {i < arr.length - 1 && (
              <span style={{ color: "#94A3B8", fontSize: 14 }}>→</span>
            )}
          </React.Fragment>
        ))}
      </div>
    </div>
  );
}
