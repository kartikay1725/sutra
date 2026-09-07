"use client";

import { useEffect, useState } from "react";
import { AppShell, PageHead, Card, Btn, Badge } from "@/components/shell";
import { activityService, ActivityEntry } from "@/lib/activity";
import * as I from "lucide-react";

export default function AuditLogPage() {
  const [logs, setLogs] = useState<ActivityEntry[]>([]);
  const [loading, setLoading] = useState(true);

  async function loadLogs() {
    setLoading(true);
    try {
      const res = await activityService.getAuditLogs(100);
      setLogs(res.items || []);
    } catch (err) {
      console.error("Failed to load audit logs:", err);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void loadLogs();
  }, []);

  const exportCSV = () => {
    if (logs.length === 0) return;
    const headers = ["Timestamp", "Actor Type", "Actor Name", "Actor ID", "Action", "Resource Type", "Resource ID", "Repository"];
    const rows = logs.map((l) => [
      l.timestamp,
      l.actor.type,
      l.actor.name,
      l.actor.id,
      l.action,
      l.resource_type,
      l.resource_id,
      l.repository || "",
    ]);
    const csvContent = [headers.join(","), ...rows.map((r) => r.map((c) => `"${String(c).replace(/"/g, '""')}"`).join(","))].join("\n");
    const blob = new Blob([csvContent], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.setAttribute("href", url);
    link.setAttribute("download", `sutra-audit-log-${new Date().toISOString().slice(0, 10)}.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  return (
    <AppShell>
      <div style={{ maxWidth: 1100, margin: "0 auto", padding: "28px 24px" }}>
        <PageHead
          eyebrow="Enterprise Compliance"
          title="Audit Log"
          sub="An immutable record of sensitive engineering actions, human approvals, agent sessions, and governance evaluations."
          action={
            <div style={{ display: "flex", gap: 10 }}>
              <Btn onClick={exportCSV} disabled={logs.length === 0}>
                <I.Download size={14} style={{ marginRight: 6 }} />
                Export CSV
              </Btn>
              <Btn onClick={loadLogs} disabled={loading}>
                <I.RefreshCw size={14} className={loading ? "animate-spin" : ""} style={{ marginRight: 6 }} />
                Refresh
              </Btn>
            </div>
          }
        />

        <Card>
          {loading ? (
            <div style={{ padding: 48, textAlign: "center", color: "var(--muted, #888)" }}>
              <I.Loader2 className="animate-spin" size={24} style={{ margin: "0 auto 12px auto" }} />
              Loading audit records...
            </div>
          ) : logs.length === 0 ? (
            <div style={{ padding: 48, textAlign: "center", color: "var(--muted, #888)" }}>
              <I.ShieldCheck size={32} style={{ margin: "0 auto 12px auto", opacity: 0.5 }} />
              No audit logs recorded yet.
            </div>
          ) : (
            <div style={{ overflowX: "auto" }}>
              <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13, textAlign: "left" }}>
                <thead>
                  <tr style={{ borderBottom: "1px solid rgba(255,255,255,0.1)", color: "var(--muted, #94a3b8)" }}>
                    <th style={{ padding: "12px 16px" }}>Time</th>
                    <th style={{ padding: "12px 16px" }}>Actor</th>
                    <th style={{ padding: "12px 16px" }}>Action</th>
                    <th style={{ padding: "12px 16px" }}>Resource</th>
                    <th style={{ padding: "12px 16px" }}>Repository</th>
                  </tr>
                </thead>
                <tbody>
                  {logs.map((item, idx) => (
                    <tr
                      key={item.id || idx}
                      style={{
                        borderBottom: "1px solid rgba(255,255,255,0.04)",
                        transition: "background 0.15s ease",
                      }}
                    >
                      <td style={{ padding: "12px 16px", color: "var(--muted, #94a3b8)", whiteSpace: "nowrap" }}>
                        {new Date(item.timestamp).toLocaleString()}
                      </td>
                      <td style={{ padding: "12px 16px" }}>
                        <span
                          style={{
                            display: "inline-flex",
                            alignItems: "center",
                            gap: 4,
                            padding: "2px 8px",
                            borderRadius: 6,
                            fontSize: 11,
                            fontWeight: 600,
                            background:
                              item.actor.type === "agent"
                                ? "rgba(139, 92, 246, 0.15)"
                                : item.actor.type === "system"
                                ? "rgba(100, 116, 139, 0.15)"
                                : "rgba(34, 197, 94, 0.15)",
                            color:
                              item.actor.type === "agent"
                                ? "#a78bfa"
                                : item.actor.type === "system"
                                ? "#94a3b8"
                                : "#4ade80",
                            border: `1px solid ${
                              item.actor.type === "agent"
                                ? "rgba(139, 92, 246, 0.3)"
                                : item.actor.type === "system"
                                ? "rgba(100, 116, 139, 0.3)"
                                : "rgba(34, 197, 94, 0.3)"
                            }`,
                          }}
                        >
                          {item.actor.type === "agent" ? <I.Bot size={11} /> : <I.User size={11} />}
                          {item.actor.name || item.actor.type}
                        </span>
                      </td>
                      <td style={{ padding: "12px 16px", fontWeight: 500 }}>{item.action}</td>
                      <td style={{ padding: "12px 16px", fontFamily: "monospace", fontSize: 12, color: "#cbd5e1" }}>
                        {item.resource_type}:{item.resource_id.slice(0, 8)}
                      </td>
                      <td style={{ padding: "12px 16px", color: "var(--muted, #94a3b8)" }}>
                        {item.repository || "—"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Card>
      </div>
    </AppShell>
  );
}
