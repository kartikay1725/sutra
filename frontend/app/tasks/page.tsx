"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Plus, Filter, Bot, UserRound, CheckCircle2, Clock, AlertCircle } from "lucide-react";
import { Page, Card, Badge } from "@/components/ui";
import { taskService, Task } from "@/lib/tasks";

export default function Tasks() {
  const [tasks, setTasks] = useState<Task[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    taskService.listAllTasks()
      .then((data) => {
        setTasks(Array.isArray(data) ? data : []);
        setLoading(false);
      })
      .catch((err) => {
        setError(err.message || "Failed to load tasks");
        setLoading(false);
      });
  }, []);

  const activeCount = tasks.filter(t => t.status !== "completed" && t.status !== "cancelled").length;

  return (
    <Page 
      eyebrow="Engineering" 
      title="Tasks" 
      description="Intent becomes executable work. Tasks can be assigned to humans or external agents under sovereign governance."
    >
      <Card>
        <div className="sectionhead">
          <div className="topactions">
            <span style={{ fontSize: "13px", fontWeight: 600 }}>All Monitored Tasks</span>
          </div>
          <span className="muted">{activeCount} active</span>
        </div>
        {loading ? (
          <div style={{ padding: "40px", textAlign: "center" }} className="muted">
            Loading tasks...
          </div>
        ) : error ? (
          <div style={{ padding: "40px", textAlign: "center", color: "#f87171" }}>
            <AlertCircle size={20} style={{ margin: "0 auto 8px" }} />
            {error}
          </div>
        ) : tasks.length === 0 ? (
          <div style={{ padding: "40px", textAlign: "center" }} className="muted">
            No tasks found across your repositories. Create a task in any repository to begin execution.
          </div>
        ) : (
          <table className="table">
            <thead>
              <tr>
                <th>Task</th>
                <th>Repository</th>
                <th>Assignee</th>
                <th>Status</th>
                <th>Created</th>
              </tr>
            </thead>
            <tbody>
              {tasks.map((task) => (
                <tr key={task.id}>
                  <td>
                    <Link 
                      href={`/tasks/${task.id}`}
                      style={{ fontWeight: 600, color: "var(--accent, #60a5fa)", textDecoration: "none" }}
                    >
                      {task.title}
                    </Link>
                    {task.description && (
                      <div style={{ fontSize: "11px", color: "var(--muted, #94a3b8)", marginTop: "2px", maxWidth: "350px", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                        {task.description}
                      </div>
                    )}
                  </td>
                  <td style={{ fontSize: "12px", fontFamily: "monospace" }}>
                    {task.repository_id ? task.repository_id.slice(0, 8) : "—"}
                  </td>
                  <td>
                    {task.assigned_agent_id ? (
                      <span style={{ display: "inline-flex", alignItems: "center", gap: "4px", fontSize: "12px" }}>
                        <Bot size={13} color="#a78bfa" /> Agent
                      </span>
                    ) : task.assignee_id ? (
                      <span style={{ display: "inline-flex", alignItems: "center", gap: "4px", fontSize: "12px" }}>
                        <UserRound size={13} color="#60a5fa" /> User
                      </span>
                    ) : (
                      <span className="muted" style={{ fontSize: "12px" }}>Unassigned</span>
                    )}
                  </td>
                  <td>
                    <Badge tone={task.status === "completed" ? "green" : task.status === "in_progress" ? "amber" : "neutral"}>
                      {task.status}
                    </Badge>
                  </td>
                  <td style={{ fontSize: "11px" }} className="muted">
                    {task.created_at ? new Date(task.created_at).toLocaleDateString() : "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>
    </Page>
  );
}