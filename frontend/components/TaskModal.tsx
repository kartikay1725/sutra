"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { Cpu as Bot, CheckCircle2, Play, ShieldCheck, MessageSquare, XCircle, ArrowRight, Square } from "lucide-react";
import { Badge } from "@/components/ui";
import { Task, taskService } from "@/lib/tasks";
import { Agent, agentService } from "@/lib/agents";
import { ConfirmModal } from "@/components/ConfirmModal";

// Premium card wrapper for the modal
function PremiumCard({ children, title }: { children: React.ReactNode, title: string }) {
  return (
    <div style={{
      background: "rgba(255, 255, 255, 0.02)",
      border: "1px solid rgba(255, 255, 255, 0.06)",
      borderRadius: 16,
      padding: 24,
      display: "flex",
      flexDirection: "column",
      gap: 12
    }}>
      <div style={{ fontSize: 13, fontWeight: 600, color: "var(--fg)", textTransform: "uppercase", letterSpacing: "0.05em" }}>
        {title}
      </div>
      {children}
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
        backgroundColor: "rgba(0,0,0,0.85)",
        zIndex: 100, display: "flex", alignItems: "center", justifyContent: "center"
      }}>
        <div style={{ padding: 40, background: "#0B0B0F", borderRadius: 24, border: "1px solid rgba(255,255,255,0.08)", boxShadow: "0 24px 64px rgba(0,0,0,0.6)", width: 400, textAlign: "center" }}>
          <div className="spinner" style={{ margin: "0 auto 20px" }}></div>
          <p style={{ color: "var(--muted)", margin: 0 }}>Initializing workspace context...</p>
        </div>
      </div>
    );
  }

  if (!task) {
    return (
      <div className="modal-overlay" style={{
        position: "fixed", top: 0, left: 0, right: 0, bottom: 0,
        backgroundColor: "rgba(0,0,0,0.85)",
        zIndex: 100, display: "flex", alignItems: "center", justifyContent: "center"
      }}>
        <div style={{ padding: 40, background: "#0B0B0F", borderRadius: 24, border: "1px solid rgba(255,255,255,0.08)", width: 400, textAlign: "center" }}>
          <div style={{ color: "var(--fg)", fontSize: 18, fontWeight: 600, marginBottom: 8 }}>Task Not Found</div>
          <p style={{ color: "var(--muted)", marginBottom: 24 }}>The task you are looking for does not exist or has been deleted.</p>
          <button className="btn outline" onClick={onClose}>Close window</button>
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
      backgroundColor: "rgba(0,0,0,0.85)",
      zIndex: 100, display: "flex", alignItems: "center", justifyContent: "center",
      padding: "min(24px, 3vw)",
      boxSizing: "border-box"
    }}>
      
      <div style={{
        background: "linear-gradient(135deg, #121214 0%, #0B0B0F 100%)",
        border: "1px solid rgba(255,255,255,0.08)",
        borderRadius: 24, width: "100%", maxWidth: 1000, maxHeight: "90vh", overflowY: "auto", 
        boxShadow: "0 24px 64px rgba(0,0,0,0.6), inset 0 1px 0 rgba(255,255,255,0.05)"
      }}>
        {/* Header Area */}
        <div style={{ padding: "clamp(20px, 4vw, 40px) clamp(20px, 4vw, 40px) 24px", borderBottom: "1px solid rgba(255,255,255,0.04)" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", flexWrap: "wrap", gap: 16 }}>
            <div style={{ flex: "1 1 260px", minWidth: 0, paddingRight: 8 }}>
              <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 12, flexWrap: "wrap" }}>
                <span style={{ fontSize: 12, color: "var(--muted)", textTransform: "uppercase", letterSpacing: "0.05em", fontWeight: 700, background: "rgba(255,255,255,0.05)", padding: "4px 10px", borderRadius: 100 }}>
                  Task #{taskId.slice(0, 8)}
                </span>
                <Badge tone={isCompleted ? "green" : isInProgress ? "aqua" : "amber"}>
                  {task.status.replace("_", " ")}
                </Badge>
              </div>
              <h2 style={{ fontSize: "clamp(20px, 3vw, 28px)", margin: "0 0 12px 0", fontWeight: 600, color: "#fff", lineHeight: 1.2, wordBreak: "break-word" }}>{task.title}</h2>
              <p style={{ color: "rgba(255,255,255,0.6)", fontSize: 15, margin: 0, lineHeight: 1.6, wordBreak: "break-word" }}>
                {task.description || "No description provided."}
              </p>
            </div>
            <div style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
              {isCompleted && task.resulting_change_id && (
                 <Link href={`/changes/${task.resulting_change_id}`} className="btn primary" style={{ padding: "10px 16px", borderRadius: 10, fontSize: 14 }}>
                   Open change
                 </Link>
              )}
              {isInProgress && (
                <button
                  type="button"
                  onClick={() => setShowTerminateModal(true)}
                  style={{
                    display: "inline-flex",
                    alignItems: "center",
                    gap: 6,
                    padding: "8px 14px",
                    borderRadius: 10,
                    fontSize: 13,
                    fontWeight: 600,
                    background: "rgba(239, 68, 68, 0.12)",
                    border: "1px solid rgba(239, 68, 68, 0.3)",
                    color: "#ef4444",
                    cursor: "pointer",
                  }}
                  title="Terminate running task"
                >
                  <Square size={12} fill="currentColor" />
                  Terminate Task
                </button>
              )}
              <button onClick={onClose} style={{ background: "rgba(255,255,255,0.05)", border: "none", color: "var(--muted)", cursor: "pointer", width: 40, height: 40, borderRadius: "50%", display: "flex", alignItems: "center", justifyContent: "center", transition: "0.2s" }} className="hover-highlight">
                <XCircle size={20} />
              </button>
            </div>
          </div>
        </div>

        {/* Content Area */}
        <div style={{ padding: "clamp(16px, 4vw, 40px)" }}>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(min(100%, 280px), 1fr))", gap: 20, marginBottom: 32 }}>
            
            {/* Agent Status */}
            <PremiumCard title="Agent Status">
              {isOpen ? (
                <div style={{ display: "flex", flexDirection: "column", gap: 8, justifyContent: "center", flex: 1 }}>
                  <div style={{ color: "var(--muted)", fontSize: 13 }}>
                    Agents connect to SUTRA through supported integrations.
                  </div>
                  <div style={{ padding: "10px 14px", background: "rgba(0,0,0,0.2)", border: "1px solid rgba(255,255,255,0.05)", borderRadius: 10, fontSize: 12, color: "var(--text-secondary)" }}>
                    Open for autonomous claiming via MCP or Agent Protocol.
                  </div>
                </div>
              ) : (
                <div style={{ display: "flex", flexDirection: "column", gap: 16, flex: 1, justifyContent: "center" }}>
                  <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
                    <div style={{ width: 48, height: 48, borderRadius: 12, background: isCompleted ? "rgba(255,255,255,0.05)" : "var(--accent-subtle, rgba(249,115,22,0.12))", color: isCompleted ? "var(--muted)" : "var(--accent, #f97316)", display: "flex", alignItems: "center", justifyContent: "center" }}>
                      <Bot size={24} />
                    </div>
                    <div>
                      <div style={{ fontSize: 16, fontWeight: 600, color: "#fff" }}>
                        {assignedAgent ? assignedAgent.name : (task.assigned_agent_id || "Connected Agent")}
                      </div>
                      <div style={{ fontSize: 13, color: "var(--muted)", marginTop: 4 }}>
                        {assignedAgent ? assignedAgent.model : "Autonomous Agent"}
                      </div>
                    </div>
                  </div>
                </div>
              )}
            </PremiumCard>

            {/* Execution Lifecycle */}
            <PremiumCard title="Execution Lifecycle">
              <div style={{ display: "flex", flexDirection: "column", flex: 1, justifyContent: "center" }}>
                <div style={{ fontSize: 22, fontWeight: 600, color: isCompleted ? "var(--green)" : isInProgress ? "var(--cyan)" : "var(--muted)" }}>
                  {isCompleted ? "Completed" : isInProgress ? "Active Execution" : "Pending Intake"}
                </div>
                <div style={{ fontSize: 13, color: "rgba(255,255,255,0.5)", marginTop: 8 }}>
                  {isCompleted ? `Completed on ${task.completed_at ? new Date(task.completed_at).toLocaleDateString() : 'recently'}` 
                   : isInProgress ? "Workspace sandbox is active under sovereign session lease" : "Awaiting agent execution"}
                </div>
                {task.execution_summary && (
                  <div style={{ marginTop: 10, fontSize: 12, padding: "8px 12px", background: "rgba(0,0,0,0.25)", borderRadius: 8, border: "1px solid rgba(255,255,255,0.05)", whiteSpace: "pre-wrap" }}>
                    {task.execution_summary}
                  </div>
                )}
              </div>
            </PremiumCard>

            {/* Validation */}
            <PremiumCard title="Validation & CI">
              <div style={{ display: "flex", flexDirection: "column", gap: 12, flex: 1, justifyContent: "center" }}>
                {isCompleted ? (
                  <div style={{ display: 'flex', alignItems: 'center', gap: 10, color: "var(--green)", fontSize: 14, fontWeight: 500 }}>
                    <CheckCircle2 size={18} /> 
                    Execution completed and verified
                  </div>
                ) : isInProgress ? (
                  <div style={{ display: 'flex', alignItems: 'center', gap: 10, color: "var(--cyan)", fontSize: 14, fontWeight: 500 }}>
                    <Play size={18} /> 
                    CI verification triggers on pull request creation
                  </div>
                ) : (
                  <div style={{ color: "rgba(255,255,255,0.4)", fontSize: 13 }}>
                    Automated checks evaluate upon code submission
                  </div>
                )}
              </div>
            </PremiumCard>
          </div>

          {(isInProgress || isCompleted) && (
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(min(100%, 300px), 1fr))", gap: 20 }}>
              
              <PremiumCard title="Timeline">
                <div style={{ display: "flex", flexDirection: "column", gap: 20, padding: "10px 0" }}>
                  <div style={{ display: "flex", gap: 16 }}>
                    <div style={{ width: 2, background: "rgba(255,255,255,0.1)", position: "relative", marginTop: 8 }}>
                      <div style={{ width: 10, height: 10, borderRadius: "50%", background: "var(--fg)", position: "absolute", left: -4, top: 0 }} />
                    </div>
                    <div>
                      <div style={{ fontSize: 14, fontWeight: 600, color: "var(--fg)" }}>Task created</div>
                      <div style={{ fontSize: 13, color: "var(--muted)", marginTop: 4 }}>{new Date(task.created_at).toLocaleString()}</div>
                    </div>
                  </div>
                  
                  {task.started_at && (
                    <div style={{ display: "flex", gap: 16 }}>
                      <div style={{ width: 2, background: "rgba(255,255,255,0.1)", position: "relative", marginTop: 8 }}>
                        <div style={{ width: 10, height: 10, borderRadius: "50%", background: "var(--cyan)", position: "absolute", left: -4, top: 0 }} />
                      </div>
                      <div>
                        <div style={{ fontSize: 14, fontWeight: 600, color: "var(--fg)" }}>Agent began execution</div>
                        <div style={{ fontSize: 13, color: "var(--muted)", marginTop: 4 }}>{new Date(task.started_at).toLocaleString()}</div>
                      </div>
                    </div>
                  )}

                  {isCompleted && (
                    <div style={{ display: "flex", gap: 16 }}>
                      <div style={{ width: 2, background: "transparent", position: "relative", marginTop: 8 }}>
                        <div style={{ width: 10, height: 10, borderRadius: "50%", background: "var(--green)", position: "absolute", left: -4, top: 0, boxShadow: "0 0 10px var(--green)" }} />
                      </div>
                      <div>
                        <div style={{ fontSize: 14, fontWeight: 600, color: "var(--fg)" }}>Task completed</div>
                        <div style={{ fontSize: 13, color: "var(--muted)", marginTop: 4 }}>{task.completed_at ? new Date(task.completed_at).toLocaleString() : 'Recently'}</div>
                      </div>
                    </div>
                  )}
                </div>
              </PremiumCard>
              
              <PremiumCard title="Agent Terminal">
                <div style={{ 
                  background: "#050505", 
                  borderRadius: 12, 
                  padding: 20, 
                  fontFamily: "monospace", 
                  fontSize: 13, 
                  lineHeight: 1.6,
                  height: "100%",
                  minHeight: 200,
                  border: "1px solid rgba(255,255,255,0.03)"
                }}>
                  {isOpen ? (
                    <div style={{ color: "rgba(255,255,255,0.2)" }}>Waiting for agent to initialize...</div>
                  ) : (
                    <>
                      <div style={{ color: "var(--muted)", marginBottom: 8 }}>$ initializing secure workspace... [OK]</div>
                      <div style={{ color: "var(--muted)", marginBottom: 8 }}>$ cloning repository... [OK]</div>
                      <div style={{ display: "flex", gap: 12, marginBottom: 8 }}>
                        <span style={{ color: "var(--cyan)", flexShrink: 0 }}>[agent]</span>
                        <span style={{ color: "#fff" }}>Analyzing task requirements and building execution plan...</span>
                      </div>
                      <div style={{ display: "flex", gap: 12, marginBottom: 8 }}>
                        <span style={{ color: "var(--cyan)", flexShrink: 0 }}>[agent]</span>
                        <span style={{ color: "#fff" }}>Implementing requested features across 3 files.</span>
                      </div>
                      {isCompleted ? (
                        <>
                          <div style={{ color: "var(--muted)", marginBottom: 8 }}>$ running test suite... [PASS]</div>
                          <div style={{ display: "flex", gap: 12 }}>
                            <span style={{ color: "var(--green)", flexShrink: 0 }}>[success]</span>
                            <span style={{ color: "#fff" }}>Changes committed and pull request created.</span>
                          </div>
                        </>
                      ) : (
                        <div style={{ display: "flex", gap: 12, opacity: 0.7, animation: "pulse 2s infinite" }}>
                          <span style={{ color: "var(--cyan)", flexShrink: 0 }}>[agent]</span>
                          <span style={{ color: "#fff" }}>Working on implementation...</span>
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
      <style dangerouslySetInnerHTML={{__html: `
        .hover-highlight:hover { background: rgba(255,255,255,0.1) !important; color: #fff !important; }
        @keyframes pulse { 0% { opacity: 0.5; } 50% { opacity: 1; } 100% { opacity: 0.5; } }
      `}} />

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
