"use client";

import { useEffect, useMemo, useState, useRef, Suspense } from "react";
import Link from "next/link";
import { useSearchParams, useRouter } from "next/navigation";
import {
  GitBranch,
  Bot,
  UserRound,
  ShieldAlert,
  Search,
  RefreshCw,
  Sparkles,
  ArrowUpRight,
  FileCode2,
  CheckCircle2,
  Clock,
  AlertTriangle,
  GitPullRequest,
} from "lucide-react";
import { AppShell, PageHead, Card, Badge, Btn, Stat } from "@/components/shell";
import { SkeletonChangeList } from "@/components/skeleton";
import { changeService, type Change } from "@/lib/changes";
import { sutraCache } from "@/lib/cache";

function relativeTime(value: string | null | undefined): string {
  if (!value) return "—";
  const timestamp = new Date(value).getTime();
  if (!Number.isFinite(timestamp)) return "—";
  const diff = Math.max(0, Date.now() - timestamp);
  const minutes = Math.floor(diff / 60000);
  if (minutes < 1) return "just now";
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  if (days < 30) return `${days}d ago`;
  return `${Math.floor(days / 30)}mo ago`;
}

function GlobalChangesContent() {
  const searchParams = useSearchParams();
  const router = useRouter();

  const initialActor = searchParams.get("actor_type") || "all";
  const initialStatus = searchParams.get("status") || "all";

  const [changes, setChanges] = useState<Change[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [actorType, setActorType] = useState<string>(initialActor);
  const [status, setStatus] = useState<string>(initialStatus);
  const [riskLevel, setRiskLevel] = useState<string>("all");
  const [search, setSearch] = useState<string>("");
  const initialMount = useRef(true);

  const [page, setPage] = useState(1);
  const PAGE_SIZE = 10;

  const load = async (forceRefresh = false) => {
    setLoading(changes.length === 0 || forceRefresh);
    setError(null);
    try {
      const cacheKey = `changes:${actorType}:${status}:${riskLevel}:${search}`;
      const rows = await sutraCache.getOrFetch<Change[]>(
        cacheKey,
        async () => {
          const res = await changeService.getAllChanges({
            actor_type: actorType,
            status: status,
            risk_level: riskLevel,
            search: search,
          });
          return res.sort(
            (a, b) =>
              new Date(b.updated_at || b.created_at || 0).getTime() -
              new Date(a.updated_at || a.created_at || 0).getTime()
          );
        },
        { staleMs: 15000, ttlMs: 60000, forceRefresh }
      );
      setChanges(rows);
      setPage(1);
    } catch (err: any) {
      console.error("Failed to load changes:", err);
      setError(err?.message || "Failed to load global changes");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void load();
  }, [actorType, status, riskLevel]);

  // Handle live search debounce (skip duplicate initial mount trigger)
  useEffect(() => {
    if (initialMount.current) {
      initialMount.current = false;
      return;
    }
    const handler = setTimeout(() => {
      void load();
    }, 300);
    return () => clearTimeout(handler);
  }, [search]);

  // Derived statistics
  const agentChangesCount = useMemo(
    () => changes.filter((c) => c.actor_type === "agent" || Boolean(c.agent_id)).length,
    [changes]
  );
  const proposedCount = useMemo(
    () => changes.filter((c) => c.status === "proposed").length,
    [changes]
  );
  const recordedCount = useMemo(
    () => changes.filter((c) => c.status === "recorded").length,
    [changes]
  );
  const mergedCount = useMemo(
    () => changes.filter((c) => c.status === "merged" || c.pull_request_status === "merged").length,
    [changes]
  );

  return (
    <AppShell>
      <PageHead
        eyebrow="Autonomous Engineering Control Plane"
        title="Global Changes"
        sub="Authoritative register of all code changes declared and executed by autonomous agents and developers across all repositories."
        action={
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <Btn onClick={() => void load(true)} disabled={loading}>
              <RefreshCw size={13} className={loading ? "spin" : ""} /> Refresh
            </Btn>
          </div>
        }
      />

      {/* KPI Stats Strip */}
      <div className="grid g4" style={{ marginBottom: 18 }}>
        <Stat label="Total Changes" value={String(changes.length)} />
        <Stat
          label="Agent Changes"
          value={String(agentChangesCount)}
          delta="Synthesized by autonomous agents"
        />
        <Stat
          label="Needing Review"
          value={String(proposedCount)}
          delta="Pending human review or CI"
        />
        <Stat
          label="Recorded / Merged"
          value={String(recordedCount + mergedCount)}
          delta="Governed commits"
        />
      </div>

      {/* Filters Card */}
      <Card style={{ marginBottom: 18 }}>
        <div
          style={{
            padding: "16px 20px",
            display: "flex",
            flexDirection: "column",
            gap: 14,
          }}
        >
          {/* Search Input */}
          <div style={{ position: "relative", width: "100%" }}>
            <Search
              size={15}
              style={{
                position: "absolute",
                left: 14,
                top: "50%",
                transform: "translateY(-50%)",
                color: "var(--muted)",
              }}
            />
            <input
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Filter by intent, title, branch, repo, or agent name…"
              style={{
                width: "100%",
                padding: "9px 14px 9px 38px",
                background: "var(--bg)",
                border: "1px solid var(--line)",
                borderRadius: 8,
                color: "var(--fg)",
                fontSize: 13,
                outline: "none",
                boxSizing: "border-box",
              }}
            />
          </div>

          {/* Filter Pills */}
          <div
            className="filter-pills-row"
            style={{
              display: "flex",
              flexWrap: "wrap",
              alignItems: "center",
              justifyContent: "space-between",
              gap: 12,
            }}
          >
            {/* Actor Filter */}
            <div style={{ display: "flex", flexWrap: "wrap", alignItems: "center", gap: 6 }}>
              <span style={{ fontSize: 12, color: "var(--muted)", marginRight: 4 }}>
                Actor:
              </span>
              {[
                { id: "all", label: "All Actors", icon: null },
                { id: "agent", label: "Agents Only", icon: <Bot size={13} /> },
                { id: "human", label: "Humans Only", icon: <UserRound size={13} /> },
              ].map((pill) => (
                <button
                  type="button"
                  key={pill.id}
                  onClick={() => setActorType(pill.id)}
                  className={`badge ${actorType === pill.id ? "aqua" : ""}`}
                  style={{
                    cursor: "pointer",
                    display: "inline-flex",
                    alignItems: "center",
                    gap: 5,
                    padding: "4px 10px",
                    borderRadius: 6,
                    border:
                      actorType === pill.id
                        ? "1px solid var(--accent-border)"
                        : "1px solid var(--border-default)",
                    background:
                      actorType === pill.id
                        ? "var(--accent-subtle)"
                        : "transparent",
                    color: actorType === pill.id ? "var(--accent)" : "var(--text-muted)",
                    fontWeight: actorType === pill.id ? 600 : 500,
                  }}
                >
                  {pill.icon}
                  {pill.label}
                </button>
              ))}
            </div>

            {/* Status Filter */}
            <div style={{ display: "flex", flexWrap: "wrap", alignItems: "center", gap: 6 }}>
              <span style={{ fontSize: 12, color: "var(--muted)", marginRight: 4 }}>
                Status:
              </span>
              {[
                { id: "all", label: "All" },
                { id: "proposed", label: "Proposed" },
                { id: "recorded", label: "Recorded" },
                { id: "merged", label: "Merged" },
                { id: "blocked", label: "Blocked" },
                { id: "rejected", label: "Rejected" },
              ].map((pill) => (
                <button
                  type="button"
                  key={pill.id}
                  onClick={() => setStatus(pill.id)}
                  className={`badge ${status === pill.id ? "orange" : ""}`}
                  style={{
                    cursor: "pointer",
                    padding: "4px 10px",
                    borderRadius: 6,
                    border:
                      status === pill.id
                        ? "1px solid var(--accent-border)"
                        : "1px solid var(--border-default)",
                    background:
                      status === pill.id
                        ? "var(--accent-subtle)"
                        : "transparent",
                    color: status === pill.id ? "var(--accent)" : "var(--text-muted)",
                    fontWeight: status === pill.id ? 600 : 500,
                    textTransform: "capitalize",
                  }}
                >
                  {pill.label}
                </button>
              ))}
            </div>

            {/* Risk Filter */}
            <div style={{ display: "flex", flexWrap: "wrap", alignItems: "center", gap: 6 }}>
              <span style={{ fontSize: 12, color: "var(--muted)", marginRight: 4 }}>
                Risk:
              </span>
              {[
                { id: "all", label: "All" },
                { id: "critical", label: "Critical" },
                { id: "high", label: "High" },
                { id: "medium", label: "Med" },
                { id: "low", label: "Low" },
              ].map((pill) => (
                <button
                  type="button"
                  key={pill.id}
                  onClick={() => setRiskLevel(pill.id)}
                  className={`badge ${riskLevel === pill.id ? "amber" : ""}`}
                  style={{
                    cursor: "pointer",
                    padding: "4px 8px",
                    borderRadius: 6,
                    border:
                      riskLevel === pill.id
                        ? "1px solid rgba(245,158,11,0.3)"
                        : "1px solid var(--border-default)",
                    background:
                      riskLevel === pill.id
                        ? "rgba(245,158,11,0.10)"
                        : "transparent",
                    color: riskLevel === pill.id ? "var(--warning)" : "var(--text-muted)",
                    fontWeight: riskLevel === pill.id ? 600 : 500,
                  }}
                >
                  {pill.label}
                </button>
              ))}
            </div>
          </div>
        </div>
      </Card>

      {/* Changes Listing */}
      {error && (
        <Card style={{ marginBottom: 16, borderColor: "rgba(239,68,68,0.3)" }}>
          <div className="card-pad" style={{ color: "#ef4444" }}>
            {error}
          </div>
        </Card>
      )}

      {loading ? (
        <SkeletonChangeList count={6} />
      ) : changes.length === 0 ? (
        <Card>
          <div
            className="card-pad"
            style={{ textAlign: "center", padding: "54px 20px" }}
          >
            <GitBranch
              size={36}
              className="muted"
              style={{ marginBottom: 12, opacity: 0.6 }}
            />
            <div className="title-sm" style={{ marginBottom: 4 }}>
              No Changes Found
            </div>
            <div className="sub" style={{ maxWidth: 420, margin: "0 auto" }}>
              No governed code changes match your current filters. Clear your filters
              or initiate a new task with an autonomous agent.
            </div>
          </div>
        </Card>
      ) : (
        <>
          <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
            {changes.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE).map((change) => {
              const isAgent =
                change.actor_type === "agent" || Boolean(change.agent_id);
              const detailHref = change.repository_name
                ? `/repositories/${encodeURIComponent(change.repository_name)}/changes/${encodeURIComponent(change.id)}`
                : `/changes/${encodeURIComponent(change.id)}`;

              return (
                <Card key={change.id} style={{ transition: "border-color var(--motion-fast) var(--ease-subtle)" }}>
                  <div
                    style={{
                      padding: "16px 20px",
                      display: "flex",
                      alignItems: "flex-start",
                      justifyContent: "space-between",
                      gap: 16,
                    }}
                  >
                    {/* Left: Change Info */}
                    <div style={{ flex: 1, minWidth: 0 }}>
                      {/* Top Meta Line: Repo, Branch, Actor */}
                      <div
                        style={{
                          display: "flex",
                          alignItems: "center",
                          gap: 8,
                          flexWrap: "wrap",
                          marginBottom: 6,
                        }}
                      >
                        {/* Repo Name */}
                        {change.repository_name ? (
                          <Link
                            href={`/repositories/${encodeURIComponent(change.repository_name)}`}
                            style={{
                              fontSize: 12,
                              fontWeight: 600,
                              color: "var(--link)",
                              textDecoration: "none",
                            }}
                          >
                            {change.repository_name}
                          </Link>
                        ) : (
                          <span
                            style={{
                              fontSize: 12,
                              color: "var(--muted)",
                              fontFamily: "monospace",
                            }}
                          >
                            {change.repository_id.slice(0, 8)}
                          </span>
                        )}

                        <span style={{ color: "var(--line)" }}>•</span>

                        {/* Actor Badge */}
                        {isAgent ? (
                          <span
                            className="badge orange"
                            style={{
                              fontSize: 11,
                              padding: "2px 8px",
                              display: "inline-flex",
                              alignItems: "center",
                              gap: 4,
                              borderRadius: 4,
                            }}
                          >
                            <Bot size={12} />
                            {change.agent_name || change.actor_name || "Agent"}
                          </span>
                        ) : (
                          <span
                            className="badge gray"
                            style={{
                              fontSize: 11,
                              padding: "2px 8px",
                              display: "inline-flex",
                              alignItems: "center",
                              gap: 4,
                              borderRadius: 4,
                            }}
                          >
                            <UserRound size={12} />
                            {change.actor_name || "User"}
                          </span>
                        )}

                        {/* Branch */}
                        {((change as any).branch_name || change.branch) && (
                          <>
                            <span style={{ color: "var(--line)" }}>•</span>
                            <span
                              style={{
                                fontSize: 12,
                                color: "var(--muted)",
                                display: "inline-flex",
                                alignItems: "center",
                                gap: 4,
                                fontFamily: "monospace",
                              }}
                            >
                              <GitBranch size={12} />
                              {(change as any).branch_name || change.branch}
                            </span>
                          </>
                        )}

                        {/* Time */}
                        <span style={{ color: "var(--line)" }}>•</span>
                        <span style={{ fontSize: 12, color: "var(--muted)" }}>
                          {relativeTime(change.updated_at || change.created_at)}
                        </span>
                      </div>

                      {/* Intent / Title */}
                      <div
                        style={{
                          fontSize: 15,
                          fontWeight: 600,
                          color: "var(--fg)",
                          marginBottom: 6,
                          lineHeight: 1.4,
                        }}
                      >
                        <Link
                          href={detailHref}
                          style={{
                            color: "inherit",
                            textDecoration: "none",
                          }}
                        >
                          {change.intent ||
                            change.title ||
                            `Change ${change.id.slice(0, 8)}`}
                        </Link>
                      </div>

                      {/* Description if present */}
                      {change.description && (
                        <div
                          style={{
                            fontSize: 13,
                            color: "var(--muted)",
                            marginBottom: 8,
                            lineHeight: 1.5,
                            display: "-webkit-box",
                            WebkitLineClamp: 2,
                            WebkitBoxOrient: "vertical",
                            overflow: "hidden",
                          }}
                        >
                          {change.description}
                        </div>
                      )}

                      {/* Bottom Meta Badges: Stats, Risk, Governance */}
                      <div
                        style={{
                          display: "flex",
                          alignItems: "center",
                          gap: 12,
                          flexWrap: "wrap",
                          fontSize: 12,
                        }}
                      >
                        {/* Additions / Deletions / Files */}
                        <span
                          style={{
                            display: "inline-flex",
                            alignItems: "center",
                            gap: 6,
                            color: "var(--muted)",
                          }}
                        >
                          <FileCode2 size={13} />
                          {change.files_changed !== undefined ? (
                            <span>{change.files_changed} files</span>
                          ) : null}
                          {change.additions !== undefined ? (
                            <span style={{ color: "var(--green)", fontWeight: 600 }}>
                              +{change.additions}
                            </span>
                          ) : null}
                          {change.deletions !== undefined ? (
                            <span style={{ color: "var(--red)", fontWeight: 600 }}>
                              -{change.deletions}
                            </span>
                          ) : null}
                        </span>

                        {/* Risk Level Badge */}
                        {change.risk_level && (
                          <span
                            className={`badge ${
                              change.risk_level === "critical" ||
                              change.risk_level === "high"
                                ? "red"
                                : change.risk_level === "medium"
                                ? "orange"
                                : "green"
                            }`}
                            style={{
                              fontSize: 11,
                              padding: "2px 7px",
                              display: "inline-flex",
                              alignItems: "center",
                              gap: 3,
                              borderRadius: 4,
                            }}
                          >
                            <ShieldAlert size={11} />
                            {change.risk_level} risk
                          </span>
                        )}

                        {/* Linked PR Badge if any */}
                        {change.pull_request_id && (
                          <span
                            className="badge aqua"
                            style={{
                              fontSize: 11,
                              padding: "2px 7px",
                              display: "inline-flex",
                              alignItems: "center",
                              gap: 3,
                              borderRadius: 4,
                            }}
                          >
                            <GitPullRequest size={11} />
                            PR linked
                          </span>
                        )}

                        {/* Linked Task Badge if any */}
                        {change.task_id && (
                          <span
                            style={{
                              fontSize: 11,
                              color: "var(--muted)",
                              fontFamily: "monospace",
                            }}
                          >
                            task-{change.task_id.slice(0, 6)}
                          </span>
                        )}
                      </div>
                    </div>

                    {/* Right: Status & Inspect CTA */}
                    <div
                      style={{
                        display: "flex",
                        flexDirection: "column",
                        alignItems: "flex-end",
                        gap: 10,
                        flexShrink: 0,
                      }}
                    >
                      <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                        {/* Governance Indicator */}
                        {Boolean((change as any).governance_state || (change as any).policy_status) && (
                          <Badge
                            tone={
                              ((change as any).governance_state || (change as any).policy_status) === "passed"
                                ? "green"
                                : ((change as any).governance_state || (change as any).policy_status) === "failed"
                                ? "red"
                                : "amber"
                            }
                          >
                            {(change as any).governance_state || (change as any).policy_status}
                          </Badge>
                        )}

                        {/* Status Badge */}
                        <Badge
                          tone={
                            change.status === "recorded" || change.status === "merged"
                              ? "green"
                              : change.status === "blocked" ||
                                change.status === "rejected"
                              ? "red"
                              : "aqua"
                          }
                        >
                          {change.status}
                        </Badge>
                      </div>

                      <Link href={detailHref} style={{ textDecoration: "none" }}>
                        <Btn
                          sm
                          style={{
                            fontSize: 12,
                            padding: "4px 10px",
                            display: "inline-flex",
                            alignItems: "center",
                            gap: 4,
                          }}
                        >
                          Inspect <ArrowUpRight size={13} />
                        </Btn>
                      </Link>
                    </div>
                  </div>
                </Card>
              );
            })}
          </div>

          {/* Pagination Controls (10 per page) */}
          {changes.length > PAGE_SIZE && (() => {
            const totalPages = Math.ceil(changes.length / PAGE_SIZE);
            return (
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "space-between",
                  padding: "16px 4px 8px",
                  marginTop: 8,
                }}
              >
                <span style={{ fontSize: 12, color: "var(--muted)" }}>
                  Showing {(page - 1) * PAGE_SIZE + 1}–{Math.min(page * PAGE_SIZE, changes.length)} of {changes.length} changes
                </span>
                <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                  <Btn
                    disabled={page <= 1}
                    onClick={() => setPage((p) => Math.max(1, p - 1))}
                    style={{ padding: "4px 10px", fontSize: 12 }}
                  >
                    Previous
                  </Btn>
                  <span style={{ fontSize: 12, color: "var(--muted)", minWidth: 48, textAlign: "center" }}>
                    {page} / {totalPages}
                  </span>
                  <Btn
                    disabled={page >= totalPages}
                    onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                    style={{ padding: "4px 10px", fontSize: 12 }}
                  >
                    Next
                  </Btn>
                </div>
              </div>
            );
          })()}
        </>
      )}
    </AppShell>
  );
}

export default function GlobalChangesPage() {
  return (
    <Suspense
      fallback={
        <AppShell>
          <div style={{ padding: 40, textAlign: "center" }} className="muted">
            Loading Changes…
          </div>
        </AppShell>
      }
    >
      <GlobalChangesContent />
    </Suspense>
  );
}
