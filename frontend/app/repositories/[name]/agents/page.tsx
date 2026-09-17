"use client";

import { use, useEffect, useState, useMemo } from "react";
import { useRouter } from "next/navigation";
import { AppShell, PageHead, Card, Btn, SkeletonAgentList } from "@/components/shell";
import { agentService, Agent } from "@/lib/agents";
import { taskService } from "@/lib/tasks";
import { authService } from "@/lib/auth";
import { ConfirmModal } from "@/components/ConfirmModal";
import * as I from "lucide-react";

// ── helpers ──────────────────────────────────────────────────────────────────

function statusColor(s: string) {
  if (s === "active") return "#10b981";
  if (s === "revoked") return "#ef4444";
  return "#8a8a8a";
}

function statusLabel(agent: Agent) {
  if (!agent.is_active || agent.status === "revoked") return "Revoked";
  return "Active";
}

// ── Register Agent Modal ──────────────────────────────────────────────────────

function RegisterModal({ onClose, onCreated }: { onClose: () => void; onCreated: (agent: any) => void }) {
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [provider, setProvider] = useState("");
  const [model, setModel] = useState("");
  const [loading, setLoading] = useState(false);
  const [created, setCreated] = useState<{ name: string; token: string } | null>(null);
  const [error, setError] = useState<string | null>(null);

  const inputStyle = {
    width: "100%", padding: "9px 12px", borderRadius: 6, border: "1px solid var(--line)",
    background: "var(--bg)", color: "var(--fg)", fontSize: 14, boxSizing: "border-box" as const,
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true); setError(null);
    try {
      const agent = await agentService.createAgent({
        name,
        description: description || undefined,
        provider: provider || undefined,
        model: model || undefined,
      });
      setCreated({ name: agent.name, token: agent.token });
      onCreated(agent);
    } catch (e: any) {
      setError(e?.message || "Failed to create agent");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.85)", zIndex: 1000, display: "flex", alignItems: "center", justifyContent: "center" }}>
      <Card style={{ width: 480, padding: 28, position: "relative" }}>
        <button onClick={onClose} style={{ position: "absolute", top: 16, right: 16, background: "none", border: "none", cursor: "pointer", color: "var(--muted)" }}>
          <I.X size={18} />
        </button>

        {created ? (
          <div>
            <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 20 }}>
              <I.CheckCircle2 size={22} color="#22d3ee" />
              <div style={{ fontSize: 17, fontWeight: 700, color: "var(--fg)" }}>Agent Registered</div>
            </div>
            <div style={{ marginBottom: 12, color: "var(--muted)", fontSize: 13 }}>
              <strong style={{ color: "var(--fg)" }}>{created.name}</strong> has been registered. Copy this token — it will not be shown again.
            </div>
            <div style={{ background: "var(--bg-subtle)", border: "1px solid rgba(34,211,238,0.3)", borderRadius: 8, padding: 14, fontFamily: "monospace", fontSize: 12, color: "#22d3ee", wordBreak: "break-all", marginBottom: 20 }}>
              {created.token}
            </div>
            <Btn primary onClick={onClose} style={{ width: "100%", justifyContent: "center" }}>Done</Btn>
          </div>
        ) : (
          <form onSubmit={handleSubmit}>
            <div style={{ fontSize: 17, fontWeight: 700, color: "var(--fg)", marginBottom: 4 }}>Register Agent</div>
            <div style={{ fontSize: 13, color: "var(--muted)", marginBottom: 20 }}>Connect an autonomous agent to SUTRA.</div>
            <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
              <div>
                <label style={{ fontSize: 13, fontWeight: 600, color: "var(--fg)", display: "block", marginBottom: 5 }}>
                  Name <span style={{ color: "#ef4444" }}>*</span>
                </label>
                <input value={name} onChange={e => setName(e.target.value)} placeholder="e.g. Security Agent" required style={inputStyle} />
              </div>
              <div>
                <label style={{ fontSize: 13, fontWeight: 600, color: "var(--fg)", display: "block", marginBottom: 5 }}>Description</label>
                <input value={description} onChange={e => setDescription(e.target.value)} placeholder="What does this agent do?" style={inputStyle} />
              </div>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
                <div>
                  <label style={{ fontSize: 13, fontWeight: 600, color: "var(--fg)", display: "block", marginBottom: 5 }}>Provider</label>
                  <input value={provider} onChange={e => setProvider(e.target.value)} placeholder="e.g. openai" style={inputStyle} />
                </div>
                <div>
                  <label style={{ fontSize: 13, fontWeight: 600, color: "var(--fg)", display: "block", marginBottom: 5 }}>Model</label>
                  <input value={model} onChange={e => setModel(e.target.value)} placeholder="e.g. gpt-4o" style={inputStyle} />
                </div>
              </div>
              {error && (
                <div style={{ padding: "10px 14px", borderRadius: 6, background: "rgba(239,68,68,0.08)", border: "1px solid rgba(239,68,68,0.3)", color: "#ef4444", fontSize: 13 }}>
                  {error}
                </div>
              )}
              <div style={{ display: "flex", gap: 10, justifyContent: "flex-end", marginTop: 4 }}>
                <Btn type="button" onClick={onClose}>Cancel</Btn>
                <Btn primary type="submit" disabled={loading || !name}>
                  {loading ? "Registering…" : "Register Agent"}
                </Btn>
              </div>
            </div>
          </form>
        )}
      </Card>
    </div>
  );
}

// ── Running Agent Card ────────────────────────────────────────────────────────

function AgentRunningCard({ agent, task, onClick, onTerminateTask }: { agent: Agent; task: any; onClick: () => void; onTerminateTask?: (taskId: string) => void }) {
  return (
    <div onClick={onClick} style={{ cursor: "pointer" }}>
    <Card style={{ padding: 0, overflow: "hidden", borderLeft: "3px solid #10b981" }}>
      <div style={{ padding: "20px 24px" }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 16 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
            <div style={{ position: "relative", width: 12, height: 12, flexShrink: 0 }}>
              <div style={{ position: "absolute", inset: 0, borderRadius: "50%", background: "#10b981", animation: "pulse-ring 1.5s ease-out infinite" }} />
              <div style={{ position: "absolute", inset: 0, borderRadius: "50%", background: "#10b981" }} />
            </div>
            <div>
              <div style={{ fontSize: 16, fontWeight: 700, color: "var(--fg)" }}>{agent.name}</div>
              {agent.provider && (
                <div style={{ fontSize: 12, color: "var(--muted)", fontFamily: "monospace" }}>
                  {agent.provider}{agent.model ? ` / ${agent.model}` : ""}
                </div>
              )}
            </div>
          </div>
          <span style={{ fontSize: 11, fontWeight: 700, letterSpacing: "0.8px", color: "#10b981", background: "rgba(16,185,129,0.1)", border: "1px solid rgba(16,185,129,0.3)", padding: "3px 10px", borderRadius: 4 }}>
            RUNNING
          </span>
        </div>

        {task && (
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16, background: "var(--bg-subtle)", padding: "10px 14px", borderRadius: 6 }}>
            <div style={{ display: "grid", gridTemplateColumns: "60px 1fr", gap: "4px 8px", fontSize: 13, flex: 1, minWidth: 0 }}>
              <span style={{ color: "var(--muted)" }}>Task:</span>
              <span style={{ color: "var(--fg)", fontWeight: 600, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{task.title}</span>
              <span style={{ color: "var(--muted)" }}>Priority:</span>
              <span style={{ color: task.priority === "urgent" ? "#ef4444" : task.priority === "high" ? "#f59e0b" : "var(--fg)", fontWeight: 500 }}>
                {task.priority || "normal"}
              </span>
            </div>
            {onTerminateTask && (
              <button
                type="button"
                onClick={(e) => {
                  e.stopPropagation();
                  onTerminateTask(task.id);
                }}
                className="badge red"
                style={{
                  cursor: "pointer",
                  display: "inline-flex",
                  alignItems: "center",
                  gap: 4,
                  padding: "4px 10px",
                  fontSize: "11px",
                  background: "rgba(239,68,68,0.12)",
                  border: "1px solid rgba(239,68,68,0.3)",
                  color: "#ef4444",
                  fontWeight: 600,
                  borderRadius: 4,
                  marginLeft: 12,
                  flexShrink: 0,
                }}
                title="Terminate running task"
              >
                <I.Square size={10} fill="currentColor" /> Terminate Task
              </button>
            )}
          </div>
        )}

        <div style={{ height: 4, background: "var(--line)", borderRadius: 2, overflow: "hidden", marginBottom: 12 }}>
          <div style={{ height: "100%", background: "#10b981", borderRadius: 2, width: "65%" }} />
        </div>

        <div className="meta"
          style={{
            display: "flex",
            alignItems: "center",
            gap: 4,
          }}
        >
          Live execution
          <I.Activity size={12} />
        </div>
      </div>
      </Card>
    </div>
  );
}

// ── Main Page ─────────────────────────────────────────────────────────────────

export default function AgentsPage({ params }: { params: Promise<{ name: string }> }) {
  const { name: repoName } = use(params);
  const router = useRouter();

  const [agents, setAgents] = useState<Agent[]>([]);
  const [agentTasks, setAgentTasks] = useState<Record<string, any[]>>({});
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState("All");
  const [search, setSearch] = useState("");
  const [taskToTerminate, setTaskToTerminate] = useState<{ id: string; title?: string } | null>(null);
  const [terminating, setTerminating] = useState(false);

  const load = async () => {
    setLoading(true);
    try {
      const user = await authService.getCurrentUser();
      const [agentList, taskList] = await Promise.all([
        agentService.listAgents(),
        taskService.listTasks(user.username, repoName).catch(() => []),
      ]);
      setAgents(agentList);

      const grouped: Record<string, any[]> = {};
      for (const task of taskList) {
        if (task.assigned_agent_id) {
          if (!grouped[task.assigned_agent_id]) grouped[task.assigned_agent_id] = [];
          grouped[task.assigned_agent_id].push(task);
        }
      }
      setAgentTasks(grouped);
    } catch (e) {
      console.error("Failed to load agents", e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, [repoName]);

  const handleTerminateTask = (taskId: string) => {
    let title = "Active task";
    for (const k in agentTasks) {
      const found = agentTasks[k].find(t => t.id === taskId);
      if (found) {
        title = found.title;
        break;
      }
    }
    setTaskToTerminate({ id: taskId, title });
  };

  const executeTerminateTask = async () => {
    if (!taskToTerminate) return;
    const taskId = taskToTerminate.id;
    setTerminating(true);
    try {
      await taskService.terminateTask(taskId);
      setAgentTasks(prev => {
        const next = { ...prev };
        for (const k in next) {
          next[k] = next[k].map(t => t.id === taskId ? { ...t, status: "cancelled" } : t);
        }
        return next;
      });
      setTaskToTerminate(null);
    } catch (err: any) {
      alert(err?.message || "Failed to terminate task");
    } finally {
      setTerminating(false);
    }
  };

  const filtered = useMemo(() => agents.filter(a => {
    const matchSearch = !search || a.name.toLowerCase().includes(search.toLowerCase());
    if (!matchSearch) return false;
    if (filter === "Active") return a.is_active && a.status === "active";
    if (filter === "Revoked") return !a.is_active || a.status === "revoked";
    return true;
  }), [agents, filter, search]);

  const runningAgents = filtered.filter(a =>
    a.is_active && (agentTasks[a.id] || []).some(t => t.status === "in_progress")
  );

  const stats = {
    total: agents.length,
    active: agents.filter(a => a.is_active && a.status === "active").length,
    running: agents.filter(a => a.is_active && a.status === "active" && (agentTasks[a.id] || []).some(t => t.status === "in_progress")).length,
    revoked: agents.filter(a => !a.is_active || a.status === "revoked").length,
  };

  return (
    <AppShell>

      <PageHead
        eyebrow={repoName}
        title="Agents"
        sub="Autonomous engineering workers connected to SUTRA."
      />
      <Card
        style={{
          marginBottom: 20,
        }}
      >
        <div
          className="card-pad"
          style={{
            display: "flex",
            alignItems: "center",
            gap: 14,
          }}
        >
          <I.Link2
            size={18}
            style={{
              color: "var(--link)",
              flexShrink: 0,
            }}
          />

          <div>
            <div className="title-sm">
              Connect an agent
            </div>

            <div
              className="sub"
              style={{
                marginTop: 4,
              }}
            >
              Agents connect from their own
              environment. Once an agent connects
              and is approved, it will appear here.
            </div>
          </div>
        </div>
      </Card>

      <div style={{ width: "100%" }}>

        {/* Stats */}
        <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 12, marginBottom: 24 }}>
          {[
            { label: "Total Agents", value: stats.total, icon: <I.Cpu size={18} />, color: "#f97316" },
            { label: "Active", value: stats.active, icon: <I.Activity size={18} />, color: "#10b981" },
            { label: "Running Tasks", value: stats.running, icon: <I.Workflow size={18} />, color: stats.running > 0 ? "#10b981" : "#8a8a8a" },
          ].map(s => (
            <Card key={s.label} style={{ padding: "16px 20px", display: "flex", alignItems: "center", gap: 14 }}>
              <div style={{ width: 38, height: 38, borderRadius: 8, background: `${s.color}15`, border: `1px solid ${s.color}30`, display: "flex", alignItems: "center", justifyContent: "center", color: s.color }}>
                {s.icon}
              </div>
              <div>
                <div style={{ fontSize: 22, fontWeight: 700, color: "var(--fg)" }}>{s.value}</div>
                <div style={{ fontSize: 12, color: "var(--muted)", marginTop: 2 }}>{s.label}</div>
              </div>
            </Card>
          ))}
        </div>

        {/* Filter bar */}
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 20 }}>
          <div style={{ display: "flex", gap: 4 }}>
            {["All", "Active", "Revoked"].map(f => (
              <button key={f} onClick={() => setFilter(f)} style={{
                background: filter === f ? "var(--bg-subtle)" : "transparent",
                border: "1px solid", borderColor: filter === f ? "var(--line)" : "transparent",
                color: filter === f ? "var(--fg)" : "var(--muted)",
                padding: "6px 14px", borderRadius: 6, cursor: "pointer", fontSize: 13,
                fontWeight: filter === f ? 600 : 400,
              }}>{f}</button>
            ))}
          </div>
          <div style={{ position: "relative" }}>
            <I.Search size={13} style={{ position: "absolute", left: 10, top: "50%", transform: "translateY(-50%)", color: "var(--muted)" }} />
            <input value={search} onChange={e => setSearch(e.target.value)} placeholder="Search agents…"
              style={{ padding: "7px 12px 7px 30px", borderRadius: 6, border: "1px solid var(--line)", background: "var(--bg)", color: "var(--fg)", fontSize: 13, width: 200 }} />
          </div>
        </div>

        {loading ? (
          <SkeletonAgentList count={3} />
        ) : filtered.length === 0 ? (
          <div style={{ padding: 48, textAlign: "center", background: "var(--bg-subtle)", borderRadius: 10, border: "1px dashed var(--line)", color: "var(--muted)" }}>
            <I.Bot size={36} style={{ marginBottom: 12, opacity: 0.3 }} />
            <div style={{ fontSize: 16, fontWeight: 500, marginBottom: 4 }}>No agents registered.</div>
            <div style={{ fontSize: 13, marginBottom: 20 }}>Register your first agent to automate engineering work.</div>
          </div>
        ) : (
          <div style={{ display: "flex", flexDirection: "column", gap: 28 }}>

            {/* ACTIVE NOW */}
            {runningAgents.length > 0 && (
              <section>
                <div style={{ fontSize: 11, fontWeight: 700, letterSpacing: "1.2px", textTransform: "uppercase", color: "var(--muted)", marginBottom: 12 }}>
                  Active Now
                </div>
                <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
                  {runningAgents.map(agent => {
                    const runningTask = (agentTasks[agent.id] || []).find(t => t.status === "in_progress");
                    return (
                      <AgentRunningCard
                        key={agent.id}
                        agent={agent}
                        task={runningTask}
                        onClick={() => router.push(`/repositories/${repoName}/agents/${agent.id}`)}
                        onTerminateTask={handleTerminateTask}
                      />
                    );
                  })}
                </div>
              </section>
            )}

            {/* ALL AGENTS table */}
            <section>
              <div style={{ fontSize: 11, fontWeight: 700, letterSpacing: "1.2px", textTransform: "uppercase", color: "var(--muted)", marginBottom: 12 }}>
                All Agents
              </div>
              <Card style={{ padding: 0, overflow: "hidden" }}>
                {filtered.map((agent, idx) => {
                  const tasks = agentTasks[agent.id] || [];
                  const runningTask = tasks.find(t => t.status === "in_progress");
                  const completedTasks = tasks.filter(t => t.status === "completed").length;
                  const isActive = agent.is_active && agent.status === "active";

                  return (
                    <div
                      key={agent.id}
                      onClick={() => router.push(`/repositories/${repoName}/agents/${agent.id}`)}
                      style={{
                        display: "flex", alignItems: "center", gap: 16, padding: "14px 20px",
                        borderBottom: idx < filtered.length - 1 ? "1px solid var(--line)" : "none",
                        cursor: "pointer", transition: "background 0.15s",
                      }}
                      onMouseEnter={e => (e.currentTarget.style.background = "var(--bg-subtle)")}
                      onMouseLeave={e => (e.currentTarget.style.background = "transparent")}
                    >
                      {/* Avatar + status dot */}
                      <div style={{ position: "relative", flexShrink: 0 }}>
                        <div style={{ width: 36, height: 36, borderRadius: "50%", background: isActive ? "var(--accent-subtle)" : "var(--bg-subtle)", border: `1px solid ${isActive ? "var(--border-accent)" : "var(--line)"}`, display: "flex", alignItems: "center", justifyContent: "center" }}>
                          <I.Cpu size={16} color={isActive ? "var(--accent)" : "var(--muted)"} />
                        </div>
                        {isActive && (
                          <div style={{ position: "absolute", bottom: 1, right: 1, width: 8, height: 8, borderRadius: "50%", background: "#10b981", border: "2px solid var(--bg)" }} />
                        )}
                      </div>

                      {/* Name + description */}
                      <div style={{ flex: 1, minWidth: 0 }}>
                        <div style={{ fontSize: 14, fontWeight: 600, color: "var(--fg)" }}>{agent.name}</div>
                        <div style={{ fontSize: 12, color: "var(--muted)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                          {runningTask ? `▶ ${runningTask.title}` : (agent.description || "No active task")}
                        </div>
                      </div>

                      {/* Provider badge */}
                      {agent.provider && (
                        <div style={{ fontSize: 11, padding: "3px 8px", borderRadius: 4, background: "var(--bg-subtle)", border: "1px solid var(--line)", color: "var(--muted)", fontFamily: "monospace", flexShrink: 0 }}>
                          {agent.provider}{agent.model ? ` / ${agent.model}` : ""}
                        </div>
                      )}

                      {/* Status pill + optional terminate */}
                      <div style={{ display: "flex", alignItems: "center", gap: 8, minWidth: 80, justifyContent: "flex-end", flexShrink: 0 }}>
                        <div style={{ display: "flex", alignItems: "center", gap: 5 }}>
                          <div style={{ width: 7, height: 7, borderRadius: "50%", background: runningTask ? "#10b981" : statusColor(agent.status) }} />
                          <span style={{ fontSize: 12, color: "var(--muted)", fontWeight: 500 }}>
                            {runningTask ? "Running" : statusLabel(agent)}
                          </span>
                        </div>
                      </div>

                      {/* Task count */}
                      <div style={{ fontSize: 12, color: "var(--muted)", minWidth: 72, textAlign: "right", flexShrink: 0 }}>
                        {tasks.length > 0 ? `${completedTasks} / ${tasks.length} done` : "—"}
                      </div>

                      <I.ChevronRight size={14} color="var(--muted)" />
                    </div>
                  );
                })}
              </Card>
            </section>
          </div>
        )}
      </div>

      <style>{`
        @keyframes pulse-ring {
          0% { transform: scale(1); opacity: 0.7; }
          100% { transform: scale(2.5); opacity: 0; }
        }
      `}</style>
      <ConfirmModal
        isOpen={Boolean(taskToTerminate)}
        onClose={() => setTaskToTerminate(null)}
        onConfirm={executeTerminateTask}
        title="Terminate Agent Task"
        description={
          <>
            Are you sure you want to terminate <strong>&ldquo;{taskToTerminate?.title}&rdquo;</strong>? Active execution will be cancelled immediately.
          </>
        }
        confirmText="Terminate Task"
        confirmTone="danger"
        loading={terminating}
      />
    </AppShell>
  );
}