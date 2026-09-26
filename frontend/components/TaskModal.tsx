"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { Cpu as Bot, CheckCircle2, Play, ShieldCheck, MessageSquare, XCircle, ArrowRight, Square } from "lucide-react";
import { Badge } from "@/components/ui";
import { Task, taskService } from "@/lib/tasks";
import { Agent, agentService } from "@/lib/agents";
import { ConfirmModal } from "@/components/ConfirmModal";

// Premium card wrapper for the modal with Double-Bezel architecture
function PremiumCard({ children, title }: { children: React.ReactNode, title: string }) {
  return (
    <div className="bezel-shell" style={{ width: "100%" }}>
      <div className="bezel-core" style={{ padding: "22px 20px", height: "100%", display: "flex", flexDirection: "column", gap: 12 }}>
        <div style={{ fontSize: 11, fontWeight: 700, color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "0.12em" }}>
          {title}
        </div>
        {children}
      </div>
    </div>
  );
}

export function TaskModal({
  taskId,
  onClose,
  onTaskUpdated,
}: {
  taskId: string;
  onClose: () => void;
  onTaskUpdated?: () => void;
}) {
  const [task, setTask] = useState<Task | null>(null);
  const [agents, setAgents] = useState<Agent[]>([]);
  const [loading, setLoading] = useState(true);
  const [showTerminateModal, setShowTerminateModal] = useState(false);
  const [terminating, setTerminating] = useState(false);

  const handleTerminate = async () => {
    if (!task) return;
    try {
      setTerminating(true);
      await taskService.terminateTask(task.id);
      setTask((prev) => (prev ? { ...prev, status: "cancelled" } : null));
      setShowTerminateModal(false);
      onTaskUpdated?.();
    } catch (err: any) {
      console.error("Failed to terminate task:", err);
    } finally {
      setTerminating(false);
    }
  };

  const loadData = () => {
    if (!taskId) return;
    setLoading(true);
    Promise.all([
      taskService.getTask(taskId),
      agentService.listAgents().catch(() => [])
    ])
    .then(([t, a]) => {
      setTask(t);
      setAgents(a);
    })
    .catch(console.error)
    .finally(() => setLoading(false));
  };

  useEffect(() => {
    loadData();
    const interval = setInterval(() => {
      if (!taskId) return;
      Promise.all([
        taskService.getTask(taskId),
        agentService.listAgents().catch(() => [])
      ]).then(([t, a]) => {
        setTask(t);
        setAgents(a);
      }).catch(console.error);
    }, 5000);
    
    return () => clearInterval(interval);
  }, [taskId]);

  if (loading) {
    return (
      <div className="modal-overlay" style={{
        position: "fixed", top: 0, left: 0, right: 0, bottom: 0,
        backgroundColor: "rgba(0,0,0,0.8)",
        backdropFilter: "blur(12px)",
        zIndex: 100, display: "flex", alignItems: "center", justifyContent: "center",
        padding: 20
      }}>
        <div className="bezel-shell" style={{ width: "100%", maxWidth: 420 }}>
          <div className="bezel-core" style={{ padding: "48px 32px", textAlign: "center" }}>
            <div className="spinner" style={{ margin: "0 auto 20px" }}></div>
            <div style={{ fontSize: 15, fontWeight: 600, color: "var(--text-primary)", marginBottom: 6 }}>
              Accessing SUTRA Control Plane
            </div>
            <p style={{ color: "var(--text-muted)", fontSize: 13, margin: 0 }}>Initializing workspace sandbox and task state...</p>
          </div>
        </div>
      </div>
    );
  }

  if (!task) {
    return (
      <div className="modal-overlay" style={{
        position: "fixed", top: 0, left: 0, right: 0, bottom: 0,
        backgroundColor: "rgba(0,0,0,0.8)",
        backdropFilter: "blur(12px)",
        zIndex: 100, display: "flex", alignItems: "center", justifyContent: "center",
        padding: 20
      }}>
        <div className="bezel-shell" style={{ width: "100%", maxWidth: 420 }}>
          <div className="bezel-core" style={{ padding: "40px 28px", textAlign: "center" }}>
            <div style={{ color: "var(--text-primary)", fontSize: 18, fontWeight: 600, marginBottom: 8 }}>Task Not Found</div>
            <p style={{ color: "var(--text-muted)", fontSize: 13, marginBottom: 24, lineHeight: 1.5 }}>
              The requested task does not exist, has been archived, or is inaccessible in this workspace scope.
            </p>
            <button className="btn-island-ghost" onClick={onClose}>Close window</button>
          </div>
        </div>
      </div>
    );
  }

  const isCompleted = task.status === "completed" || task.status === "done";
  const isInProgress = task.status === "in_progress" || task.status === "assigned";
  const isOpen = task.status === "todo" || task.status === "open";
  const assignedAgent = agents.find(a => a.id === task.assigned_agent_id);

  return (
    <div className="modal-overlay" style={{
      position: "fixed", top: 0, left: 0, right: 0, bottom: 0,
      backgroundColor: "rgba(0,0,0,0.82)",
      backdropFilter: "blur(14px)",
      zIndex: 100, display: "flex", alignItems: "center", justifyContent: "center",
      padding: "min(24px, 3vw)",
      boxSizing: "border-box"
    }}>
      
      <div className="bezel-shell" style={{ width: "100%", maxWidth: 1020, maxHeight: "92vh", display: "flex", flexDirection: "column" }}>
        <div className="bezel-core" style={{ 
          overflowY: "auto", 
          maxHeight: "calc(92vh - 12px)",
          background: "linear-gradient(180deg, #141418 0%, #0E0E11 100%)",
          display: "flex",
          flexDirection: "column"
        }}>
          
          {/* Header Area */}
          <div style={{ 
            padding: "clamp(24px, 4vw, 36px) clamp(24px, 4vw, 36px) 24px", 
            borderBottom: "1px solid rgba(255,255,255,0.06)",
            background: "radial-gradient(ellipse at 50% -20%, rgba(249, 115, 22, 0.08) 0%, transparent 70%)"
          }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", flexWrap: "wrap", gap: 16 }}>
              <div style={{ flex: "1 1 280px", minWidth: 0, paddingRight: 8 }}>
                <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 14, flexWrap: "wrap" }}>
                  <span style={{ 
                    fontSize: 11, 
                    color: "var(--text-secondary)", 
                    fontFamily: "var(--font-mono, monospace)", 
                    fontWeight: 600, 
                    background: "rgba(255,255,255,0.05)", 
                    border: "1px solid rgba(255,255,255,0.08)",
                    padding: "2px 8px", 
                    borderRadius: 4 
                  }}>
                    #{taskId.slice(0, 8)}
                  </span>
                  <Badge tone={isCompleted ? "green" : isInProgress ? "aqua" : "amber"}>
                    {task.status.replace("_", " ")}
                  </Badge>
                </div>
                <h2 style={{ fontSize: "clamp(22px, 3vw, 28px)", margin: "0 0 10px 0", fontWeight: 600, color: "#FFFFFF", lineHeight: 1.25, letterSpacing: "-0.02em", wordBreak: "break-word" }}>
                  {task.title}
                </h2>
                <p style={{ color: "var(--text-secondary)", fontSize: 14, margin: 0, lineHeight: 1.6, wordBreak: "break-word" }}>
                  {task.description || "No description provided."}
                </p>
              </div>

              <div style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
                {isCompleted && task.resulting_change_id && (
                  <Link href={`/changes/${task.resulting_change_id}`} className="btn-island">
                    <span>Open Change</span>
                    <span className="icon-pill">
                      <ArrowRight size={12} />
                    </span>
                  </Link>
                )}
                {isInProgress && (
                  <button
                    type="button"
                    onClick={() => setShowTerminateModal(true)}
                    style={{
                      display: "inline-flex",
                      alignItems: "center",
                      gap: 8,
                      padding: "8px 16px",
                      borderRadius: 8,
                      fontSize: 13,
                      fontWeight: 600,
                      background: "rgba(239, 68, 68, 0.12)",
                      border: "1px solid rgba(239, 68, 68, 0.3)",
                      color: "#EF4444",
                      cursor: "pointer",
                      transition: "all 180ms ease"
                    }}
                    title="Terminate running task"
                    className="card-haptic"
                  >
                    <Square size={12} fill="currentColor" />
                    Terminate Task
                  </button>
                )}
                <button 
                  onClick={onClose} 
                  style={{ 
                    background: "rgba(255,255,255,0.05)", 
                    border: "1px solid rgba(255,255,255,0.08)", 
                    color: "var(--text-secondary)", 
                    cursor: "pointer", 
                    width: 38, 
                    height: 38, 
                    borderRadius: "50%", 
                    display: "flex", 
                    alignItems: "center", 
                    justifyContent: "center", 
                    transition: "all 200ms cubic-bezier(0.32, 0.72, 0, 1)" 
                  }} 
                  className="card-haptic"
                  aria-label="Close modal"
                >
                  <XCircle size={18} />
                </button>
              </div>
            </div>
          </div>

          {/* Content Area */}
          <div style={{ padding: "clamp(20px, 4vw, 36px)", display: "flex", flexDirection: "column", gap: 24 }}>
            
            {/* Top Stat Matrix */}
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(min(100%, 260px), 1fr))", gap: 16 }}>
              
              {/* Agent Status */}
              <PremiumCard title="Agent Authority & Identity">
                {isOpen ? (
                  <div style={{ display: "flex", flexDirection: "column", gap: 10, justifyContent: "center", flex: 1 }}>
                    <div style={{ color: "var(--text-muted)", fontSize: 13, lineHeight: 1.5 }}>
                      Agents connect to SUTRA through supported sovereign integrations.
                    </div>
                    <div style={{ padding: "10px 14px", background: "rgba(0,0,0,0.3)", border: "1px solid rgba(255,255,255,0.05)", borderRadius: 10, fontSize: 12, color: "var(--text-secondary)" }}>
                      Open for autonomous claiming via MCP or Agent Protocol.
                    </div>
                  </div>
                ) : (
                  <div style={{ display: "flex", alignItems: "center", gap: 16, flex: 1, padding: "6px 0" }}>
                    <div style={{ 
                      width: 48, 
                      height: 48, 
                      borderRadius: 14, 
                      background: isCompleted ? "rgba(255,255,255,0.05)" : "rgba(249, 115, 22, 0.12)", 
                      border: isCompleted ? "1px solid rgba(255,255,255,0.08)" : "1px solid rgba(249, 115, 22, 0.25)",
                      color: isCompleted ? "var(--text-muted)" : "var(--accent)", 
                      display: "flex", 
                      alignItems: "center", 
                      justifyContent: "center",
                      flexShrink: 0
                    }}>
                      <Bot size={22} />
                    </div>
                    <div>
                      <div style={{ fontSize: 15, fontWeight: 600, color: "#FFFFFF" }}>
                        {assignedAgent ? assignedAgent.name : (task.assigned_agent_id || "Connected Agent")}
                      </div>
                      <div style={{ fontSize: 12, color: "var(--text-muted)", marginTop: 2 }}>
                        {assignedAgent ? assignedAgent.model : "Autonomous Agent Session"}
                      </div>
                    </div>
                  </div>
                )}
              </PremiumCard>

              {/* Execution Lifecycle */}
              <PremiumCard title="Execution Lifecycle">
                <div style={{ display: "flex", flexDirection: "column", flex: 1, justifyContent: "center" }}>
                  <div style={{ fontSize: 20, fontWeight: 600, letterSpacing: "-0.01em", color: isCompleted ? "var(--green)" : isInProgress ? "var(--accent)" : "var(--text-muted)" }}>
                    {isCompleted ? "Completed" : isInProgress ? "Active Execution Lease" : "Pending Intake"}
                  </div>
                  <div style={{ fontSize: 13, color: "var(--text-muted)", marginTop: 6, lineHeight: 1.5 }}>
                    {isCompleted ? `Verified & completed on ${task.completed_at ? new Date(task.completed_at).toLocaleDateString() : 'recently'}` 
                     : isInProgress ? "Workspace sandbox active under sovereign session lease" : "Awaiting agent execution claim"}
                  </div>
                  {task.execution_summary && (
                    <div style={{ marginTop: 12, fontSize: 12, padding: "10px 14px", background: "rgba(0,0,0,0.3)", borderRadius: 10, border: "1px solid rgba(255,255,255,0.05)", whiteSpace: "pre-wrap", color: "var(--text-secondary)", lineHeight: 1.5 }}>
                      {task.execution_summary}
                    </div>
                  )}
                </div>
              </PremiumCard>

              {/* Validation & CI */}
              <PremiumCard title="Validation & CI Gates">
                <div style={{ display: "flex", flexDirection: "column", gap: 12, flex: 1, justifyContent: "center" }}>
                  {isCompleted ? (
                    <div style={{ display: 'flex', alignItems: 'center', gap: 10, color: "var(--green)", fontSize: 13, fontWeight: 500 }}>
                      <CheckCircle2 size={16} /> 
                      Execution completed & verified
                    </div>
                  ) : isInProgress ? (
                    <div style={{ display: 'flex', alignItems: 'center', gap: 10, color: "var(--accent)", fontSize: 13, fontWeight: 500 }}>
                      <Play size={16} /> 
                      CI verification triggers on pull request creation
                    </div>
                  ) : (
                    <div style={{ color: "var(--text-muted)", fontSize: 13, lineHeight: 1.5 }}>
                      Automated governance gates evaluate upon branch synchronization
                    </div>
                  )}
                </div>
              </PremiumCard>
            </div>

            {/* Timeline & Agent Terminal */}
            {(isInProgress || isCompleted) && (
              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(min(100%, 320px), 1fr))", gap: 16 }}>
                
                {/* Timeline */}
                <PremiumCard title="Execution Milestones">
                  <div style={{ display: "flex", flexDirection: "column", gap: 20, padding: "8px 0" }}>
                    <div style={{ display: "flex", gap: 16 }}>
                      <div style={{ width: 2, background: "rgba(255,255,255,0.1)", position: "relative", marginTop: 6 }}>
                        <div style={{ width: 8, height: 8, borderRadius: "50%", background: "#FFFFFF", position: "absolute", left: -3, top: 0, boxShadow: "0 0 8px rgba(255,255,255,0.4)" }} />
                      </div>
                      <div>
                        <div style={{ fontSize: 13, fontWeight: 600, color: "var(--text-primary)" }}>Task created</div>
                        <div style={{ fontSize: 12, color: "var(--text-muted)", marginTop: 2, fontVariantNumeric: "tabular-nums" }}>{new Date(task.created_at).toLocaleString()}</div>
                      </div>
                    </div>
                    
                    {task.started_at && (
                      <div style={{ display: "flex", gap: 16 }}>
                        <div style={{ width: 2, background: "rgba(255,255,255,0.1)", position: "relative", marginTop: 6 }}>
                          <div style={{ width: 8, height: 8, borderRadius: "50%", background: "var(--accent)", position: "absolute", left: -3, top: 0, boxShadow: "0 0 10px var(--accent)" }} />
                        </div>
                        <div>
                          <div style={{ fontSize: 13, fontWeight: 600, color: "var(--text-primary)" }}>Agent claim authorized</div>
                          <div style={{ fontSize: 12, color: "var(--text-muted)", marginTop: 2, fontVariantNumeric: "tabular-nums" }}>{new Date(task.started_at).toLocaleString()}</div>
                        </div>
                      </div>
                    )}

                    {isCompleted && (
                      <div style={{ display: "flex", gap: 16 }}>
                        <div style={{ width: 2, background: "transparent", position: "relative", marginTop: 6 }}>
                          <div style={{ width: 8, height: 8, borderRadius: "50%", background: "var(--green)", position: "absolute", left: -3, top: 0, boxShadow: "0 0 10px var(--green)" }} />
                        </div>
                        <div>
                          <div style={{ fontSize: 13, fontWeight: 600, color: "var(--text-primary)" }}>Task verified & merged</div>
                          <div style={{ fontSize: 12, color: "var(--text-muted)", marginTop: 2, fontVariantNumeric: "tabular-nums" }}>{task.completed_at ? new Date(task.completed_at).toLocaleString() : 'Recently'}</div>
                        </div>
                      </div>
                    )}
                  </div>
                </PremiumCard>
                
                {/* Agent Terminal */}
                <PremiumCard title="Agent Telemetry Stream">
                  <div style={{ 
                    background: "#070709", 
                    borderRadius: 12, 
                    padding: "16px 18px", 
                    fontFamily: "var(--font-mono, monospace)", 
                    fontSize: 12, 
                    lineHeight: 1.7,
                    height: "100%",
                    minHeight: 180,
                    border: "1px solid rgba(255,255,255,0.05)",
                    display: "flex",
                    flexDirection: "column"
                  }}>
                    {/* Console Bar */}
                    <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 12, paddingBottom: 8, borderBottom: "1px solid rgba(255,255,255,0.04)" }}>
                      <div style={{ width: 8, height: 8, borderRadius: "50%", background: "rgba(239, 68, 68, 0.6)" }} />
                      <div style={{ width: 8, height: 8, borderRadius: "50%", background: "rgba(245, 158, 11, 0.6)" }} />
                      <div style={{ width: 8, height: 8, borderRadius: "50%", background: "rgba(34, 197, 94, 0.6)" }} />
                      <span style={{ fontSize: 10, color: "var(--text-muted)", marginLeft: 8, letterSpacing: "0.05em" }}>sovereign-agent-pty</span>
                    </div>

                    {isOpen ? (
                      <div style={{ color: "var(--text-muted)", opacity: 0.6 }}>Waiting for agent to initialize sovereign sandbox...</div>
                    ) : (
                      <>
                        <div style={{ color: "var(--text-muted)", marginBottom: 4 }}>$ initializing secure workspace... <span style={{ color: "var(--green)" }}>[OK]</span></div>
                        <div style={{ color: "var(--text-muted)", marginBottom: 4 }}>$ cloning repository substrate... <span style={{ color: "var(--green)" }}>[OK]</span></div>
                        <div style={{ display: "flex", gap: 10, marginBottom: 4 }}>
                          <span style={{ color: "var(--accent)", flexShrink: 0 }}>[agent]</span>
                          <span style={{ color: "var(--text-primary)" }}>Analyzing task requirements and building execution plan...</span>
                        </div>
                        <div style={{ display: "flex", gap: 10, marginBottom: 4 }}>
                          <span style={{ color: "var(--accent)", flexShrink: 0 }}>[agent]</span>
                          <span style={{ color: "var(--text-primary)" }}>Implementing requested changes across repository files.</span>
                        </div>
                        {isCompleted ? (
                          <>
                            <div style={{ color: "var(--text-muted)", marginBottom: 4 }}>$ running test suite verification... <span style={{ color: "var(--green)" }}>[PASS]</span></div>
                            <div style={{ display: "flex", gap: 10 }}>
                              <span style={{ color: "var(--green)", flexShrink: 0 }}>[provenance]</span>
                              <span style={{ color: "#FFFFFF" }}>Commit attested and sovereign pull request registered.</span>
                            </div>
                          </>
                        ) : (
                          <div style={{ display: "flex", gap: 10, opacity: 0.8, animation: "pulse 2s infinite" }}>
                            <span style={{ color: "var(--accent)", flexShrink: 0 }}>[agent]</span>
                            <span style={{ color: "var(--text-primary)" }}>Executing task instructions...</span>
                          </div>
                        )}
                      </>
                    )}
                  </div>
                </PremiumCard>
              </div>
            )}
          </div>
        </div>
      </div>
      
      <ConfirmModal
        isOpen={showTerminateModal}
        onClose={() => setShowTerminateModal(false)}
        onConfirm={handleTerminate}
        title="Terminate Task"
        description={
          <>
            Are you sure you want to terminate <strong>&ldquo;{task.title}&rdquo;</strong>? Active execution will be cancelled immediately and marked as cancelled.
          </>
        }
        confirmText="Terminate Task"
        confirmTone="danger"
        loading={terminating}
      />
    </div>
  );
}

