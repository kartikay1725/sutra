"use client";

import { useEffect, useState } from "react";
import { AppShell, PageHead, Card, Btn, Badge } from "@/components/shell";
import { repositoriesService, Repository } from "@/lib/repositories";
import { discussionService, Discussion } from "@/lib/discussions";
import { authService } from "@/lib/auth";
import * as I from "lucide-react";
import Link from "next/link";

export default function DiscussionsGlobalPage() {
  const [repositories, setRepositories] = useState<Repository[]>([]);
  const [selectedRepo, setSelectedRepo] = useState<string>("");
  const [discussions, setDiscussions] = useState<Discussion[]>([]);
  const [loading, setLoading] = useState(true);
  const [user, setUser] = useState<any>(null);

  useEffect(() => {
    async function load() {
      try {
        const u = await authService.getCurrentUser();
        setUser(u);
        const repos = await repositoriesService.list();
        setRepositories(repos || []);
        if (repos && repos.length > 0) {
          setSelectedRepo(repos[0].name);
          const discs = await discussionService.listDiscussions(u.username, repos[0].name);
          setDiscussions(discs || []);
        }
      } catch (e) {
        console.error("Failed to load discussions", e);
      } finally {
        setLoading(false);
      }
    }
    void load();
  }, []);

  const handleRepoChange = async (repoName: string) => {
    setSelectedRepo(repoName);
    if (!user) return;
    setLoading(true);
    try {
      const discs = await discussionService.listDiscussions(user.username, repoName);
      setDiscussions(discs || []);
    } catch (e) {
      console.error(e);
      setDiscussions([]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <AppShell>
      <div style={{ maxWidth: 1100, margin: "0 auto", padding: "28px 24px" }}>
        <PageHead
          eyebrow="Collaborative Context"
          title="Discussions"
          sub="Human discussions where agents can participate, learn context, and turn decisions into governed engineering work."
          action={
            selectedRepo ? (
              <a
                href={`https://github.com/${encodeURIComponent(user?.username || "github")}/${encodeURIComponent(selectedRepo)}/discussions`}
                target="_blank"
                rel="noopener noreferrer"
                style={{ textDecoration: "none" }}
              >
                <Btn primary>
                  <I.ExternalLink size={14} /> Open on GitHub
                </Btn>
              </a>
            ) : null
          }
        />

        {/* Repository selector */}
        {repositories.length > 0 && (
          <div style={{ margin: "20px 0", display: "flex", alignItems: "center", gap: 12 }}>
            <span style={{ fontSize: 13, color: "var(--muted)", fontWeight: 600 }}>Repository:</span>
            <select
              value={selectedRepo}
              onChange={(e) => handleRepoChange(e.target.value)}
              style={{
                padding: "8px 14px",
                borderRadius: 8,
                border: "1px solid var(--line)",
                background: "var(--bg-subtle)",
                color: "var(--fg)",
                fontSize: 14,
                cursor: "pointer",
              }}
            >
              {repositories.map((r) => (
                <option key={r.id} value={r.name} style={{ background: "var(--bg)" }}>
                  {r.name}
                </option>
              ))}
            </select>
          </div>
        )}

        {loading ? (
          <div style={{ padding: 40, textAlign: "center" }} className="muted">
            Loading discussions...
          </div>
        ) : discussions.length === 0 ? (
          <Card style={{ padding: 40, textAlign: "center" }}>
            <I.MessageSquare size={32} style={{ color: "var(--muted)", margin: "0 auto 12px", opacity: 0.6 }} />
            <div style={{ fontSize: 16, fontWeight: 600, color: "var(--fg)" }}>No discussions yet</div>
            <div style={{ fontSize: 13, color: "var(--muted)", marginTop: 4 }}>
              Start a discussion to collaborate with human engineers and autonomous SUTRA agents.
            </div>
            {selectedRepo && (
              <div style={{ marginTop: 16 }}>
                <Link href={`/repositories/${encodeURIComponent(selectedRepo)}/discussions/new`}>
                  <Btn primary>Start first discussion</Btn>
                </Link>
              </div>
            )}
          </Card>
        ) : (
          <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
            {discussions.map((d: any) => {
              const isAgent = d.author_type === "agent" || d.body?.includes("[SUTRA Agent:");
              return (
                <Link
                  key={d.id}
                  href={`/repositories/${encodeURIComponent(selectedRepo)}/discussions/${d.id}`}
                  style={{ textDecoration: "none" }}
                >
                  <Card
                    style={{
                      padding: "18px 20px",
                      display: "flex",
                      justifyContent: "space-between",
                      alignItems: "center",
                      cursor: "pointer",
                      transition: "transform .15s, border-color .15s",
                    }}
                  >
                    <div>
                      <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 6 }}>
                        <Badge tone="cyan">{d.category || "General"}</Badge>
                        {isAgent ? (
                          <Badge tone="emerald">
                            <I.Bot size={11} style={{ marginRight: 4 }} /> SUTRA Agent
                          </Badge>
                        ) : (
                          <Badge tone="dim">
                            <I.User size={11} style={{ marginRight: 4 }} /> Human
                          </Badge>
                        )}
                        {d.task_id && (
                          <Badge tone="indigo">
                            <I.CheckSquare size={11} style={{ marginRight: 4 }} /> Task Linked
                          </Badge>
                        )}
                      </div>
                      <div style={{ fontSize: 16, fontWeight: 600, color: "#fff" }}>{d.title}</div>
                      <div style={{ fontSize: 12, color: "var(--muted)", marginTop: 4 }}>
                        Started by <b>{d.author_name || "Author"}</b> on {new Date(d.created_at).toLocaleDateString()}
                      </div>
                    </div>
                    <I.ChevronRight size={18} style={{ color: "var(--muted)" }} />
                  </Card>
                </Link>
              );
            })}
          </div>
        )}
      </div>
    </AppShell>
  );
}