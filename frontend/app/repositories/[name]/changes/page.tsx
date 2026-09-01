"use client";

import { use, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { AppShell, PageHead, Card, Btn, Badge } from "@/components/shell";
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

      <div style={{ maxWidth: 1000, margin: "0 auto", padding: "0 20px" }}>
        
        {/* Filters and Stats Row */}
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
          <div style={{ display: "flex", gap: 8 }}>
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
          <div style={{ display: "flex", gap: 12 }}>
            <div style={{ position: "relative" }}>
              <I.Search size={14} style={{ position: "absolute", left: 10, top: "50%", transform: "translateY(-50%)", color: "var(--muted)" }} />
              <input type="text" placeholder="Search changes..." style={{ padding: "6px 10px 6px 30px", borderRadius: 6, border: "1px solid var(--line)", background: "var(--bg)", color: "var(--fg)", fontSize: 14 }} />
            </div>
            <Btn>Filter <I.Filter size={14} style={{ marginLeft: 6 }} /></Btn>
          </div>
        </div>

        <div style={{ display: "flex", gap: 24, fontSize: 14, color: "var(--muted)", marginBottom: 24, padding: "12px 16px", background: "var(--bg-subtle)", borderRadius: 8, border: "1px solid var(--line)" }}>
          <div><strong style={{ color: "var(--fg)" }}>{stats.open}</strong> Open Changes</div>
          <div><strong style={{ color: "var(--fg)" }}>{stats.needsReview}</strong> Needs Review</div>
          <div><strong style={{ color: "var(--fg)" }}>{stats.agentChanges}</strong> Agent Changes</div>
          <div><strong style={{ color: "var(--fg)" }}>{stats.recorded}</strong> Recorded</div>
        </div>

        {/* Changes List */}
        {loading ? (
           <div style={{ padding: 40, textAlign: "center", color: "var(--muted)" }}>Loading changes...</div>
        ) : filteredChanges.length === 0 ? (
           <div style={{ padding: 40, textAlign: "center", color: "var(--muted)", background: "var(--bg-subtle)", borderRadius: 8, border: "1px solid var(--line)" }}>
             No changes found.
           </div>
        ) : (
          <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
            {filteredChanges.map(change => (
              <div key={change.id} onClick={() => router.push(`/repositories/${repoId}/changes/${change.id}`)} style={{ cursor: "pointer" }}>
                <Card style={{ padding: 24, transition: "border-color 0.2s" }}>
                  

                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 16 }}>
                  <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
                    <div style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 12, fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.5px", color: statusColors[change.status] || "var(--fg)" }}>
                      <div style={{ width: 8, height: 8, borderRadius: "50%", background: statusColors[change.status] || "var(--fg)" }} />
                      {statusLabels[change.status] || change.status.replace('_', ' ')}
                    </div>
                    <div style={{ fontSize: 13, color: "var(--muted)" }}>
                      {new Date(change.updated_at).toLocaleDateString()}
                    </div>
                  </div>
                </div>

                <div style={{ marginBottom: 16 }}>
                  <div style={{ fontSize: 20, fontWeight: 600, color: "var(--fg)", marginBottom: 8 }}>{change.title || "Untitled Change"}</div>
                  <div style={{ fontSize: 14, color: "var(--muted)" }}>{change.description || change.intent}</div>
                </div>

                <div style={{ display: "flex", gap: 40, marginBottom: 24 }}>
                  {change.task_id && (
                    <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                      <div style={{ fontSize: 12, color: "var(--muted)", fontWeight: 600, textTransform: "uppercase" }}>Task</div>
                      <div style={{ fontSize: 14, color: "var(--fg)", display: "flex", alignItems: "center", gap: 6 }}>
                        <I.CheckSquare size={14} color="var(--cyan)" /> #{change.task_id.split('-').pop()?.slice(0,6) || change.task_id.slice(0,6)}
                      </div>
                    </div>
                  )}
                  {change.task_id && change.actor_type === "agent" && (
                    <div style={{ display: "flex", alignItems: "center", color: "var(--line)" }}>
                      <I.ArrowRight size={16} />
                    </div>
                  )}
                  <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                    <div style={{ fontSize: 12, color: "var(--muted)", fontWeight: 600, textTransform: "uppercase" }}>
                      {change.actor_type === "agent" ? "Agent" : "Author"}
                    </div>
                    <div style={{ fontSize: 14, color: "var(--fg)", display: "flex", alignItems: "center", gap: 6 }}>
                      {change.actor_type === "agent" ? <I.Bot size={14} color="var(--purple)" /> : <I.User size={14} color="var(--cyan)" />}
                      {change.actor_name || "Unknown"}
                    </div>
                  </div>
                  {change.actor_type === "agent" && (
                    <div style={{ display: "flex", alignItems: "center", color: "var(--line)" }}>
                      <I.ArrowRight size={16} />
                    </div>
                  )}
                  <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                    <div style={{ fontSize: 12, color: "var(--muted)", fontWeight: 600, textTransform: "uppercase" }}>Change</div>
                    <div style={{ fontSize: 14, color: "var(--fg)", display: "flex", alignItems: "center", gap: 6 }}>
                      <I.GitCommit size={14} color="var(--green)" /> #{change.id.split('-').pop()?.slice(0,6) || change.id.slice(0,6)}
                    </div>
                  </div>
                </div>

                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", borderTop: "1px solid var(--line)", paddingTop: 16 }}>
                  <div style={{ display: "flex", alignItems: "center", gap: 16, fontSize: 13, color: "var(--muted)" }}>
                    <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                      <span style={{ color: "var(--green)" }}>+{change.additions || 0}</span>
                      <span style={{ color: "var(--red)" }}>−{change.deletions || 0}</span>
                      <span>{change.files_changed || 0} files changed</span>
                    </div>
                  </div>

                  <div style={{ display: "flex", gap: 16, fontSize: 13, color: "var(--fg)" }}>
                    {change.checks && change.checks.map(c => (
                      <div key={c.name} style={{ display: "flex", alignItems: "center", gap: 6 }}>
                        {c.status === "passed" ? <I.Check size={14} color="var(--green)" /> : 
                         c.status === "running" ? <I.Loader size={14} color="var(--cyan)" /> : 
                         <I.X size={14} color="var(--red)" />}
                        {c.name}
                      </div>
                    ))}
                    {change.reviews && change.reviews.length > 0 && (
                      <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                        {change.reviews.every(r => r.status === "approved") ? 
                          <I.Check size={14} color="var(--green)" /> : 
                          <I.CheckCircle2 size={14} color="var(--yellow)" />}
                        Review {change.reviews.filter(r => r.status === "approved").length}/{change.reviews.length}
                      </div>
                    )}
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