"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { Plus, Filter, Bot, UserRound, CheckCircle2, Clock, AlertCircle, Search, RefreshCw } from "lucide-react";
import { Page, Card, Badge, EmptyState, Table, Btn, SutraLoading } from "@/components/ui";
import { taskService, Task } from "@/lib/tasks";

export default function Tasks() {
  const [tasks, setTasks] = useState<Task[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState<string>("all");
  const [search, setSearch] = useState<string>("");

  const loadTasks = () => {
    setLoading(true);
    setError(null);
    taskService.listAllTasks()
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
    loadTasks();
  }, []);

  const filteredTasks = useMemo(() => {
    return tasks.filter((t) => {
      const matchesSearch = !search || 
        t.title.toLowerCase().includes(search.toLowerCase()) ||
        (t.description && t.description.toLowerCase().includes(search.toLowerCase())) ||
        (t.repository_id && t.repository_id.toLowerCase().includes(search.toLowerCase()));
      
      if (!matchesSearch) return false;
      if (statusFilter === "all") return true;
      if (statusFilter === "active") return t.status !== "completed" && t.status !== "cancelled" && t.status !== "done";
      if (statusFilter === "completed") return t.status === "completed" || t.status === "done";
      if (statusFilter === "agent") return Boolean(t.assigned_agent_id);
      return t.status === statusFilter;
    });
  }, [tasks, statusFilter, search]);

  const activeCount = tasks.filter(t => t.status !== "completed" && t.status !== "cancelled" && t.status !== "done").length;
  const completedCount = tasks.filter(t => t.status === "completed" || t.status === "done").length;
  const agentCount = tasks.filter(t => Boolean(t.assigned_agent_id)).length;

  return (
    <Page 
      eyebrow="Engineering Control Plane" 
      title="Tasks" 
      description="Intent becomes executable work. Tasks can be dispatched to agents or humans under sovereign governance."
      actions={
        <Btn onClick={loadTasks} disabled={loading}>
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
            <div className="num" style={{ color: "var(--blue-hover)" }}>{activeCount}</div>
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
          <SutraLoading message="Querying tasks across monitored repositories..." quote={true} />
        ) : error ? (
          <div style={{ padding: "32px 20px" }}>
            <div className="error-banner">
              <AlertCircle size={16} />
              <span>{error}</span>
            </div>
          </div>
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
                    <Link 
                      href={`/tasks/${task.id}`}
                      style={{ fontWeight: 600, color: "var(--text-primary)", textDecoration: "none" }}
                    >
                      {task.title}
                    </Link>
                    {task.description && (
                      <div style={{ fontSize: "11px", color: "var(--muted)", marginTop: "2px", maxWidth: "440px", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                        {task.description}
                      </div>
                    )}
                  </td>
                  <td>
                    <span style={{ fontSize: "12px", fontFamily: "var(--font-mono, monospace)", color: "var(--text-secondary)" }}>
                      {task.repository_id ? task.repository_id.slice(0, 10) : "—"}
                    </span>
                  </td>
                  <td>
                    {task.assigned_agent_id ? (
                      <span className="badge indigo">
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
                    <Badge tone={task.status === "completed" || task.status === "done" ? "green" : task.status === "in_progress" ? "blue" : "amber"}>
                      {task.status}
                    </Badge>
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
  );
}