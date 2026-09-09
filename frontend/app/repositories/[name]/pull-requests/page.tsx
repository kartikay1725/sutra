"use client";

import { use, useEffect, useState, useMemo } from "react";
import { useRouter } from "next/navigation";
import { AppShell, PageHead, Card, Btn } from "@/components/shell";
import { pullRequestService, PullRequest } from "@/lib/pull-requests";
import { repositoryService } from "@/lib/repositories";
import { authService } from "@/lib/auth";
import * as I from "lucide-react";

const STATUS_COLORS: Record<string, string> = {
  open: "var(--cyan)",
  draft: "var(--muted)",
  approved: "var(--green)",
  merged: "var(--purple)",
  closed: "var(--muted)",
  rejected: "var(--red)",
};

const STATUS_ICONS: Record<string, React.ReactNode> = {
  open: <I.GitPullRequest size={14} />,
  draft: <I.GitPullRequestDraft size={14} />,
  approved: <I.CheckCircle2 size={14} />,
  merged: <I.GitMerge size={14} />,
  closed: <I.GitPullRequestClosed size={14} />,
  rejected: <I.XCircle size={14} />,
};

function timeAgo(dateStr: string) {
  const diff = Date.now() - new Date(dateStr).getTime();
  const m = Math.floor(diff / 60000);
  if (m < 1) return "just now";
  if (m < 60) return `${m}m ago`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}h ago`;
  return `${Math.floor(h / 24)}d ago`;
}

export default function PullRequestsPage({ params }: { params: Promise<{ name: string }> }) {
  const { name: repoName } = use(params);
  const router = useRouter();
  const [owner, setOwner] = useState<string>("");
  const [prs, setPrs] = useState<PullRequest[]>([]);
  const [loading, setLoading] = useState(true);
  const [activeFilter, setActiveFilter] = useState("All");
  const [search, setSearch] = useState("");

  useEffect(() => {
    const load = async () => {
      setLoading(true);
      try {
        const user = await authService.getCurrentUser();
        if (user?.username) setOwner(user.username);
        const repo = await repositoryService.getRepository(user.username, repoName);
        const data = await pullRequestService.listPRs(repo.id);
        setPrs(data);
      } catch (e) {
        console.error("Failed to load PRs", e);
        setPrs([]);
      } finally {
        setLoading(false);
      }
    };
    load();
  }, [repoName]);

  const filteredPrs = useMemo(() => {
    return prs.filter(pr => {
      const matchesSearch = !search || pr.title.toLowerCase().includes(search.toLowerCase());
      if (!matchesSearch) return false;
      if (activeFilter === "All") return true;
      if (activeFilter === "Needs Review") return pr.status === "open";
      if (activeFilter === "My PRs") return true; // author filter needs user id
      if (activeFilter === "Approved") return pr.status === "approved";
      if (activeFilter === "Merged") return pr.status === "merged";
      return true;
    });
  }, [prs, activeFilter, search]);

  const stats = {
    open: prs.filter(p => p.status === "open" || p.status === "draft").length,
    approved: prs.filter(p => p.status === "approved").length,
    merged: prs.filter(p => p.status === "merged").length,
  };

  const needsReview = filteredPrs.filter(p => p.status === "open");
  const others = filteredPrs.filter(p => p.status !== "open");

  const PRCard = ({ pr }: { pr: PullRequest }) => (
    <div onClick={() => router.push(`/repositories/${repoName}/pull-requests/${pr.id}`)} style={{ cursor: "pointer" }}>
      <Card style={{
        padding: 0, overflow: "hidden", transition: "border-color 0.2s",
        borderLeft: `3px solid ${pr.status === "open" ? "var(--cyan)" : "transparent"}`,
      }}>
        <div style={{ padding: "20px 24px" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 12 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <span style={{ color: STATUS_COLORS[pr.status], display: "flex", alignItems: "center" }}>
                {STATUS_ICONS[pr.status]}
              </span>
              <span style={{ fontSize: 12, fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.5px", color: STATUS_COLORS[pr.status] }}>
                {pr.status}
              </span>
            </div>
            <span style={{ fontSize: 12, color: "var(--muted)" }}>{timeAgo(pr.updated_at)}</span>
          </div>

          <div style={{ marginBottom: 12 }}>
            <div style={{ fontSize: 17, fontWeight: 600, color: "var(--fg)", marginBottom: 4, lineHeight: 1.3 }}>
              {pr.title}
            </div>
            {pr.description && (
              <div style={{ fontSize: 13, color: "var(--muted)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                {pr.description}
              </div>
            )}
          </div>

          <div style={{ display: "flex", alignItems: "center", gap: 16, fontSize: 13, color: "var(--muted)" }}>
            <div style={{ display: "flex", alignItems: "center", gap: 5 }}>
              <I.GitBranch size={13} />
              <span style={{ fontFamily: "monospace", fontSize: 12 }}>
                {pr.source_commit ? pr.source_commit.slice(0, 7) : "—"} → {pr.target_branch}
              </span>
            </div>
            <div style={{ display: "flex", alignItems: "center", gap: 5 }}>
              <I.Hash size={13} />
              <span>{pr.id.slice(0, 8)}</span>
            </div>
          </div>
        </div>
      </Card>
    </div>
  );

  return (
    <AppShell>
      <PageHead
        eyebrow={repoName}
        title="Pull Requests"
        sub="Review and ship changes across your repository."
        action={
          <a
            href={`https://github.com/${owner}/${repoName}/pulls`}
            target="_blank"
            rel="noopener noreferrer"
            className="btn primary"
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: 6,
              textDecoration: "none",
            }}
          >
            <I.ExternalLink size={14} />
            Open on GitHub
          </a>
        }
      />

      <div style={{ maxWidth: 960, margin: "0 auto", padding: "0 20px" }}>

        {/* Filter Bar */}
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
          <div style={{ display: "flex", gap: 6 }}>
            {["All", "Needs Review", "My PRs", "Approved", "Merged"].map(f => (
              <button key={f} onClick={() => setActiveFilter(f)} style={{
                background: activeFilter === f ? "var(--bg-subtle)" : "transparent",
                border: "1px solid", borderColor: activeFilter === f ? "var(--line)" : "transparent",
                color: activeFilter === f ? "var(--fg)" : "var(--muted)",
                padding: "6px 14px", borderRadius: 6, cursor: "pointer", fontSize: 14,
                fontWeight: activeFilter === f ? 600 : 400,
              }}>{f}</button>
            ))}
          </div>
          <div style={{ position: "relative" }}>
            <I.Search size={14} style={{ position: "absolute", left: 10, top: "50%", transform: "translateY(-50%)", color: "var(--muted)" }} />
            <input
              value={search}
              onChange={e => setSearch(e.target.value)}
              placeholder="Search pull requests..."
              style={{ padding: "7px 12px 7px 32px", borderRadius: 6, border: "1px solid var(--line)", background: "var(--bg)", color: "var(--fg)", fontSize: 14, width: 220 }}
            />
          </div>
        </div>

        {/* Stats Row */}
        <div style={{ display: "flex", gap: 24, fontSize: 14, color: "var(--muted)", marginBottom: 24, padding: "12px 16px", background: "var(--bg-subtle)", borderRadius: 8, border: "1px solid var(--line)" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <I.GitPullRequest size={14} color="var(--cyan)" />
            <strong style={{ color: "var(--fg)" }}>{stats.open}</strong> Open
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <I.CheckCircle2 size={14} color="var(--green)" />
            <strong style={{ color: "var(--fg)" }}>{stats.approved}</strong> Approved
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <I.GitMerge size={14} color="var(--purple)" />
            <strong style={{ color: "var(--fg)" }}>{stats.merged}</strong> Merged
          </div>
        </div>

        {loading ? (
          <div style={{ padding: 48, textAlign: "center", color: "var(--muted)" }}>Loading pull requests...</div>
        ) : filteredPrs.length === 0 ? (
          <div style={{ padding: 48, textAlign: "center", color: "var(--muted)", background: "var(--bg-subtle)", borderRadius: 8, border: "1px solid var(--line)" }}>
            <I.GitPullRequest size={32} style={{ marginBottom: 16, opacity: 0.3 }} />
            <div style={{ fontSize: 16, fontWeight: 500 }}>No pull requests found.</div>
          </div>
        ) : (
          <div style={{ display: "flex", flexDirection: "column", gap: 24 }}>
            {needsReview.length > 0 && (
              <section>
                <div style={{ fontSize: 12, fontWeight: 700, letterSpacing: "1px", textTransform: "uppercase", color: "var(--muted)", marginBottom: 12 }}>
                  Needs Review
                </div>
                <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
                  {needsReview.map(pr => <PRCard key={pr.id} pr={pr} />)}
                </div>
              </section>
            )}
            {others.length > 0 && (
              <section>
                {needsReview.length > 0 && (
                  <div style={{ fontSize: 12, fontWeight: 700, letterSpacing: "1px", textTransform: "uppercase", color: "var(--muted)", marginBottom: 12 }}>
                    Other
                  </div>
                )}
                <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
                  {others.map(pr => <PRCard key={pr.id} pr={pr} />)}
                </div>
              </section>
            )}
          </div>
        )}
      </div>
    </AppShell>
  );
}