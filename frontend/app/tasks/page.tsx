"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { Plus, Filter, Bot, UserRound, CheckCircle2, Clock, Search, RefreshCw, Sparkles, GitPullRequest, Square } from "lucide-react";
import { AppShell } from "@/components/shell";
import { Page, Card, Badge, EmptyState, ErrorState, Table, Btn, Skeleton } from "@/components/ui";
import { taskService, Task } from "@/lib/tasks";
import { ConfirmModal } from "@/components/ConfirmModal";

export default function Tasks() {
  const [tasks, setTasks] = useState<Task[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState<string>("all");
  const [search, setSearch] = useState<string>("");
  const [terminatingId, setTerminatingId] = useState<string | null>(null);
  const [taskToTerminate, setTaskToTerminate] = useState<Task | null>(null);

  const handleTerminate = (task: Task) => {
    setTaskToTerminate(task);
  };

  const executeTerminate = async () => {
    if (!taskToTerminate) return;
    const taskId = taskToTerminate.id;
    setTerminatingId(taskId);
    try {
      await taskService.terminateTask(taskId);
      setTasks((prev) =>
        prev.map((t) => (t.id === taskId ? { ...t, status: "cancelled" } : t))
      );
      setTaskToTerminate(null);
    } catch (err: any) {
      alert(err?.message || "Failed to terminate task");
    } finally {
      setTerminatingId(null);
    }
  };

  const loadTasks = (query?: string) => {
    setLoading(true);
    setError(null);
    taskService.listAllTasks(query)
      .then((data) => {
        setTasks(Array.isArray(data) ? data : []);
      })
      .catch((err) => {
        setError(err.message || "Failed to load tasks");
      })
      .finally(() => {
        setLoading(false);
      });
  };

  useEffect(() => {
    const handler = setTimeout(() => {
      loadTasks(search);
    }, 250);
    return () => clearTimeout(handler);
  }, [search]);

  const filteredTasks = useMemo(() => {
    return tasks.filter((t) => {
      const matchesSearch = !search || 
        t.title.toLowerCase().includes(search.toLowerCase()) ||
        (t.description && t.description.toLowerCase().includes(search.toLowerCase())) ||
        (t.execution_summary && t.execution_summary.toLowerCase().includes(search.toLowerCase())) ||
        (t.repository_id && t.repository_id.toLowerCase().includes(search.toLowerCase()));
      
      if (!matchesSearch) return false;
      if (statusFilter === "all") return true;
      if (statusFilter === "active") return t.status !== "completed" && t.status !== "cancelled" && t.status !== "done";
      if (statusFilter === "completed") return t.status === "completed" || t.status === "done";
      if (statusFilter === "agent") return Boolean(t.assigned_agent_id) || t.source === "agent";
      if (statusFilter === "agent_created") return t.source === "agent";
      if (statusFilter === "human_created") return t.source !== "agent";
      return t.status === statusFilter;
    });
  }, [tasks, statusFilter, search]);

  const activeCount = tasks.filter(t => t.status !== "completed" && t.status !== "cancelled" && t.status !== "done").length;
  const completedCount = tasks.filter(t => t.status === "completed" || t.status === "done").length;
  const agentCount = tasks.filter(t => Boolean(t.assigned_agent_id) || t.source === "agent").length;
  const agentCreatedCount = tasks.filter(t => t.source === "agent").length;

  return (
    <AppShell>
      <Page
        eyebrow="Engineering Control Plane"
        title="Tasks"
        description="Intent becomes executable work. Tasks can be dispatched to agents or humans under sovereign governance."
        actions={
          <Btn onClick={() => loadTasks(search)} disabled={loading}>
            <RefreshCw size={13} className={loading ? "spin" : ""} /> Refresh
          </Btn>
        }
      >
      <div className="grid g4" style={{ marginBottom: 16 }}>
        <Card>
          <div className="stat">
            <div className="statlabel">Total Tasks</div>
            <div className="num">{tasks.length}</div>
          </div>
        </Card>
        <Card>
          <div className="stat">
            <div className="statlabel">Active Work</div>
            <div className="num" style={{ color: "var(--accent)" }}>{activeCount}</div>
          </div>
        </Card>
        <Card>
          <div className="stat">
            <div className="statlabel">Agent Assigned</div>
            <div className="num" style={{ color: "var(--indigo-hover)" }}>{agentCount}</div>
          </div>
        </Card>
        <Card>
          <div className="stat">
            <div className="statlabel">Completed</div>
            <div className="num" style={{ color: "var(--success)" }}>{completedCount}</div>
          </div>
        </Card>
      </div>

      <Card>
        <div className="sectionhead" style={{ flexWrap: "wrap", gap: 12 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            {[
              { id: "all", label: `All (${tasks.length})` },
              { id: "active", label: `Active (${activeCount})` },
              { id: "agent", label: `Agent (${agentCount})` },
              { id: "completed", label: `Completed (${completedCount})` },
            ].map((tab) => (
              <button
                key={tab.id}
                type="button"
                className={`btn sm ${statusFilter === tab.id ? "primary" : "outline"}`}
                onClick={() => setStatusFilter(tab.id)}
              >
                {tab.label}
              </button>
            ))}
          </div>

          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <div style={{ position: "relative" }}>
              <Search size={13} style={{ position: "absolute", left: 10, top: "50%", transform: "translateY(-50%)", color: "var(--muted)" }} />
              <input
                type="text"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Search tasks, repos..."
                style={{
                  height: 30,
                  padding: "0 10px 0 28px",
                  fontSize: 12,
                  background: "var(--surface-2)",
                  border: "1px solid var(--line)",
                  borderRadius: "var(--radius-sm)",
                  color: "var(--text-primary)",
                  width: 200,
                  outline: "none",
                }}
              />
            </div>
            <span className="meta">{filteredTasks.length} shown</span>
          </div>
        </div>

        {loading ? (
          <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
            {[1, 2, 3, 4, 5].map((i) => (
              <Card key={i} style={{ padding: "16px 20px" }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                  <div style={{ display: "flex", alignItems: "center", gap: 12, flex: 1 }}>
                    <Skeleton width={18} height={18} borderRadius={4} />
                    <div style={{ display: "flex", flexDirection: "column", gap: 6, flex: 1 }}>
                      <Skeleton width={`${40 + (i % 3) * 15}%`} height={15} borderRadius={4} />
                      <Skeleton width={130} height={12} borderRadius={3} />
                    </div>
                  </div>
                  <Skeleton width={80} height={22} borderRadius={11} />
                </div>
              </Card>
            ))}
          </div>
        ) : error ? (
          <ErrorState
            description={error}
            action={<Btn sm onClick={() => loadTasks(search)}>Try again</Btn>}
          />
        ) : filteredTasks.length === 0 ? (
          <div style={{ padding: "20px" }}>
            <EmptyState
              icon={<Clock size={18} />}
              title="No tasks match the filter"
              description={search ? `No tasks found matching "${search}".` : "No tasks found in this view. Tasks will appear when initiated across your connected repositories."}
              action={
                search ? (
                  <Btn sm onClick={() => setSearch("")}>Clear search</Btn>
                ) : null
              }
            />
          </div>
        ) : (
          <Table>
            <thead>
              <tr>
                <th style={{ width: "42%" }}>Task</th>
                <th style={{ width: "18%" }}>Repository</th>
                <th style={{ width: "16%" }}>Assignee</th>
                <th style={{ width: "12%" }}>Status</th>
                <th style={{ width: "12%", textAlign: "right" }}>Created</th>
              </tr>
            </thead>
            <tbody>
              {filteredTasks.map((task) => (
                <tr key={task.id}>
                  <td>
                    <div style={{ display: "flex", alignItems: "center", gap: "8px", flexWrap: "wrap" }}>
                      <Link 
                        href={`/tasks/${task.id}`}
                        style={{ fontWeight: 600, color: "var(--text-primary)", textDecoration: "none" }}
                      >
                        {task.title}
                      </Link>
                      {task.source === "agent" ? (
                        <span className="badge orange" style={{ fontSize: "10px", padding: "1px 6px", display: "inline-flex", alignItems: "center", gap: 3 }}>
                          <Sparkles size={10} /> Agent-created
                        </span>
                      ) : (
                        <span className="badge gray" style={{ fontSize: "10px", padding: "1px 6px" }}>
                          Human-created
                        </span>
                      )}
                    </div>
                    {task.execution_summary ? (
                      <div style={{ fontSize: "12px", color: "var(--text-secondary)", marginTop: "4px", maxWidth: "520px", display: "-webkit-box", WebkitLineClamp: 2, WebkitBoxOrient: "vertical", overflow: "hidden", lineHeight: 1.4 }}>
                        <span style={{ color: "var(--accent, #f97316)", fontWeight: 500 }}>Summary:</span> {task.execution_summary}
                      </div>
                    ) : task.description ? (
                      <div style={{ fontSize: "11px", color: "var(--muted)", marginTop: "2px", maxWidth: "440px", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                        {task.description}
                      </div>
                    ) : null}
                  </td>
                  <td>
                    <span style={{ fontSize: "12px", fontFamily: "var(--font-mono, monospace)", color: "var(--text-secondary)" }}>
                      {task.repository_id ? task.repository_id.slice(0, 10) : "—"}
                    </span>
                  </td>
                  <td>
                    {task.assigned_agent_id ? (
                      <span className="badge orange">
                        <Bot size={11} /> Agent
                      </span>
                    ) : task.assignee_id ? (
                      <span className="badge blue">
                        <UserRound size={11} /> User
                      </span>
                    ) : (
                      <span className="badge gray">Unassigned</span>
                    )}
                  </td>
                  <td>
                    <div style={{ display: "flex", alignItems: "center", gap: 6, flexWrap: "wrap" }}>
                      <Badge tone={task.status === "completed" || task.status === "done" ? "green" : task.status === "cancelled" ? "red" : task.status === "in_progress" ? "blue" : "amber"}>
                        {task.status}
                      </Badge>
                      {(task.status === "in_progress" || task.status === "assigned" || task.status === "open") && (
                        <button
                          type="button"
                          onClick={() => handleTerminate(task)}
                          disabled={terminatingId === task.id}
                          className="badge red"
                          style={{
                            cursor: "pointer",
                            padding: "2px 8px",
                            fontSize: "10px",
                            background: "rgba(239,68,68,0.12)",
                            border: "1px solid rgba(239,68,68,0.3)",
                            color: "#ef4444",
                            fontWeight: 600,
                          }}
                          title="Terminate active task"
                        >
                          <Square size={9} fill="currentColor" /> {terminatingId === task.id ? "Stopping…" : "Terminate"}
                        </button>
                      )}
                    </div>
                  </td>
                  <td style={{ fontSize: "11px", textAlign: "right" }} className="meta">
                    {task.created_at ? new Date(task.created_at).toLocaleDateString() : "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </Table>
        )}
      </Card>
      </Page>

      <ConfirmModal
        isOpen={Boolean(taskToTerminate)}
        onClose={() => setTaskToTerminate(null)}
        onConfirm={executeTerminate}
        title="Terminate Task"
        description={
          <>
            Are you sure you want to terminate <strong>&ldquo;{taskToTerminate?.title}&rdquo;</strong>? The task execution will be aborted immediately and set to cancelled.
          </>
        }
        confirmText="Terminate Task"
        confirmTone="danger"
        loading={Boolean(terminatingId)}
      />
    </AppShell>
  );
}