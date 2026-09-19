"use client";

import { use, useEffect, useState, useMemo } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { AppShell, PageHead, Card, Btn, SkeletonPRList } from "@/components/shell";
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
  const [page, setPage] = useState(1);
  const PAGE_SIZE = 10;

  useEffect(() => {
    const load = async () => {
      setLoading(true);
      try {
        const user = await authService.getCurrentUser();
        if (user?.username) setOwner(user.username);
        const repo = await repositoryService.getRepository(user.username, repoName);
        const data = await pullRequestService.listPRs(repo.id);
        setPrs(data);
        setPage(1);
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

  const totalPages = Math.max(1, Math.ceil(filteredPrs.length / PAGE_SIZE));
  const safePage = Math.min(page, totalPages);
  const paginatedPrs = useMemo(() => {
    return filteredPrs.slice((safePage - 1) * PAGE_SIZE, safePage * PAGE_SIZE);
  }, [filteredPrs, safePage]);

  const stats = {
    open: prs.filter(p => p.status === "open" || p.status === "draft").length,
    approved: prs.filter(p => p.status === "approved").length,
    merged: prs.filter(p => p.status === "merged").length,
  };

  const needsReview = paginatedPrs.filter(p => p.status === "open");
  const others = paginatedPrs.filter(p => p.status !== "open");

  const PRCard = ({ pr }: { pr: PullRequest }) => (
    <Link
      href={`/repositories/${encodeURIComponent(repoName)}/pull-requests/${pr.id}`}
      style={{
        textDecoration: "none",
        color: "inherit",
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        gap: 16,
        padding: "14px 18px",
        background: "var(--surface)",
        border: "1px solid var(--line)",
        borderRadius: "var(--radius-sm)",
        transition: "all 0.15s ease",
        cursor: "pointer",
      }}
      className="list-row"
    >
      <div style={{ display: "flex", alignItems: "flex-start", gap: 12, minWidth: 0 }}>
        <span style={{ color: STATUS_COLORS[pr.status], marginTop: 2, flexShrink: 0 }}>
          {STATUS_ICONS[pr.status]}
        </span>
        <div style={{ minWidth: 0 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
            <span style={{ fontSize: 14, fontWeight: 600, color: "var(--text-primary)" }}>
              {pr.title}
            </span>
            <span style={{ fontSize: 11, fontFamily: "var(--font-mono, monospace)", color: "var(--muted)" }}>
              #{pr.id.slice(0, 7)}
            </span>
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: 12, fontSize: 12, color: "var(--muted)", marginTop: 4, flexWrap: "wrap" }}>
            <span style={{ fontFamily: "var(--font-mono, monospace)" }}>
              {pr.source_commit ? pr.source_commit.slice(0, 7) : "branch"} → {pr.target_branch}
            </span>
            <span>·</span>
            <span>updated {timeAgo(pr.updated_at)}</span>
          </div>
        </div>
      </div>

      <div style={{ display: "flex", alignItems: "center", gap: 10, flexShrink: 0 }}>
        <span className={`badge ${pr.status === "approved" || pr.status === "merged" ? "green" : pr.status === "open" ? "blue" : "gray"}`}>
          {pr.status}
        </span>
      </div>
    </Link>
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

      <div style={{ width: "100%" }}>

        {/* Filter Bar */}
        <div className="changes-filter-row" style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
          <div className="changes-filter-tabs" style={{ display: "flex", gap: 6 }}>
            {["All", "Needs Review", "My PRs", "Approved", "Merged"].map(f => (
              <button key={f} onClick={() => {
                setActiveFilter(f);
                setPage(1);
              }} style={{
                background: activeFilter === f ? "var(--bg-subtle)" : "transparent",
                border: "1px solid", borderColor: activeFilter === f ? "var(--line)" : "transparent",
                color: activeFilter === f ? "var(--fg)" : "var(--muted)",
                padding: "6px 14px", borderRadius: 6, cursor: "pointer", fontSize: 14,
                fontWeight: activeFilter === f ? 600 : 400,
                flexShrink: 0,
              }}>{f}</button>
            ))}
          </div>
          <div className="changes-search-group" style={{ position: "relative" }}>
            <I.Search size={14} style={{ position: "absolute", left: 10, top: "50%", transform: "translateY(-50%)", color: "var(--muted)" }} />
            <input
              value={search}
              onChange={e => {
                setSearch(e.target.value);
                setPage(1);
              }}
              placeholder="Search pull requests..."
              style={{ padding: "7px 12px 7px 32px", borderRadius: 6, border: "1px solid var(--line)", background: "var(--bg)", color: "var(--fg)", fontSize: 14, width: "100%", maxWidth: 220 }}
            />
          </div>
        </div>

        {/* Stats Row */}
        <div className="changes-stats-row" style={{ display: "flex", gap: 24, fontSize: 14, color: "var(--muted)", marginBottom: 24, padding: "12px 16px", background: "var(--bg-subtle)", borderRadius: 8, border: "1px solid var(--line)" }}>
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
          <SkeletonPRList count={5} />
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

            {/* Pagination Controls (10 per page) */}
            {filteredPrs.length > PAGE_SIZE && (
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "space-between",
                  padding: "16px 4px 8px",
                  gap: 12,
                }}
              >
                <span style={{ fontSize: 12, color: "var(--muted)" }}>
                  Showing {(safePage - 1) * PAGE_SIZE + 1}–{Math.min(safePage * PAGE_SIZE, filteredPrs.length)} of {filteredPrs.length} pull requests
                </span>
                <div style={{ display: "flex", gap: 8 }}>
                  <Btn
                    disabled={safePage <= 1}
                    onClick={() => setPage((p) => Math.max(1, p - 1))}
                  >
                    Previous
                  </Btn>
                  <span style={{ fontSize: 12, color: "var(--muted)", minWidth: 48, textAlign: "center", lineHeight: "28px" }}>
                    {safePage} / {totalPages}
                  </span>
                  <Btn
                    disabled={safePage >= totalPages}
                    onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                  >
                    Next
                  </Btn>
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </AppShell>
  );
}