"use client";

import { use, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { AppShell, PageHead, Card, Btn, Badge, EmptyState, SkeletonChangeList } from "@/components/shell";
import { changeService, Change } from "@/lib/changes";
import { authService } from "@/lib/auth";
import * as I from "lucide-react";

export default function ChangesListPage({ params }: { params: Promise<{ name: string }> }) {
  const { name: repoId } = use(params);
  const router = useRouter();
  const [changes, setChanges] = useState<Change[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState("All");

  const loadChanges = async () => {
    setLoading(true);
    try {
      const u = await authService.getCurrentUser();
      const data = await changeService.listChanges(u.username, repoId);
      setChanges(data);
    } catch (e) {
      console.error("Failed to load changes", e);
      setChanges([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadChanges();
  }, [repoId]);

  const stats = {
    open: changes.filter(c => ["proposed", "recorded"].includes(c.status)).length,
    needsReview: changes.filter(c => c.status === "proposed" || (c.reviews && c.reviews.some(r => r.status === "pending"))).length,
    agentChanges: changes.filter(c => c.actor_type === "agent").length,
    recorded: changes.filter(c => c.status === "recorded").length,
  };

  const statusColors: Record<string, string> = {
    "proposed": "var(--yellow)",
    "recorded": "var(--cyan)",
    "blocked": "var(--red)",
    "rejected": "var(--red)",
    "needs_review": "var(--yellow)",
    "approved": "var(--green)",
    "merged": "var(--purple)",
  };

  const statusLabels: Record<string, string> = {
    "proposed": "Proposed",
    "recorded": "Recorded",
    "blocked": "Blocked",
    "rejected": "Rejected",
    "needs_review": "Needs Review",
    "approved": "Approved",
    "merged": "Merged",
  };

  // Filter changes based on selected filter
  const filteredChanges = changes.filter(change => {
    if (filter === "All") return true;
    if (filter === "Open") return ["proposed", "recorded"].includes(change.status);
    if (filter === "Needs Review") return change.status === "proposed" || (change.reviews && change.reviews.some(r => r.status === "pending"));
    if (filter === "Agent Changes") return change.actor_type === "agent";
    if (filter === "My Changes") return change.actor_type === "human"; 
    return true;
  });

  return (
    <AppShell>
      <PageHead
        eyebrow={repoId}
        title="Changes"
        sub="All code changes produced by humans and agents."
      />

      <div style={{ width: "100%" }}>
        
        {/* Filters and Stats Row */}
        <div className="changes-filter-row" style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
          <div className="changes-filter-tabs" style={{ display: "flex", gap: 8 }}>
            {["All", "Open", "Needs Review", "Agent Changes", "My Changes"].map(f => (
              <button 
                key={f}
                onClick={() => setFilter(f)}
                style={{
                  background: filter === f ? "var(--bg-subtle)" : "transparent",
                  border: "1px solid",
                  borderColor: filter === f ? "var(--line)" : "transparent",
                  color: filter === f ? "var(--fg)" : "var(--muted)",
                  padding: "6px 12px",
                  borderRadius: 6,
                  cursor: "pointer",
                  fontSize: 14,
                  fontWeight: filter === f ? 600 : 400
                }}
              >
                {f}
              </button>
            ))}
          </div>
          <div className="changes-search-group" style={{ display: "flex", gap: 12 }}>
            <div style={{ position: "relative" }}>
              <I.Search size={14} style={{ position: "absolute", left: 10, top: "50%", transform: "translateY(-50%)", color: "var(--muted)" }} />
              <input type="text" placeholder="Search changes..." style={{ padding: "6px 10px 6px 30px", borderRadius: 6, border: "1px solid var(--line)", background: "var(--bg)", color: "var(--fg)", fontSize: 14 }} />
            </div>
            <Btn>Filter <I.Filter size={14} style={{ marginLeft: 6 }} /></Btn>
          </div>
        </div>

        <div className="changes-stats-row" style={{ display: "flex", gap: 24, fontSize: 14, color: "var(--muted)", marginBottom: 24, padding: "12px 16px", background: "var(--bg-subtle)", borderRadius: 8, border: "1px solid var(--line)" }}>
          <div><strong style={{ color: "var(--fg)" }}>{stats.open}</strong> Open Changes</div>
          <div><strong style={{ color: "var(--fg)" }}>{stats.needsReview}</strong> Needs Review</div>
          <div><strong style={{ color: "var(--fg)" }}>{stats.agentChanges}</strong> Agent Changes</div>
          <div><strong style={{ color: "var(--fg)" }}>{stats.recorded}</strong> Recorded</div>
        </div>

        {/* Changes List */}
        {loading ? (
           <SkeletonChangeList count={4} />
        ) : filteredChanges.length === 0 ? (
           <EmptyState
             icon={<I.GitCommit size={20} />}
             title="No changes found"
             description="No recorded or proposed changes match the selected filter."
           />
        ) : (
          <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
            {filteredChanges.map(change => (
              <div 
                key={change.id} 
                onClick={() => router.push(`/repositories/${repoId}/changes/${change.id}`)} 
                style={{ cursor: "pointer" }}
              >
                <Card style={{ padding: "14px 18px", transition: "border-color 0.15s ease" }}>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 14 }}>
                    <div style={{ minWidth: 0, flex: 1 }}>
                      <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap", marginBottom: 4 }}>
                        <span className={`badge ${change.status === "approved" || change.status === "merged" ? "green" : change.status === "proposed" ? "amber" : "blue"}`}>
                          {statusLabels[change.status] || change.status}
                        </span>
                        <span style={{ fontSize: 13, fontWeight: 600, color: "var(--text-primary)" }}>
                          {change.title || "Untitled Change"}
                        </span>
                        <span style={{ fontSize: 11, fontFamily: "var(--font-mono, monospace)", color: "var(--muted)" }}>
                          #{change.id.slice(0, 7)}
                        </span>
                      </div>

                      {change.description && (
                        <div style={{ fontSize: 12, color: "var(--text-secondary)", marginBottom: 8, maxWidth: 640, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                          {change.description || change.intent}
                        </div>
                      )}

                      <div style={{ display: "flex", alignItems: "center", gap: 16, fontSize: 11, color: "var(--muted)", flexWrap: "wrap" }}>
                        <div style={{ display: "flex", alignItems: "center", gap: 4 }}>
                          {change.actor_type === "agent" ? (
                            <span className="badge orange">
                              <I.Bot size={10} /> {change.actor_name || "Agent"}
                            </span>
                          ) : (
                            <span className="badge blue">
                              <I.User size={10} /> {change.actor_name || "Author"}
                            </span>
                          )}
                        </div>

                        {change.task_id && (
                          <div style={{ display: "flex", alignItems: "center", gap: 4, fontFamily: "var(--font-mono, monospace)" }}>
                            <I.CheckSquare size={12} color="var(--blue-hover)" />
                            <span>task-{change.task_id.slice(0, 6)}</span>
                          </div>
                        )}

                        <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                          <span style={{ color: "var(--success)", fontWeight: 600 }}>+{change.additions || 0}</span>
                          <span style={{ color: "var(--error)", fontWeight: 600 }}>−{change.deletions || 0}</span>
                          <span>{change.files_changed || 0} {(change.files_changed === 1) ? "file" : "files"}</span>
                        </div>

                        <span>{new Date(change.updated_at).toLocaleDateString()}</span>
                      </div>
                    </div>

                    <div style={{ display: "flex", alignItems: "center", gap: 8, flexShrink: 0 }}>
                      <I.ChevronRight size={15} color="var(--muted)" />
                    </div>
                  </div>
                </Card>
              </div>
            ))}
          </div>
        )}

      </div>
    </AppShell>
  );
}