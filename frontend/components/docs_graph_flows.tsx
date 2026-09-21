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
 * 1. Interactive Animated Node-and-Edge Execution Canvas
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
      color: "#3B82F6",
      payload: "{ \"task_id\": \"task_8f91\", \"repo\": \"sutra-core\", \"scope\": [\"read\", \"write\"] }",
      rule: "Human identity holds root governance authority."
    },
    {
      id: "agent",
      label: "2. Agent Auth",
      actor: "AI Agent",
      type: "Token Broker",
      desc: "Authenticates via Agent Token and receives a short-lived 15-minute AgentSession JWT.",
      icon: Cpu,
      color: "#3B82F6",
      payload: "{ \"session_token\": \"sat_99a1...\", \"expires_in\": 900, \"capabilities\": [\"repository.write\"] }",
      rule: "Possession of token is bound strictly to target repository."
    },
    {
      id: "git",
      label: "3. Git Engine",
      actor: "Git Engine & Substrate",
      type: "Version Control",
      desc: "Accepts session-bound git push or coordinates branch updates with upstream Git substrate (e.g., GitHub). Validates token per-request.",
      icon: GitBranch,
      color: "#60A5FA",
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
      color: "#3B82F6",
      payload: "{ \"change_id\": \"chg_4e12\", \"additions\": 48, \"deletions\": 12, \"files\": 3 }",
      rule: "Evidence cannot be altered or bypassed."
    },
    {
      id: "ci",
      label: "5. Automated CI",
      actor: "CI Runner",
      type: "Verification Engine",
      desc: "Executes automated test suites, linting, and policy checks against the exact commit SHA.",
      icon: CheckCircle2,
      color: "#3B82F6",
      payload: "{ \"ci_status\": \"passed\", \"tests_passed\": 19, \"coverage\": \"94.2%\" }",
      rule: "100% required checks must pass for branch protection clearance."
    },
    {
      id: "review",
      label: "6. Human Sign-off",
      actor: "Human Reviewer",
      type: "Authoritative Review",
      desc: "Human reviews diff evidence, resolves inline threads, and provides authoritative approval.",
      icon: Eye,
      color: "#F97316",
      payload: "{ \"review_status\": \"approved\", \"reviewer\": \"human_owner\", \"threads_open\": 0 }",
      rule: "AI Agents CANNOT approve their own Pull Requests."
    },
    {
      id: "merge",
      label: "7. Protected Merge",
      actor: "Merge Controller",
      type: "Completion",
      desc: "Executes verified merge into target branch via substrate API/gateway after human approval, records commit SHA, and revokes session.",
      icon: CheckCheck,
      color: "#F97316",
      payload: "{ \"merge_status\": \"merged\", \"target_commit\": \"c81a9f02\", \"session\": \"revoked\" }",
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
        background: "#111418",
        border: "1px solid #202632",
        borderRadius: 10,
        padding: "16px 18px",
        margin: "18px 0",
        position: "relative",
      }}
      aria-label="SUTRA Execution Lifecycle Flow"
    >
      {/* Top Header */}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 14, flexWrap: "wrap", gap: 10 }}>
        <div>
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <span style={{ width: 6, height: 6, borderRadius: "50%", background: "#F97316" }} />
            <span style={{ fontSize: 11, fontWeight: 700, letterSpacing: "0.08em", textTransform: "uppercase", color: "#F97316" }}>
              Execution Lifecycle Flow
            </span>
          </div>
          <div style={{ fontSize: 12, color: "#8B949E", marginTop: 2 }}>
            Intent Task → Agent Auth → Git Engine → Change Evidence → Automated CI → Human Sign-off → Protected Merge
          </div>
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <button
            onClick={() => setIsPlaying(!isPlaying)}
            className="btn"
            style={{
              height: 28,
              padding: "0 10px",
              fontSize: 11,
              fontWeight: 600,
              background: isPlaying ? "rgba(249, 115, 22, 0.12)" : "#161B22",
              borderColor: isPlaying ? "#F97316" : "#2D333B",
              color: isPlaying ? "#F97316" : "#C9D1D9",
              display: "flex",
              alignItems: "center",
              gap: 6,
            }}
          >
            {isPlaying ? (
              <>
                <Sparkles size={11} />
                <span>Simulating...</span>
              </>
            ) : (
              <>
                <Play size={11} />
                <span>Simulate Flow</span>
              </>
            )}
          </button>
          <button
            onClick={() => { setIsPlaying(false); setActiveStep(0); }}
            className="btn"
            style={{ height: 28, padding: "0 8px", fontSize: 11, background: "#161B22", borderColor: "#2D333B", color: "#8B949E" }}
            title="Reset to Step 1"
            aria-label="Reset to Step 1"
          >
            <RotateCcw size={11} />
          </button>
        </div>
      </div>

      {/* Compact Interactive Node Stepper */}
      <div
        className="no-scrollbar"
        style={{
          position: "relative",
          marginBottom: 14,
          overflowX: "auto",
          paddingBottom: 4,
          scrollbarWidth: "none",
          msOverflowStyle: "none",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", minWidth: 620, width: "100%", justifyContent: "space-between", position: "relative" }}>
          {/* Track Line */}
          <div
            style={{
              position: "absolute",
              top: 18,
              left: 24,
              right: 24,
              height: 2,
              background: "#202632",
              zIndex: 1,
            }}
          >
            <div
              style={{
                height: "100%",
                background: "#3B82F6",
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
                  minWidth: 72,
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
                    background: isActive ? s.color : isPassed ? "#161B22" : "#0D1117",
                    border: `2px solid ${isActive ? "#FFFFFF" : isPassed ? s.color : "#30363D"}`,
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    color: isActive ? "#FFFFFF" : isPassed ? s.color : "#8B949E",
                    transition: "all 0.18s ease-out",
                    marginBottom: 6,
                  }}
                >
                  <Icon size={15} />
                </div>
                <div
                  style={{
                    fontSize: 10,
                    fontWeight: isActive ? 700 : 500,
                    color: isActive ? "#F0F6FC" : isPassed ? "#C9D1D9" : "#8B949E",
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
          background: "#0D1117",
          border: "1px solid #21262D",
          borderRadius: 8,
          padding: "14px 16px",
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(260px, 1fr))",
          gap: 16,
        }}
      >
        <div>
          <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 6 }}>
            <span
              style={{
                fontSize: 10,
                fontWeight: 700,
                background: `${steps[activeStep].color}20`,
                color: steps[activeStep].color,
                border: `1px solid ${steps[activeStep].color}40`,
                padding: "1px 6px",
                borderRadius: 4,
                textTransform: "uppercase",
              }}
            >
              {steps[activeStep].type}
            </span>
            <span style={{ fontSize: 11, color: "#8B949E" }}>
              Actor: <strong style={{ color: "#E6EDF3" }}>{steps[activeStep].actor}</strong>
            </span>
          </div>

          <h4 style={{ fontSize: 14, fontWeight: 700, color: "#F0F6FC", margin: "0 0 6px 0" }}>
            {steps[activeStep].label}
          </h4>

          <p style={{ fontSize: 12, lineHeight: 1.55, color: "#8B949E", margin: "0 0 8px 0" }}>
            {steps[activeStep].desc}
          </p>

          <div style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 11, color: "#F97316" }}>
            <ShieldCheck size={13} />
            <span><strong>Rule:</strong> {steps[activeStep].rule}</span>
          </div>
        </div>

        {/* Payload Box */}
        <div>
          <div style={{ fontSize: 10, fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.06em", color: "#8B949E", marginBottom: 6 }}>
            Runtime Telemetry & Payload
          </div>
          <div
            style={{
              background: "#161B22",
              border: "1px solid #30363D",
              borderRadius: 6,
              padding: "10px 12px",
              fontFamily: "var(--font-mono, monospace)",
              fontSize: 11,
              color: "#58A6FF",
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
          marginTop: 12,
          fontSize: 12,
          color: "#8B949E",
          borderTop: "1px solid #21262D",
          paddingTop: 10,
        }}
      >
        <summary style={{ cursor: "pointer", fontWeight: 600, color: "#58A6FF" }}>
          View all 7 lifecycle steps in static text format
        </summary>
        <ol style={{ margin: "8px 0 0 18px", padding: 0, display: "flex", flexDirection: "column", gap: 6 }}>
          {steps.map((s) => (
            <li key={s.id} style={{ fontSize: 12, color: "#C9D1D9" }}>
              <strong style={{ color: "#F0F6FC" }}>{s.label} ({s.actor})</strong>: {s.desc} <em>Rule: {s.rule}</em>
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
    <div style={{ background: "#111418", border: "1px solid #202632", borderRadius: 10, padding: "16px 18px", margin: "18px 0" }}>
      <div style={{ fontSize: 11, fontWeight: 700, letterSpacing: "0.08em", textTransform: "uppercase", color: "#F97316", marginBottom: 14 }}>
        Dual-Identity Security Boundary Architecture
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(260px, 1fr))", gap: 14 }}>
        {/* Human Actor */}
        <div style={{ background: "#161B22", border: "1px solid #2D333B", borderRadius: 8, padding: "14px 16px" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 12 }}>
            <div style={{ width: 32, height: 32, borderRadius: 8, background: "rgba(59, 130, 246, 0.15)", display: "flex", alignItems: "center", justifyContent: "center", color: "#3B82F6" }}>
              <ShieldCheck size={18} />
            </div>
            <div>
              <div style={{ fontSize: 14, fontWeight: 700, color: "#F0F6FC" }}>Human Owner Actor</div>
              <div style={{ fontSize: 11, color: "#8B949E" }}>Session JWT • Governance Authority</div>
            </div>
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: 6, fontSize: 12, color: "#C9D1D9" }}>
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <span style={{ color: "#3B82F6", fontWeight: 700 }}>✓</span> Full repository administration
            </div>
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <span style={{ color: "#3B82F6", fontWeight: 700 }}>✓</span> Agent registration & scope approval
            </div>
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <span style={{ color: "#3B82F6", fontWeight: 700 }}>✓</span> Authoritative Pull Request approval & merge
            </div>
          </div>
        </div>

        {/* AI Agent Actor */}
        <div style={{ background: "#161B22", border: "1px solid #2D333B", borderRadius: 8, padding: "14px 16px" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 12 }}>
            <div style={{ width: 32, height: 32, borderRadius: 8, background: "rgba(249, 115, 22, 0.15)", display: "flex", alignItems: "center", justifyContent: "center", color: "#F97316" }}>
              <Cpu size={18} />
            </div>
            <div>
              <div style={{ fontSize: 14, fontWeight: 700, color: "#F0F6FC" }}>AI Agent Actor</div>
              <div style={{ fontSize: 11, color: "#8B949E" }}>AgentSession • Capability Bounded</div>
            </div>
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: 6, fontSize: 12, color: "#C9D1D9" }}>
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <span style={{ color: "#3B82F6", fontWeight: 700 }}>✓</span> Bounded Git operations & push to feature branch
            </div>
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <span style={{ color: "#8B949E", fontWeight: 700 }}>✕</span> Cannot self-approve changes or merge
            </div>
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <span style={{ color: "#8B949E", fontWeight: 700 }}>✕</span> Access blocked upon token expiration
            </div>
          </div>
        </div>
      </div>

      {/* Gateway bar */}
      <div style={{ marginTop: 14, padding: "10px 14px", background: "rgba(249, 115, 22, 0.06)", border: "1px solid rgba(249, 115, 22, 0.2)", borderRadius: 8, display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: 10 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 12, color: "#F0F6FC", fontWeight: 600 }}>
          <Lock size={14} style={{ color: "#F97316" }} />
          SUTRA HTTP Git & API Gateway
        </div>
        <div style={{ fontSize: 11, color: "#8B949E" }}>
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
    <div style={{ background: "#111418", border: "1px solid #202632", borderRadius: 10, padding: "16px 18px", margin: "18px 0" }}>
      <div style={{ fontSize: 11, fontWeight: 700, letterSpacing: "0.08em", textTransform: "uppercase", color: "#F97316", marginBottom: 14 }}>
        Session-Bound Git Protocol Flow
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: 12 }}>
        {[
          { step: "1. Token Issue", cmd: "POST /v1/agents/sessions", note: "Yields scoped JWT session" },
          { step: "2. Git Clone", cmd: "git clone https://github.com/owner/repo.git", note: "Authenticates via Git substrate / PAT" },
          { step: "3. Branch & Commit", cmd: "git checkout -b feature/xyz", note: "Real signed git commits" },
          { step: "4. Git Push Hook", cmd: "git push origin feature/xyz", note: "Gateway records Change evidence" },
        ].map((item) => (
          <div key={item.step} style={{ background: "#161B22", border: "1px solid #2D333B", borderRadius: 8, padding: "12px 14px" }}>
            <div style={{ fontSize: 12, fontWeight: 700, color: "#F0F6FC", marginBottom: 6 }}>{item.step}</div>
            <div style={{ fontFamily: "var(--font-mono, monospace)", fontSize: 11, color: "#58A6FF", background: "#0D1117", padding: "6px 8px", borderRadius: 4, marginBottom: 6, wordBreak: "break-all" }}>
              {item.cmd}
            </div>
            <div style={{ fontSize: 11, color: "#8B949E" }}>{item.note}</div>
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
    <div style={{ background: "#111418", border: "1px solid #202632", borderRadius: 10, padding: "16px 18px", margin: "18px 0" }}>
      <div style={{ fontSize: 11, fontWeight: 700, letterSpacing: "0.08em", textTransform: "uppercase", color: "#F97316", marginBottom: 14 }}>
        Knowledge Graph AST & Impact Pipeline
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
              <div style={{ flex: 1, minWidth: 130, background: "#161B22", border: "1px solid #2D333B", borderRadius: 8, padding: "14px 12px", textAlign: "center" }}>
                <div style={{ width: 32, height: 32, borderRadius: "50%", background: "rgba(249, 115, 22, 0.12)", border: "1px solid rgba(249, 115, 22, 0.3)", display: "flex", alignItems: "center", justifyContent: "center", color: "#F97316", margin: "0 auto 8px" }}>
                  <Icon size={16} />
                </div>
                <div style={{ fontSize: 13, fontWeight: 700, color: "#F0F6FC" }}>{node.title}</div>
                <div style={{ fontSize: 11, color: "#8B949E", marginTop: 2 }}>{node.desc}</div>
              </div>
              {i < arr.length - 1 && (
                <div style={{ color: "#484F58", display: "flex", alignItems: "center" }}>
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
    <div style={{ background: "#111418", border: "1px solid #202632", borderRadius: 10, padding: "16px 18px", margin: "18px 0" }}>
      <div style={{ fontSize: 11, fontWeight: 700, letterSpacing: "0.08em", textTransform: "uppercase", color: "#F97316", marginBottom: 14 }}>
        Automated CI & Branch Gatekeeper Pipeline
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))", gap: 12 }}>
        {[
          { title: "1. Push Hook", status: "Triggered", icon: GitBranch, color: "#F97316", desc: "Receives commit SHA" },
          { title: "2. Test Runner", status: "Automated", icon: CheckCircle2, color: "#3B82F6", desc: "Runs unit & integration suites" },
          { title: "3. Lint & Audit", status: "Verified", icon: FileCode, color: "#3B82F6", desc: "Static analysis & vulnerability scan" },
          { title: "4. Policy Gate", status: "Enforced", icon: ShieldCheck, color: "#F97316", desc: "Requires 100% checks passing" },
        ].map((stage) => {
          const Icon = stage.icon;
          return (
            <div key={stage.title} style={{ background: "#161B22", border: "1px solid #2D333B", borderRadius: 8, padding: "14px" }}>
              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 10 }}>
                <div style={{ width: 28, height: 28, borderRadius: 6, background: `${stage.color}18`, display: "flex", alignItems: "center", justifyContent: "center", color: stage.color }}>
                  <Icon size={15} />
                </div>
                <span style={{ fontSize: 10, background: `${stage.color}15`, color: stage.color, border: `1px solid ${stage.color}30`, padding: "1px 6px", borderRadius: 4, fontWeight: 700 }}>
                  {stage.status}
                </span>
              </div>
              <div style={{ fontSize: 13, fontWeight: 700, color: "#F0F6FC" }}>{stage.title}</div>
              <div style={{ fontSize: 11, color: "#8B949E", marginTop: 2 }}>{stage.desc}</div>
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
    <div style={{ background: "#111418", border: "1px solid #202632", borderRadius: 10, padding: "16px 18px", margin: "18px 0" }}>
      <div style={{ fontSize: 11, fontWeight: 700, letterSpacing: "0.08em", textTransform: "uppercase", color: "#F97316", marginBottom: 14 }}>
        Authoritative Pull Request & Review State Machine
      </div>

      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 8, flexWrap: "wrap" }}>
        {[
          { state: "Open PR", desc: "Change proposed", color: "#3B82F6" },
          { state: "Active Threads", desc: "Inline comments open", color: "#F97316" },
          { state: "Threads Resolved", desc: "All discussions closed", color: "#3B82F6" },
          { state: "Human Approval", desc: "Sign-off recorded", color: "#F97316" },
          { state: "Merged", desc: "Fast-forward into main", color: "#3B82F6" },
        ].map((node, i, arr) => (
          <React.Fragment key={node.state}>
            <div style={{ flex: 1, minWidth: 120, background: "#161B22", border: "1px solid #2D333B", borderRadius: 8, padding: "10px 12px", textAlign: "center" }}>
              <div style={{ fontSize: 12, fontWeight: 700, color: node.color }}>{node.state}</div>
              <div style={{ fontSize: 10, color: "#8B949E", marginTop: 2 }}>{node.desc}</div>
            </div>
            {i < arr.length - 1 && (
              <span style={{ color: "#484F58", fontSize: 12 }}>→</span>
            )}
          </React.Fragment>
        ))}
      </div>
    </div>
  );
}

