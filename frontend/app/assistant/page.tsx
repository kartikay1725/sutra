"use client";

import { useEffect, useState } from "react";
import { AppShell, PageHead, Card, Btn, Badge } from "@/components/shell";
import { repositoriesService, Repository } from "@/lib/repositories";
import * as I from "lucide-react";
import Link from "next/link";

export default function AssistantGlobalPage() {
  const [repositories, setRepositories] = useState<Repository[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");

  useEffect(() => {
    async function load() {
      try {
        const repos = await repositoriesService.list();
        setRepositories(repos || []);
      } catch (e) {
        console.error("Failed to load repositories", e);
      } finally {
        setLoading(false);
      }
    }
    void load();
  }, []);

  const filtered = repositories.filter(
    (r) =>
      r.name.toLowerCase().includes(search.toLowerCase()) ||
      (r.description && r.description.toLowerCase().includes(search.toLowerCase()))
  );

  return (
    <AppShell>
      <div style={{ maxWidth: 1100, margin: "0 auto", padding: "28px 24px" }}>
        <PageHead
          eyebrow="Autonomous Engineering Context"
          title="SUTRA AI Assistant"
          sub="Ask questions about tasks, changes, pull requests, CI checks, code provenance, and governance."
        />

        <div style={{ margin: "24px 0", display: "flex", gap: 12 }}>
          <div style={{ position: "relative", flex: 1 }}>
            <I.Search
              size={14}
              style={{
                position: "absolute",
                left: 12,
                top: "50%",
                transform: "translateY(-50%)",
                color: "var(--muted)",
              }}
            />
            <input
              type="text"
              placeholder="Search repositories to launch assistant..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              style={{
                width: "100%",
                padding: "10px 12px 10px 36px",
                borderRadius: 8,
                border: "1px solid var(--line)",
                background: "var(--bg-subtle)",
                color: "var(--fg)",
                fontSize: 14,
              }}
            />
          </div>
        </div>

        {loading ? (
          <div style={{ padding: 40, textAlign: "center" }} className="muted">
            Loading repositories...
          </div>
        ) : filtered.length === 0 ? (
          <Card style={{ padding: 40, textAlign: "center" }}>
            <I.Bot size={32} style={{ color: "var(--muted)", margin: "0 auto 12px", opacity: 0.6 }} />
            <div style={{ fontSize: 16, fontWeight: 600, color: "var(--fg)" }}>No repositories found</div>
            <div style={{ fontSize: 13, color: "var(--muted)", marginTop: 4 }}>
              Select or import a repository to consult the SUTRA Assistant.
            </div>
          </Card>
        ) : (
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(320px, 1fr))", gap: 16 }}>
            {filtered.map((repo) => (
              <Link
                key={repo.id}
                href={`/repositories/${encodeURIComponent(repo.name)}/assistant`}
                style={{ textDecoration: "none" }}
              >
                <Card
                  style={{
                    padding: 20,
                    height: "100%",
                    display: "flex",
                    flexDirection: "column",
                    justifyContent: "space-between",
                    transition: "transform .15s, border-color .15s",
                    cursor: "pointer",
                  }}
                >
                  <div>
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 8 }}>
                      <div style={{ fontSize: 16, fontWeight: 700, color: "#fff" }}>{repo.name}</div>
                      <Badge tone="accent">Assistant ready</Badge>
                    </div>
                    <div style={{ fontSize: 13, color: "var(--muted)", lineHeight: 1.5, marginBottom: 16 }}>
                      {repo.description || "No description provided."}
                    </div>
                  </div>

                  <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", paddingTop: 12, borderTop: "1px solid var(--line)" }}>
                    <span style={{ fontSize: 12, color: "var(--muted)", display: "flex", alignItems: "center", gap: 5 }}>
                      <I.Bot size={13} style={{ color: "var(--accent)" }} />
                      Live Control Plane Context
                    </span>
                    <span style={{ fontSize: 12, fontWeight: 600, color: "var(--accent)", display: "flex", alignItems: "center", gap: 4 }}>
                      Open Assistant <I.ArrowRight size={13} />
                    </span>
                  </div>
                </Card>
              </Link>
            ))}
          </div>
        )}
      </div>
    </AppShell>
  );
}
