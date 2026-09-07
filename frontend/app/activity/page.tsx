"use client";

import { useEffect, useState } from "react";
import { AppShell, PageHead, Card, Btn, Badge } from "@/components/shell";
import { activityService, ActivityEntry } from "@/lib/activity";
import { repositoriesService, Repository } from "@/lib/repositories";
import * as I from "lucide-react";
import Link from "next/link";

export default function ActivityPage() {
  const [entries, setEntries] = useState<ActivityEntry[]>([]);
  const [repositories, setRepositories] = useState<Repository[]>([]);
  const [selectedRepo, setSelectedRepo] = useState<string>("all");
  const [actorFilter, setActorFilter] = useState<string>("all");
  const [loading, setLoading] = useState(true);

  async function loadData() {
    setLoading(true);
    try {
      const [actRes, repos] = await Promise.all([
        activityService.getGlobalActivity(100),
        repositoriesService.list().catch(() => []),
      ]);
      setEntries(actRes.items || []);
      setRepositories(repos || []);
    } catch (err) {
      console.error("Failed to load activity:", err);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void loadData();
  }, []);

  const filteredEntries = entries.filter((e) => {
    if (selectedRepo !== "all") {
      if (!e.repository || !e.repository.toLowerCase().includes(selectedRepo.toLowerCase())) {
        return false;
      }
    }
    if (actorFilter !== "all") {
      if (e.actor.type !== actorFilter) {
        return false;
      }
    }
    return true;
  });

  const getActorBadge = (actor: ActivityEntry["actor"]) => {
    if (actor.type === "agent") {
      return (
        <span
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: 4,
            padding: "2px 8px",
            borderRadius: 6,
            fontSize: 11,
            fontWeight: 600,
            background: "rgba(139, 92, 246, 0.15)",
            color: "#a78bfa",
            border: "1px solid rgba(139, 92, 246, 0.3)",
          }}
        >
          <I.Bot size={12} />
          {actor.name || "Agent"}
        </span>
      );
    }
    if (actor.type === "system") {
      return (
        <span
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: 4,
            padding: "2px 8px",
            borderRadius: 6,
            fontSize: 11,
            fontWeight: 600,
            background: "rgba(100, 116, 139, 0.15)",
            color: "#94a3b8",
            border: "1px solid rgba(100, 116, 139, 0.3)",
          }}
        >
          <I.Cpu size={12} />
          {actor.name || "System"}
        </span>
      );
    }
    return (
      <span
        style={{
          display: "inline-flex",
          alignItems: "center",
          gap: 4,
          padding: "2px 8px",
          borderRadius: 6,
          fontSize: 11,
          fontWeight: 600,
          background: "rgba(34, 197, 94, 0.15)",
          color: "#4ade80",
          border: "1px solid rgba(34, 197, 94, 0.3)",
        }}
      >
        <I.User size={12} />
        {actor.name || "Human"}
      </span>
    );
  };

  const getCategoryIcon = (category: string) => {
    switch (category) {
      case "change":
        return <I.FileCode2 size={15} style={{ color: "#38bdf8" }} />;
      case "task":
        return <I.CheckSquare size={15} style={{ color: "#a855f7" }} />;
      case "pull_request":
        return <I.GitPullRequest size={15} style={{ color: "#22c55e" }} />;
      case "git":
        return <I.GitCommit size={15} style={{ color: "#f59e0b" }} />;
      case "discussion":
        return <I.MessageSquare size={15} style={{ color: "#ec4899" }} />;
      default:
        return <I.Activity size={15} style={{ color: "#94a3b8" }} />;
    }
  };

  return (
    <AppShell>
      <div style={{ maxWidth: 1100, margin: "0 auto", padding: "28px 24px" }}>
        <PageHead
          eyebrow="Audit & Observability"
          title="Activity Timeline"
          sub="Unified real-time provenance timeline of human decisions, autonomous agent actions, changes, and GitHub substrate events."
          action={
            <Btn onClick={() => loadData()} disabled={loading}>
              <I.RefreshCw size={14} className={loading ? "animate-spin" : ""} style={{ marginRight: 6 }} />
              Refresh
            </Btn>
          }
        />

        <div style={{ display: "flex", gap: 12, marginBottom: 20, flexWrap: "wrap", alignItems: "center" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <span style={{ fontSize: 13, color: "var(--muted, #888)" }}>Repository:</span>
            <select
              value={selectedRepo}
              onChange={(e) => setSelectedRepo(e.target.value)}
              style={{
                background: "var(--surface, #1e1e24)",
                color: "inherit",
                border: "1px solid rgba(255,255,255,0.1)",
                borderRadius: 8,
                padding: "6px 12px",
                fontSize: 13,
              }}
            >
              <option value="all">All Repositories</option>
              {repositories.map((r) => (
                <option key={r.id || r.name} value={r.name}>
                  {r.name}
                </option>
              ))}
            </select>
          </div>

          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <span style={{ fontSize: 13, color: "var(--muted, #888)" }}>Actor:</span>
            <select
              value={actorFilter}
              onChange={(e) => setActorFilter(e.target.value)}
              style={{
                background: "var(--surface, #1e1e24)",
                color: "inherit",
                border: "1px solid rgba(255,255,255,0.1)",
                borderRadius: 8,
                padding: "6px 12px",
                fontSize: 13,
              }}
            >
              <option value="all">All Actors</option>
              <option value="human">Humans</option>
              <option value="agent">Agents</option>
              <option value="system">System</option>
            </select>
          </div>
        </div>

        <Card>
          {loading ? (
            <div style={{ padding: 48, textAlign: "center", color: "var(--muted, #888)" }}>
              <I.Loader2 className="animate-spin" size={24} style={{ margin: "0 auto 12px auto" }} />
              Loading activity timeline...
            </div>
          ) : filteredEntries.length === 0 ? (
            <div style={{ padding: 48, textAlign: "center", color: "var(--muted, #888)" }}>
              <I.Inbox size={32} style={{ margin: "0 auto 12px auto", opacity: 0.5 }} />
              No activity matching the current filters.
            </div>
          ) : (
            <div style={{ display: "flex", flexDirection: "column" }}>
              {filteredEntries.map((item, idx) => (
                <div
                  key={item.id || idx}
                  style={{
                    display: "flex",
                    alignItems: "flex-start",
                    gap: 16,
                    padding: "16px 20px",
                    borderBottom: idx < filteredEntries.length - 1 ? "1px solid rgba(255,255,255,0.06)" : "none",
                    transition: "background 0.15s ease",
                  }}
                >
                  <div
                    style={{
                      width: 32,
                      height: 32,
                      borderRadius: 8,
                      background: "rgba(255,255,255,0.04)",
                      border: "1px solid rgba(255,255,255,0.08)",
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      flexShrink: 0,
                      marginTop: 2,
                    }}
                  >
                    {getCategoryIcon(item.category)}
                  </div>

                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap", marginBottom: 4 }}>
                      <span style={{ fontWeight: 600, fontSize: 14 }}>{item.action}</span>
                      {getActorBadge(item.actor)}
                      {item.repository && (
                        <span
                          style={{
                            fontSize: 12,
                            color: "var(--muted, #94a3b8)",
                            background: "rgba(255,255,255,0.05)",
                            padding: "1px 6px",
                            borderRadius: 4,
                          }}
                        >
                          {item.repository}
                        </span>
                      )}
                    </div>

                    <div style={{ display: "flex", alignItems: "center", gap: 12, fontSize: 12, color: "var(--muted, #888)" }}>
                      <span>
                        Resource: <code style={{ color: "#cbd5e1" }}>{item.resource_type}:{item.resource_id.slice(0, 8)}</code>
                      </span>
                      {item.metadata?.title && (
                        <span style={{ color: "#e2e8f0" }}>• {item.metadata.title}</span>
                      )}
                      {item.metadata?.branch && (
                        <span style={{ color: "#38bdf8" }}>• {item.metadata.branch}</span>
                      )}
                    </div>
                  </div>

                  <div style={{ fontSize: 12, color: "var(--muted, #888)", whiteSpace: "nowrap", flexShrink: 0 }}>
                    {new Date(item.timestamp).toLocaleString()}
                  </div>
                </div>
              ))}
            </div>
          )}
        </Card>
      </div>
    </AppShell>
  );
}