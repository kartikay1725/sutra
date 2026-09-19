"use client";

import { useEffect, useState } from "react";
import { AppShell, PageHead, Card, Btn, Badge, EmptyState, Table, Skeleton } from "@/components/shell";
import { activityService, ActivityEntry } from "@/lib/activity";
import * as I from "lucide-react";

export default function AuditLogPage() {
  const [logs, setLogs] = useState<ActivityEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);
  const PAGE_SIZE = 10;

  async function loadLogs() {
    setLoading(true);
    try {
      const res = await activityService.getAuditLogs(100);
      setLogs(res.items || []);
      setPage(1);
    } catch (err) {
      console.error("Failed to load audit logs:", err);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void loadLogs();
  }, []);

  const totalPages = Math.max(1, Math.ceil(logs.length / PAGE_SIZE));
  const safePage = Math.min(page, totalPages);
  const paginatedLogs = logs.slice((safePage - 1) * PAGE_SIZE, safePage * PAGE_SIZE);

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
            <div style={{ padding: "16px 20px", display: "flex", flexDirection: "column", gap: 12 }}>
              {[1, 2, 3, 4, 5].map((i) => (
                <div key={i} style={{ display: "flex", alignItems: "center", justifyContent: "space-between", paddingBottom: 10, borderBottom: i < 5 ? "1px solid var(--line)" : "none" }}>
                  <div style={{ display: "flex", alignItems: "center", gap: 12, flex: 1 }}>
                    <Skeleton width={16} height={16} borderRadius="50%" />
                    <Skeleton width={`${40 + (i % 3) * 15}%`} height={14} borderRadius={4} />
                  </div>
                  <Skeleton width={80} height={12} borderRadius={3} />
                </div>
              ))}
            </div>
          ) : logs.length === 0 ? (
            <div style={{ padding: 24 }}>
              <EmptyState
                icon={<I.ShieldCheck size={20} />}
                title="No audit logs recorded yet"
                description="Engineering operations, approvals, and automated agent decisions will be tracked here immutably."
              />
            </div>
          ) : (
            <>
              <Table>
                <thead>
                  <tr>
                    <th style={{ width: "22%" }}>Time</th>
                    <th style={{ width: "18%" }}>Actor</th>
                    <th style={{ width: "24%" }}>Action</th>
                    <th style={{ width: "20%" }}>Resource</th>
                    <th style={{ width: "16%" }}>Repository</th>
                  </tr>
                </thead>
                <tbody>
                  {paginatedLogs.map((item, idx) => (
                    <tr key={item.id || idx}>
                      <td style={{ fontSize: "11px", whiteSpace: "nowrap" }} className="meta">
                        {new Date(item.timestamp).toLocaleString()}
                      </td>
                      <td>
                        <span className={`badge ${item.actor.type === "agent" ? "orange" : item.actor.type === "system" ? "gray" : "green"}`}>
                          {item.actor.type === "agent" ? <I.Bot size={11} /> : <I.User size={11} />}
                          {item.actor.name || item.actor.type}
                        </span>
                      </td>
                      <td style={{ fontWeight: 500 }}>{item.action}</td>
                      <td>
                        <span style={{ fontFamily: "var(--font-mono, monospace)", fontSize: "11px", color: "var(--text-secondary)" }}>
                          {item.resource_type}:{item.resource_id.slice(0, 8)}
                        </span>
                      </td>
                      <td style={{ color: "var(--text-secondary)", fontSize: "12px" }}>
                        {item.repository || "—"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </Table>

              {logs.length > PAGE_SIZE && (
                <div
                  style={{
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "space-between",
                    padding: "12px 16px",
                    borderTop: "1px solid var(--line)",
                    background: "rgba(255, 255, 255, 0.015)",
                  }}
                >
                  <div className="meta" style={{ fontSize: 12 }}>
                    Showing {(safePage - 1) * PAGE_SIZE + 1}–{Math.min(safePage * PAGE_SIZE, logs.length)} of {logs.length} entries
                  </div>
                  <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                    <Btn
                      disabled={safePage <= 1}
                      onClick={() => setPage((p) => Math.max(1, p - 1))}
                      style={{ padding: "4px 10px", fontSize: 12 }}
                    >
                      Previous
                    </Btn>
                    <span style={{ fontSize: 12, color: "var(--muted)", minWidth: 48, textAlign: "center" }}>
                      {safePage} / {totalPages}
                    </span>
                    <Btn
                      disabled={safePage >= totalPages}
                      onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                      style={{ padding: "4px 10px", fontSize: 12 }}
                    >
                      Next
                    </Btn>
                  </div>
                </div>
              )}
            </>
          )}
        </Card>
      </div>
    </AppShell>
  );
}
