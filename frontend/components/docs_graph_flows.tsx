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
      color: "#6366F1",
      payload: "{ \"session_token\": \"sat_99a1...\", \"expires_in\": 900, \"capabilities\": [\"repository.write\"] }",
      rule: "Possession of token is bound strictly to target repository."
    },
    {
      id: "git",
      label: "3. Git Engine",
      actor: "SUTRA Git Gateway",
      type: "Version Control",
      desc: "Accepts session-bound git-receive-pack over HTTP. Validates token per-request before disk writes.",
      icon: GitBranch,
      color: "#60A5FA",
      payload: "git push http://sat_99a1...@sutra.dev/repo.git feature/login-otp",
      rule: "Force-pushing (-f) is rejected by pre-receive hook."
    },
    {
      id: "change",
      label: "4. Change Evidence",
      actor: "Evidence Core",
      type: "Audit Chain",
      desc: "Hooks create an authoritative Change record tracking commit SHA, changed files, and AST diffs.",
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
      desc: "Runs automated test suites, linting, and vulnerability scans against the exact commit SHA.",
      icon: CheckCircle2,
      color: "#22C55E",
      payload: "{ \"ci_status\": \"passed\", \"tests_passed\": 19, \"coverage\": \"94.2%\" }",
      rule: "100% checks must pass for branch protection clearance."
    },
    {
      id: "review",
      label: "6. Human Sign-off",
      actor: "Human Reviewer",
      type: "Authoritative Review",
      desc: "Reviews diff evidence, resolves inline threads, and gives authoritative cryptographic approval.",
      icon: Eye,
      color: "#F59E0B",
      payload: "{ \"review_status\": \"approved\", \"reviewer\": \"human_owner\", \"threads_open\": 0 }",
      rule: "AI Agents CANNOT approve their own Pull Requests."
    },
    {
      id: "merge",
      label: "7. Protected Merge",
      actor: "Merge Engine",
      type: "Completion",
      desc: "Executes verified merge into target branch, records signed commit, and revokes short-lived session.",
      icon: CheckCheck,
      color: "#22C55E",
      payload: "{ \"merge_status\": \"merged\", \"target_commit\": \"c81a9f02\", \"session\": \"revoked\" }",
      rule: "Protected branches only accept verified merges."
    }
  ];

  // Auto-play animation cycle
  useEffect(() => {
    let timer: any;
    if (isPlaying) {
      timer = setInterval(() => {
        setActiveStep((prev) => (prev + 1) % steps.length);
      }, 2200);
    }
    return () => clearInterval(timer);
  }, [isPlaying, steps.length]);

  return (
    <div style={{ background: "#10151C", border: "1px solid #212836", borderRadius: 16, padding: "28px", margin: "24px 0", position: "relative" }}>
      {/* Top Header */}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 24, flexWrap: "wrap", gap: 12 }}>
        <div>
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <span style={{ width: 8, height: 8, borderRadius: "50%", background: "#3B82F6", boxShadow: "0 0 10px #3B82F6" }} />
            <span style={{ fontSize: 12, fontWeight: 700, letterSpacing: "0.1em", textTransform: "uppercase", color: "#60A5FA" }}>
              Interactive Animated Node Flow
            </span>
          </div>
          <div style={{ fontSize: 13, color: "#707A88", marginTop: 4 }}>
            Click nodes or trigger playback to trace live execution packets
          </div>
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <button
            onClick={() => setIsPlaying(!isPlaying)}
            className="btn"
            style={{
              height: 32,
              padding: "0 12px",
              fontSize: 12,
              fontWeight: 600,
              background: isPlaying ? "rgba(34, 197, 94, 0.15)" : "#171D26",
              borderColor: isPlaying ? "#22C55E" : "#212836",
              color: isPlaying ? "#22C55E" : "#F2F5F8",
            }}
          >
            {isPlaying ? (
              <>
                <Sparkles size={13} />
                <span>Simulating Execution Flow...</span>
              </>
            ) : (
              <>
                <Play size={13} />
                <span>Simulate Execution Flow</span>
              </>
            )}
          </button>
          <button
            onClick={() => { setIsPlaying(false); setActiveStep(0); }}
            className="btn"
            style={{ height: 32, padding: "0 10px", fontSize: 12 }}
            title="Reset to Step 1"
          >
            <RotateCcw size={13} />
          </button>
        </div>
      </div>

      {/* SVG Animated Connector Flow */}
      <div
        className="no-scrollbar"
        style={{
          position: "relative",
          marginBottom: 28,
          overflowX: "auto",
          paddingBottom: 6,
          scrollbarWidth: "none",
          msOverflowStyle: "none",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", minWidth: 680, width: "100%", justifyContent: "space-between", position: "relative" }}>
          {/* Animated Connecting Line */}
          <div
            style={{
              position: "absolute",
              top: 22,
              left: 30,
              right: 30,
              height: 2,
              background: "rgba(255, 255, 255, 0.08)",
              zIndex: 1,
            }}
          >
            <div
              style={{
                height: "100%",
                background: "linear-gradient(90deg, #3B82F6, #6366F1, #22C55E)",
                width: `${(activeStep / (steps.length - 1)) * 100}%`,
                transition: "width 0.4s cubic-bezier(0.16, 1, 0.3, 1)",
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
                }}
              >
                <div
                  className={isActive ? "node-pulse-active" : ""}
                  style={{
                    width: 44,
                    height: 44,
                    borderRadius: "50%",
                    background: isActive ? s.color : isPassed ? "#171D26" : "#10151C",
                    border: `2px solid ${isActive ? "#FFFFFF" : isPassed ? s.color : "#212836"}`,
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    color: isActive ? "#FFFFFF" : isPassed ? s.color : "#707A88",
                    transition: "all 0.25s ease",
                    marginBottom: 8,
                  }}
                >
                  <Icon size={18} />
                </div>
                <div
                  style={{
                    fontSize: 11,
                    fontWeight: 700,
                    color: isActive ? "#F2F5F8" : isPassed ? "#A8B1BD" : "#707A88",
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

      {/* Interactive Node State Inspector Card */}
      <div
        style={{
          background: "#171D26",
          border: "1px solid #212836",
          borderRadius: 12,
          padding: "22px 24px",
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))",
          gap: 20,
        }}
      >
        <div>
          <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 8 }}>
            <span
              style={{
                fontSize: 11,
                fontWeight: 700,
                background: `${steps[activeStep].color}18`,
                color: steps[activeStep].color,
                border: `1px solid ${steps[activeStep].color}35`,
                padding: "2px 8px",
                borderRadius: 999,
                textTransform: "uppercase",
              }}
            >
              {steps[activeStep].type}
            </span>
            <span style={{ fontSize: 12, color: "#707A88" }}>
              Actor: <strong style={{ color: "#F2F5F8" }}>{steps[activeStep].actor}</strong>
            </span>
          </div>

          <h4 style={{ fontSize: 16, fontWeight: 700, color: "#F2F5F8", marginBottom: 8 }}>
            {steps[activeStep].label}
          </h4>

          <p style={{ fontSize: 13, lineHeight: 1.6, color: "#A8B1BD", margin: "0 0 12px 0" }}>
            {steps[activeStep].desc}
          </p>

          <div style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 12, color: "#F59E0B" }}>
            <ShieldCheck size={14} />
            <strong>Rule:</strong> {steps[activeStep].rule}
          </div>
        </div>

        {/* Live Payload Stream Box */}
        <div>
          <div style={{ fontSize: 11, fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.08em", color: "#707A88", marginBottom: 8 }}>
            Runtime Telemetry & Payload
          </div>
          <div
            style={{
              background: "#090C10",
              border: "1px solid #212836",
              borderRadius: 8,
              padding: "14px 16px",
              fontFamily: "JetBrains Mono, monospace",
              fontSize: 12,
              color: "#60A5FA",
              overflowX: "auto",
              whiteSpace: "pre-wrap",
              lineHeight: 1.6,
            }}
          >
            {steps[activeStep].payload}
          </div>
        </div>
      </div>
    </div>
  );
}

/**
 * 2. Identity & Capability Guard Architecture
 */
export function IdentityAccessFlowGraph() {
  return (
    <div style={{ background: "#10151C", border: "1px solid #212836", borderRadius: 16, padding: "28px", margin: "24px 0" }}>
      <div style={{ fontSize: 12, fontWeight: 700, letterSpacing: "0.1em", textTransform: "uppercase", color: "#6366F1", marginBottom: 20 }}>
        Dual-Identity Security Boundary Architecture
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))", gap: 20 }}>
        {/* Human Actor */}
        <div style={{ background: "#171D26", border: "1px solid #212836", borderRadius: 12, padding: "20px" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 16 }}>
            <div style={{ width: 36, height: 36, borderRadius: 10, background: "rgba(59, 130, 246, 0.15)", display: "flex", alignItems: "center", justifyContent: "center", color: "#60A5FA" }}>
              <ShieldCheck size={20} />
            </div>
            <div>
              <div style={{ fontSize: 15, fontWeight: 700, color: "#F2F5F8" }}>Human Owner Actor</div>
              <div style={{ fontSize: 11, color: "#707A88" }}>Session JWT • Governance Authority</div>
            </div>
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: 8, fontSize: 13, color: "#A8B1BD" }}>
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <span style={{ color: "#22C55E", fontWeight: 700 }}>✓</span> Full repository administration
            </div>
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <span style={{ color: "#22C55E", fontWeight: 700 }}>✓</span> Agent registration & scope approval
            </div>
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <span style={{ color: "#22C55E", fontWeight: 700 }}>✓</span> Authoritative Pull Request approval & merge
            </div>
          </div>
        </div>

        {/* AI Agent Actor */}
        <div style={{ background: "#171D26", border: "1px solid #212836", borderRadius: 12, padding: "20px" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 16 }}>
            <div style={{ width: 36, height: 36, borderRadius: 10, background: "rgba(99, 102, 241, 0.15)", display: "flex", alignItems: "center", justifyContent: "center", color: "#818CF8" }}>
              <Cpu size={20} />
            </div>
            <div>
              <div style={{ fontSize: 15, fontWeight: 700, color: "#F2F5F8" }}>AI Agent Actor</div>
              <div style={{ fontSize: 11, color: "#707A88" }}>AgentSession • Capability Bounded</div>
            </div>
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: 8, fontSize: 13, color: "#A8B1BD" }}>
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <span style={{ color: "#22C55E", fontWeight: 700 }}>✓</span> Bounded Git clone & push to feature branch
            </div>
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <span style={{ color: "#EF4444", fontWeight: 700 }}>✕</span> Cannot self-approve changes or merge
            </div>
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <span style={{ color: "#EF4444", fontWeight: 700 }}>✕</span> Access immediately blocked upon token expiration
            </div>
          </div>
        </div>
      </div>

      {/* Gateway bar */}
      <div style={{ marginTop: 20, padding: "14px 18px", background: "rgba(59, 130, 246, 0.08)", border: "1px solid rgba(59, 130, 246, 0.25)", borderRadius: 10, display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: 12 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10, fontSize: 13, color: "#F2F5F8", fontWeight: 700 }}>
          <Lock size={16} style={{ color: "#3B82F6" }} />
          SUTRA HTTP Git & API Gateway
        </div>
        <div style={{ fontSize: 12, color: "#A8B1BD" }}>
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
    <div style={{ background: "#10151C", border: "1px solid #212836", borderRadius: 16, padding: "28px", margin: "24px 0" }}>
      <div style={{ fontSize: 12, fontWeight: 700, letterSpacing: "0.1em", textTransform: "uppercase", color: "#22C55E", marginBottom: 20 }}>
        Session-Bound Git Protocol Flow
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))", gap: 14 }}>
        {[
          { step: "1. Token Issue", cmd: "POST /v1/agents/sessions", note: "Yields scoped JWT session" },
          { step: "2. Git Clone", cmd: "git clone http://token@host/repo.git", note: "Authenticates basic auth" },
          { step: "3. Branch & Commit", cmd: "git checkout -b feature/xyz", note: "Real signed git commits" },
          { step: "4. Git Push Hook", cmd: "git push origin feature/xyz", note: "Hooks create Change evidence" },
        ].map((item) => (
          <div key={item.step} style={{ background: "#171D26", border: "1px solid #212836", borderRadius: 10, padding: "16px" }}>
            <div style={{ fontSize: 13, fontWeight: 700, color: "#F2F5F8", marginBottom: 8 }}>{item.step}</div>
            <div style={{ fontFamily: "JetBrains Mono, monospace", fontSize: 12, color: "#60A5FA", background: "#090C10", padding: "8px 10px", borderRadius: 6, marginBottom: 8, wordBreak: "break-all" }}>
              {item.cmd}
            </div>
            <div style={{ fontSize: 12, color: "#707A88" }}>{item.note}</div>
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
    <div style={{ background: "#10151C", border: "1px solid #212836", borderRadius: 16, padding: "28px", margin: "24px 0" }}>
      <div style={{ fontSize: 12, fontWeight: 700, letterSpacing: "0.1em", textTransform: "uppercase", color: "#F59E0B", marginBottom: 20 }}>
        Knowledge Graph AST & Impact Pipeline
      </div>

      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12, flexWrap: "wrap" }}>
        {[
          { title: "Source Files", desc: "AST Tree Parsing", icon: FolderGit2 },
          { title: "Symbol Nodes", desc: "Classes & Functions", icon: Layers },
          { title: "Graph Index", desc: "Dependency Edges", icon: Database },
          { title: "Impact Analysis", desc: "Blast-radius queries", icon: Workflow },
        ].map((node, i, arr) => {
          const Icon = node.icon;
          return (
            <React.Fragment key={node.title}>
              <div style={{ flex: 1, minWidth: 150, background: "#171D26", border: "1px solid #212836", borderRadius: 12, padding: "18px", textAlign: "center" }}>
                <div style={{ width: 36, height: 36, borderRadius: "50%", background: "rgba(245, 158, 11, 0.12)", border: "1px solid rgba(245, 158, 11, 0.3)", display: "flex", alignItems: "center", justifyContent: "center", color: "#F59E0B", margin: "0 auto 10px" }}>
                  <Icon size={18} />
                </div>
                <div style={{ fontSize: 14, fontWeight: 700, color: "#F2F5F8" }}>{node.title}</div>
                <div style={{ fontSize: 12, color: "#707A88", marginTop: 4 }}>{node.desc}</div>
              </div>
              {i < arr.length - 1 && (
                <div style={{ color: "#707A88", display: "flex", alignItems: "center" }}>
                  <ArrowRight size={16} />
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
    <div style={{ background: "#10151C", border: "1px solid #212836", borderRadius: 16, padding: "28px", margin: "24px 0" }}>
      <div style={{ fontSize: 12, fontWeight: 700, letterSpacing: "0.1em", textTransform: "uppercase", color: "#3B82F6", marginBottom: 20 }}>
        Automated CI & Branch Gatekeeper Pipeline
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: 14 }}>
        {[
          { title: "1. Push Hook", status: "Triggered", icon: GitBranch, color: "#60A5FA", desc: "Receives commit SHA" },
          { title: "2. Test Runner", status: "Automated", icon: CheckCircle2, color: "#22C55E", desc: "Runs unit & integration suites" },
          { title: "3. Lint & Audit", status: "Verified", icon: FileCode, color: "#3B82F6", desc: "Static analysis & vulnerability scan" },
          { title: "4. Policy Gate", status: "Enforced", icon: ShieldCheck, color: "#F59E0B", desc: "Requires 100% checks passing" },
        ].map((stage) => {
          const Icon = stage.icon;
          return (
            <div key={stage.title} style={{ background: "#171D26", border: "1px solid #212836", borderRadius: 10, padding: "18px" }}>
              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 12 }}>
                <div style={{ width: 32, height: 32, borderRadius: 8, background: `${stage.color}18`, display: "flex", alignItems: "center", justifyContent: "center", color: stage.color }}>
                  <Icon size={17} />
                </div>
                <span style={{ fontSize: 11, background: `${stage.color}15`, color: stage.color, border: `1px solid ${stage.color}30`, padding: "2px 8px", borderRadius: 999, fontWeight: 700 }}>
                  {stage.status}
                </span>
              </div>
              <div style={{ fontSize: 14, fontWeight: 700, color: "#F2F5F8" }}>{stage.title}</div>
              <div style={{ fontSize: 12, color: "#A8B1BD", marginTop: 4 }}>{stage.desc}</div>
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
    <div style={{ background: "#10151C", border: "1px solid #212836", borderRadius: 16, padding: "28px", margin: "24px 0" }}>
      <div style={{ fontSize: 12, fontWeight: 700, letterSpacing: "0.1em", textTransform: "uppercase", color: "#F59E0B", marginBottom: 20 }}>
        Authoritative Pull Request & Review State Machine
      </div>

      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 10, flexWrap: "wrap" }}>
        {[
          { state: "Open PR", desc: "Change proposed", color: "#60A5FA" },
          { state: "Active Threads", desc: "Inline comments open", color: "#F59E0B" },
          { state: "Threads Resolved", desc: "All discussions closed", color: "#3B82F6" },
          { state: "Human Approval", desc: "Sign-off recorded", color: "#22C55E" },
          { state: "Merged", desc: "Fast-forward into main", color: "#22C55E" },
        ].map((node, i, arr) => (
          <React.Fragment key={node.state}>
            <div style={{ flex: 1, minWidth: 140, background: "#171D26", border: "1px solid #212836", borderRadius: 10, padding: "14px 16px", textAlign: "center" }}>
              <div style={{ fontSize: 13, fontWeight: 700, color: node.color }}>{node.state}</div>
              <div style={{ fontSize: 11, color: "#707A88", marginTop: 4 }}>{node.desc}</div>
            </div>
            {i < arr.length - 1 && (
              <span style={{ color: "#707A88", fontSize: 14 }}>→</span>
            )}
          </React.Fragment>
        ))}
      </div>
    </div>
  );
}
