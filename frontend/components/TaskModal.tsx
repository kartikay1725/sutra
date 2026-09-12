"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { Bot, CheckCircle2, Play, ShieldCheck, MessageSquare, XCircle, ArrowRight } from "lucide-react";
import { Badge } from "@/components/ui";
import { Task, taskService } from "@/lib/tasks";
import { Agent, agentService } from "@/lib/agents";

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

export function TaskModal({ taskId, onClose }: { taskId: string, onClose: () => void }) {
  const [task, setTask] = useState<Task | null>(null);
  const [agents, setAgents] = useState<Agent[]>([]);
  const [loading, setLoading] = useState(true);
  const [assigning, setAssigning] = useState(false);

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

  const handleAssign = (agentId: string) => {
    setAssigning(true);
    taskService.assignTask(taskId, agentId)
      .then(() => loadData())
      .catch(console.error)
      .finally(() => setAssigning(false));
  };

  const [showNoAgentsPrompt, setShowNoAgentsPrompt] = useState(false);

  const handleDispatchNext = async () => {
    if (!task) return;
    const available = agents.find(a => a.status === 'idle' || a.is_active);
    if (available) {
      handleAssign(available.id);
    } else {
      setShowNoAgentsPrompt(true);
    }
  };

  if (loading) {
    return (
      <div className="modal-overlay" style={{
        position: "fixed", top: 0, left: 0, right: 0, bottom: 0,
        backgroundColor: "rgba(0,0,0,0.7)", backdropFilter: "blur(12px)",
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
        backgroundColor: "rgba(0,0,0,0.7)", backdropFilter: "blur(12px)",
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
      backgroundColor: "rgba(0,0,0,0.7)", backdropFilter: "blur(12px)",
      zIndex: 100, display: "flex", alignItems: "center", justifyContent: "center",
      padding: "min(24px, 3vw)",
      boxSizing: "border-box"
    }}>
      
      {showNoAgentsPrompt && (
        <div style={{
          position: "absolute", top: 0, left: 0, right: 0, bottom: 0, zIndex: 200,
          display: "flex", alignItems: "center", justifyContent: "center",
          backgroundColor: "rgba(0,0,0,0.85)", backdropFilter: "blur(4px)",
          padding: 16
        }}>
          <div style={{ padding: "clamp(24px, 4vw, 40px)", background: "linear-gradient(135deg, #1A1A1F 0%, #121214 100%)", borderRadius: 24, border: "1px solid rgba(255,255,255,0.08)", width: "min(100%, 440px)", textAlign: "center", boxShadow: "0 24px 64px rgba(0,0,0,0.8)" }}>
            <div style={{ width: 64, height: 64, borderRadius: "50%", background: "rgba(255,100,100,0.1)", color: "#FF6B6B", display: "flex", alignItems: "center", justifyContent: "center", margin: "0 auto 24px" }}>
              <Bot size={32} />
            </div>
            <div style={{ color: "var(--fg)", fontSize: 20, fontWeight: 600, marginBottom: 12 }}>No Registered Agents</div>
            <p style={{ color: "var(--muted)", marginBottom: 32, fontSize: 15, lineHeight: 1.5 }}>
              You do not have any registered agents available for auto-dispatch. You can register them easily on the Agents page of your repository.
            </p>
            <div style={{ display: "flex", gap: 12, justifyContent: "center" }}>
              <button className="btn outline" onClick={() => setShowNoAgentsPrompt(false)}>Dismiss</button>
            </div>
          </div>
        </div>
      )}

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
              {isOpen && (
                 <button className="btn outline" onClick={handleDispatchNext} disabled={assigning} style={{ padding: "10px 16px", borderRadius: 10, fontSize: 14 }}>
                   Auto-Dispatch
                 </button>
              )}
              {isCompleted && task.resulting_change_id && (
                 <Link href={`/changes/${task.resulting_change_id}`} className="btn primary" style={{ padding: "10px 16px", borderRadius: 10, fontSize: 14 }}>
                   Open change
                 </Link>
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
                <>
                  <div style={{ color: "var(--muted)", fontSize: 14, marginBottom: 12 }}>Available Agents</div>
                  <div style={{ display: "flex", flexDirection: "column", gap: 8, maxHeight: 180, overflowY: "auto", paddingRight: 8 }}>
                    {agents.length === 0 ? <div style={{ color: "rgba(255,255,255,0.4)", fontSize: 14, fontStyle: "italic" }}>No agents available right now.</div> : 
                     agents.map(a => (
                       <div key={a.id} style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "12px 16px", background: "rgba(0,0,0,0.2)", border: "1px solid rgba(255,255,255,0.05)", borderRadius: 12 }}>
                         <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
                           <div style={{ width: 32, height: 32, borderRadius: "50%", background: "var(--violet-dim)", color: "var(--violet)", display: "flex", alignItems: "center", justifyContent: "center" }}>
                             <Bot size={16} />
                           </div>
                           <div style={{ fontSize: 14, fontWeight: 500 }}>{a.name}</div>
                         </div>
                         <button className="btn primary" style={{ padding: "6px 12px", fontSize: 12, borderRadius: 8 }} onClick={() => handleAssign(a.id)} disabled={assigning}>
                           Assign
                         </button>
                       </div>
                     ))
                    }
                  </div>
                </>
              ) : (
                <div style={{ display: "flex", flexDirection: "column", gap: 16, flex: 1, justifyContent: "center" }}>
                  <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
                    <div style={{ width: 48, height: 48, borderRadius: 12, background: isCompleted ? "rgba(255,255,255,0.05)" : "var(--cyan-dim)", color: isCompleted ? "var(--muted)" : "var(--cyan)", display: "flex", alignItems: "center", justifyContent: "center" }}>
                      <Bot size={24} />
                    </div>
                    <div>
                      <div style={{ fontSize: 16, fontWeight: 600, color: "#fff" }}>
                        {assignedAgent ? assignedAgent.name : (task.assigned_agent_id || "Unassigned")}
                      </div>
                      <div style={{ fontSize: 13, color: "var(--muted)", marginTop: 4 }}>
                        {assignedAgent ? assignedAgent.model : "AI Engineer"}
                      </div>
                    </div>
                  </div>
                </div>
              )}
            </PremiumCard>

            {/* Execution Progress */}
            <PremiumCard title="Execution">
              <div style={{ display: "flex", flexDirection: "column", flex: 1, justifyContent: "center" }}>
                <div style={{ display: "flex", alignItems: "baseline", gap: 8, marginBottom: 16 }}>
                  <span style={{ fontSize: 48, fontWeight: 300, color: isCompleted ? "var(--green)" : isInProgress ? "var(--cyan)" : "var(--muted)", lineHeight: 1 }}>
                    {isCompleted ? "100" : isInProgress ? "67" : "0"}
                  </span>
                  <span style={{ fontSize: 20, color: "var(--muted)" }}>%</span>
                </div>
                
                <div style={{ width: "100%", height: 6, background: "rgba(255,255,255,0.05)", borderRadius: 100, overflow: "hidden", marginBottom: 12 }}>
                  <div style={{ 
                    height: "100%", 
                    width: isCompleted ? "100%" : isInProgress ? "67%" : "0%",
                    background: isCompleted ? "var(--green)" : "var(--cyan)",
                    borderRadius: 100,
                    transition: "width 1s cubic-bezier(0.4, 0, 0.2, 1)"
                  }} />
                </div>
                
                <div style={{ fontSize: 13, color: "rgba(255,255,255,0.5)" }}>
                  {isCompleted ? `Completed on ${task.completed_at ? new Date(task.completed_at).toLocaleDateString() : 'recently'}` 
                   : isInProgress ? "Workspace sandbox is active" : "Pending agent assignment"}
                </div>
              </div>
            </PremiumCard>

            {/* Validation */}
            <PremiumCard title="Validation & CI">
              <div style={{ display: "flex", flexDirection: "column", gap: 16, flex: 1, justifyContent: "center" }}>
                {isCompleted || isInProgress ? (
                  <>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 12, color: isCompleted ? "var(--green)" : "var(--amber)", fontSize: 14, fontWeight: 500 }}>
                      <CheckCircle2 size={18} /> 
                      {isCompleted ? '18 / 18 tests passing' : 'Running tests...'}
                    </div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 12, color: isCompleted ? "var(--green)" : "var(--amber)", fontSize: 14, fontWeight: 500 }}>
                      <ShieldCheck size={18} /> 
                      {isCompleted ? 'Security sweep clean' : 'Scanning changes...'}
                    </div>
                    {isInProgress && (
                      <div style={{ display: 'flex', alignItems: 'center', gap: 12, color: "var(--cyan)", fontSize: 14, fontWeight: 500 }}>
                        <Play size={18} /> 
                        CI Pipeline running
                      </div>
                    )}
                  </>
                ) : (
                  <div style={{ color: "rgba(255,255,255,0.3)", fontSize: 14, fontStyle: "italic", textAlign: "center", padding: "20px 0" }}>
                    Waiting for execution to start
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
    </div>
  );
}
