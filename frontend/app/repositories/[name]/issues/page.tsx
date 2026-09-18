"use client";

import { use, useCallback, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import {
  AlertCircle,
  Check,
  CheckCircle2,
  CircleDot,
  Filter,
  Loader2,
  MessageSquare,
  Plus,
  RefreshCw,
  Search,
  Trash2,
  X,
  ExternalLink,
} from "lucide-react";

import { AppShell, SkeletonIssueList } from "@/components/shell";
import { authService } from "@/lib/auth";
import { issueService, Issue } from "@/lib/issues";
import { repositoryService } from "@/lib/repositories";
import { clientCache } from "@/lib/cache";

type FilterState = "open" | "closed" | "all";

function getIssueStatus(issue: Issue): "open" | "closed" {
  return issue.state || issue.status || "open";
}

function formatDate(value: string): string {
  const date = new Date(value);

  if (Number.isNaN(date.getTime())) {
    return "Unknown date";
  }

  return date.toLocaleDateString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}

function formatRelativeDate(value: string): string {
  const date = new Date(value);

  if (Number.isNaN(date.getTime())) {
    return "unknown time";
  }

  const diffMs = Date.now() - date.getTime();
  const diffMinutes = Math.floor(diffMs / 60000);
  const diffHours = Math.floor(diffMinutes / 60);
  const diffDays = Math.floor(diffHours / 24);

  if (diffMinutes < 1) return "just now";
  if (diffMinutes < 60) return `${diffMinutes}m ago`;
  if (diffHours < 24) return `${diffHours}h ago`;
  if (diffDays < 30) return `${diffDays}d ago`;

  return formatDate(value);
}

function issueNumber(issue: Issue): string {
  if (typeof issue.number === "number") {
    return `#${issue.number}`;
  }

  return `#${issue.id.slice(0, 8)}`;
}

function getErrorMessage(error: unknown): string {
  if (error instanceof Error) {
    return error.message;
  }

  if (
    typeof error === "object" &&
    error !== null &&
    "message" in error
  ) {
    return String(
      (error as { message?: unknown }).message || "Something went wrong",
    );
  }

  return "Something went wrong";
}

export default function RepositoryIssuesPage({
  params,
}: {
  params: Promise<{ name: string }>;
}) {
  const { name: repoName } = use(params);

  const router = useRouter();

  const [owner, setOwner] = useState("");
  const [issues, setIssues] = useState<Issue[]>([]);
  const [filter, setFilter] = useState<FilterState>("open");
  const [search, setSearch] = useState("");

  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const [error, setError] = useState("");

  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [updatingId, setUpdatingId] = useState<string | null>(null);

  const [confirmDeleteId, setConfirmDeleteId] = useState<string | null>(null);
  const [lastSyncedAt, setLastSyncedAt] = useState<number | null>(null);

  const loadIssues = useCallback(
    async (showRefreshState = false, forceRefresh = false) => {
      if (!owner) {
        return;
      }

      const cacheKey = `issues:${owner.toLowerCase()}/${repoName.toLowerCase()}`;
      const cached = forceRefresh ? null : clientCache.get<Issue[]>(cacheKey);

      if (cached && !showRefreshState) {
        setIssues(Array.isArray(cached.data) ? cached.data : []);
        setLastSyncedAt(cached.cachedAt);
        setLoading(false);
      } else if (showRefreshState) {
        setRefreshing(true);
      } else {
        setLoading(true);
      }

      setError("");

      try {
        const data = await issueService.listIssues(
          owner,
          repoName,
          { forceRefresh }
        );

        setIssues(Array.isArray(data) ? data : []);
        const meta = clientCache.getMetadata(cacheKey);
        if (meta.lastSyncedAt) {
          setLastSyncedAt(meta.lastSyncedAt);
        }
      } catch (err) {
        setError(getErrorMessage(err));
      } finally {
        setLoading(false);
        setRefreshing(false);
      }
    },
    [owner, repoName],
  );

  useEffect(() => {
    let mounted = true;

    (async () => {
      try {
        const user = await authService.getCurrentUser();
        let canonicalOwner = user.username;
        try {
          const repo = await repositoryService.getRepository(user.username, repoName);
          if (repo && (repo.provider_owner || repo.owner)) {
            canonicalOwner = repo.provider_owner || repo.owner || user.username;
          }
        } catch {
          // Fall back to user.username if repo fetch fails
        }
        if (mounted) {
          setOwner(canonicalOwner);
        }
      } catch (err) {
        if (mounted) {
          setError(getErrorMessage(err));
          setLoading(false);
        }
      }
    })();

    return () => {
      mounted = false;
    };
  }, [repoName]);

  useEffect(() => {
    if (!owner) {
      return;
    }

    void loadIssues();
  }, [owner, loadIssues]);

  const filteredIssues = useMemo(() => {
    const normalizedSearch = search.trim().toLowerCase();

    return issues
      .filter((issue) => {
        const status = getIssueStatus(issue);

        if (filter === "open" && status !== "open") {
          return false;
        }

        if (filter === "closed" && status !== "closed") {
          return false;
        }

        return true;
      })
      .filter((issue) => {
        if (!normalizedSearch) {
          return true;
        }

        const haystack = [
          issue.title,
          issue.body,
          issue.author_id,
          issue.number !== undefined ? String(issue.number) : "",
          issue.id,
        ]
          .join(" ")
          .toLowerCase();

        return haystack.includes(normalizedSearch);
      })
      .sort((a, b) => {
        const aDate = new Date(a.updated_at || a.created_at).getTime();
        const bDate = new Date(b.updated_at || b.created_at).getTime();

        return bDate - aDate;
      });
  }, [issues, filter, search]);

  const openCount = useMemo(
    () =>
      issues.filter(
        (issue) => getIssueStatus(issue) === "open",
      ).length,
    [issues],
  );

  const closedCount = useMemo(
    () =>
      issues.filter(
        (issue) => getIssueStatus(issue) === "closed",
      ).length,
    [issues],
  );

  const handleToggleStatus = async (issue: Issue) => {
    if (!owner) {
      return;
    }

    const currentStatus = getIssueStatus(issue);
    const nextStatus =
      currentStatus === "open" ? "closed" : "open";

    setUpdatingId(issue.id);
    setError("");

    try {
      await issueService.updateIssueStatus(
        owner,
        repoName,
        issue.id,
        {
          status: nextStatus,
        },
      );

      await loadIssues(true);
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setUpdatingId(null);
    }
  };

  const handleDelete = async (issue: Issue) => {
    if (!owner) {
      return;
    }

    setDeletingId(issue.id);
    setError("");

    try {
      await issueService.deleteIssue(
        owner,
        repoName,
        issue.id,
      );

      setIssues((previous) =>
        previous.filter(
          (item) => item.id !== issue.id,
        ),
      );

      setConfirmDeleteId(null);
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setDeletingId(null);
    }
  };

  return (
    <AppShell>
      <div
        style={{
          width: "100%",
        }}
      >
        {/* Header */}
        <div className="issues-page-header" style={{ marginBottom: 24 }}>
          <div>
            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: 10,
              }}
            >
              <h1
                style={{
                  margin: 0,
                  fontSize: 25,
                  fontWeight: 700,
                  letterSpacing: "-0.02em",
                  color: "var(--fg)",
                }}
              >
                Issues
              </h1>

              <span
                style={{
                  fontSize: 12,
                  padding: "4px 8px",
                  borderRadius: 999,
                  background: "var(--bg-subtle)",
                  border: "1px solid var(--line)",
                  color: "var(--muted)",
                  fontFamily: "monospace",
                }}
              >
                {repoName}
              </span>
            </div>

            <p
              style={{
                margin: "7px 0 0",
                color: "var(--muted)",
                fontSize: 13,
              }}
            >
              Track bugs, engineering work, and repository discussions.
            </p>
          </div>

          <div className="issues-header-actions">
            {lastSyncedAt && (
              <span
                style={{
                  fontSize: 12,
                  color: "var(--muted)",
                  marginRight: 4,
                  whiteSpace: "nowrap",
                }}
              >
                Synced {formatRelativeDate(new Date(lastSyncedAt).toISOString())}
              </span>
            )}

            <button
              className="btn"
              onClick={() => void loadIssues(true, true)}
              disabled={refreshing || loading}
              style={{
                display: "flex",
                alignItems: "center",
                gap: 7,
                height: 36,
              }}
            >
              {refreshing ? (
                <Loader2
                  size={14}
                  className="spin"
                />
              ) : (
                <RefreshCw size={14} />
              )}

              Refresh
            </button>

            <a
              className="btn primary"
              href={`https://github.com/${owner || "kartikay1725"}/${repoName}/issues`}
              target="_blank"
              rel="noopener noreferrer"
              style={{
                display: "flex",
                alignItems: "center",
                gap: 7,
                height: 36,
                textDecoration: "none",
              }}
            >
              <ExternalLink size={14} />
              Open on GitHub
            </a>
          </div>
        </div>

        {/* Error */}
        {error && (
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: 9,
              padding: "11px 14px",
              marginBottom: 18,
              borderRadius: 8,
              background: "rgba(239,68,68,0.08)",
              border: "1px solid rgba(239,68,68,0.2)",
              color: "#f87171",
              fontSize: 13,
            }}
          >
            <AlertCircle size={15} />

            <span style={{ flex: 1 }}>
              {error}
            </span>

            <button
              onClick={() => setError("")}
              style={{
                background: "none",
                border: "none",
                color: "inherit",
                cursor: "pointer",
                padding: 2,
              }}
            >
              <X size={14} />
            </button>
          </div>
        )}

        {/* Stats */}
        <div className="stats-grid-3">
          <div
            style={{
              padding: "15px 17px",
              borderRadius: 10,
              border: "1px solid var(--line)",
              background:
                "linear-gradient(135deg, rgba(34,211,238,0.05), rgba(255,255,255,0.015))",
            }}
          >
            <div
              style={{
                color: "var(--muted)",
                fontSize: 11,
                fontWeight: 600,
                textTransform: "uppercase",
                letterSpacing: "0.08em",
              }}
            >
              Open
            </div>

            <div
              style={{
                marginTop: 5,
                fontSize: 24,
                fontWeight: 700,
                color: "var(--fg)",
              }}
            >
              {openCount}
            </div>
          </div>

          <div
            style={{
              padding: "15px 17px",
              borderRadius: 10,
              border: "1px solid var(--line)",
              background:
                "linear-gradient(135deg, rgba(167,139,250,0.05), rgba(255,255,255,0.015))",
            }}
          >
            <div
              style={{
                color: "var(--muted)",
                fontSize: 11,
                fontWeight: 600,
                textTransform: "uppercase",
                letterSpacing: "0.08em",
              }}
            >
              Closed
            </div>

            <div
              style={{
                marginTop: 5,
                fontSize: 24,
                fontWeight: 700,
                color: "var(--fg)",
              }}
            >
              {closedCount}
            </div>
          </div>

          <div
            style={{
              padding: "15px 17px",
              borderRadius: 10,
              border: "1px solid var(--line)",
              background:
                "linear-gradient(135deg, rgba(52,211,153,0.05), rgba(255,255,255,0.015))",
            }}
          >
            <div
              style={{
                color: "var(--muted)",
                fontSize: 11,
                fontWeight: 600,
                textTransform: "uppercase",
                letterSpacing: "0.08em",
              }}
            >
              Total
            </div>

            <div
              style={{
                marginTop: 5,
                fontSize: 24,
                fontWeight: 700,
                color: "var(--fg)",
              }}
            >
              {issues.length}
            </div>
          </div>
        </div>

        {/* Main card */}
        <div
          style={{
            border: "1px solid var(--line)",
            borderRadius: 10,
            overflow: "hidden",
            background: "var(--bg-card)",
          }}
        >
          {/* Toolbar */}
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: 12,
              padding: 12,
              borderBottom: "1px solid var(--line)",
              flexWrap: "wrap",
            }}
          >
            <div
              style={{
                flex: 1,
                minWidth: 220,
                position: "relative",
              }}
            >
              <Search
                size={15}
                style={{
                  position: "absolute",
                  left: 11,
                  top: "50%",
                  transform: "translateY(-50%)",
                  opacity: 0.45,
                  pointerEvents: "none",
                }}
              />

              <input
                className="input"
                value={search}
                onChange={(event) =>
                  setSearch(event.target.value)
                }
                placeholder="Search issues..."
                style={{
                  width: "100%",
                  height: 36,
                  paddingLeft: 34,
                }}
              />
            </div>

            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: 4,
                padding: 3,
                borderRadius: 7,
                background: "var(--bg-page)",
                border: "1px solid var(--line)",
              }}
            >
              <Filter
                size={13}
                style={{
                  marginLeft: 7,
                  marginRight: 2,
                  opacity: 0.45,
                }}
              />

              {(
                [
                  ["open", `Open ${openCount}`],
                  ["closed", `Closed ${closedCount}`],
                  ["all", `All ${issues.length}`],
                ] as const
              ).map(([value, label]) => (
                <button
                  key={value}
                  onClick={() => setFilter(value)}
                  style={{
                    border: "none",
                    borderRadius: 5,
                    padding: "6px 9px",
                    background:
                      filter === value
                        ? "var(--accent)"
                        : "transparent",
                    color:
                      filter === value
                        ? "#fff"
                        : "var(--muted)",
                    cursor: "pointer",
                    fontSize: 11,
                    fontWeight:
                      filter === value ? 600 : 500,
                  }}
                >
                  {label}
                </button>
              ))}
            </div>
          </div>

          {loading ? (
            <SkeletonIssueList count={6} />
          ) : filteredIssues.length === 0 ? (
            <div
              style={{
                minHeight: 320,
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                flexDirection: "column",
                gap: 10,
                padding: 30,
              }}
            >
              <div
                style={{
                  width: 48,
                  height: 48,
                  borderRadius: "50%",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  background: "var(--bg-subtle)",
                  border: "1px solid var(--line)",
                  color: "var(--muted)",
                }}
              >
                <MessageSquare size={20} />
              </div>

              <div
                style={{
                  fontWeight: 600,
                  fontSize: 14,
                  color: "var(--fg)",
                }}
              >
                {search
                  ? "No matching issues"
                  : filter === "open"
                    ? "No open issues"
                    : filter === "closed"
                      ? "No closed issues"
                      : "No issues yet"}
              </div>

              <div
                style={{
                  color: "var(--muted)",
                  fontSize: 12,
                  textAlign: "center",
                }}
              >
                {search
                  ? "Try a different search term."
                  : "Create the first issue for this repository."}
              </div>

              {!search && (
                <a
                  className="btn primary"
                  href={`https://github.com/${owner || "kartikay1725"}/${repoName}/issues`}
                  target="_blank"
                  rel="noopener noreferrer"
                  style={{
                    marginTop: 4,
                    display: "flex",
                    alignItems: "center",
                    gap: 6,
                    textDecoration: "none",
                  }}
                >
                  <ExternalLink size={14} />
                  Open on GitHub
                </a>
              )}
            </div>
          ) : (
            <div>
              {filteredIssues.map(
                (issue) => {
                  const status =
                    getIssueStatus(issue);
                  const isOpen =
                    status === "open";

                  const isUpdating =
                    updatingId === issue.id;
                  const isDeleting =
                    deletingId === issue.id;
                  const isConfirmingDelete =
                    confirmDeleteId === issue.id;

                  return (
                    <div
                      key={issue.id}
                      style={{
                        borderBottom:
                          "1px solid var(--line)",
                        padding:
                          "15px 16px",
                        transition:
                          "background 0.15s",
                      }}
                      className="issue-row"
                    >
                      <div
                        style={{
                          display: "flex",
                          alignItems:
                            "flex-start",
                          gap: 13,
                        }}
                      >
                        {/* Status icon */}
                        <div
                          style={{
                            paddingTop: 2,
                            flexShrink: 0,
                            color: isOpen
                              ? "var(--green)"
                              : "var(--muted)",
                          }}
                        >
                          {isOpen ? (
                            <CircleDot
                              size={18}
                            />
                          ) : (
                            <CheckCircle2
                              size={18}
                            />
                          )}
                        </div>

                        {/* Main */}
                        <div
                          style={{
                            flex: 1,
                            minWidth: 0,
                          }}
                        >
                          <button
                            onClick={() =>
                              router.push(
                                `/repositories/${repoName}/issues/${issue.id}`,
                              )
                            }
                            style={{
                              display:
                                "block",
                              width: "100%",
                              padding: 0,
                              margin: 0,
                              border: "none",
                              background:
                                "none",
                              color:
                                "var(--fg)",
                              textAlign:
                                "left",
                              cursor:
                                "pointer",
                              fontSize: 15,
                              fontWeight: 600,
                              lineHeight:
                                1.4,
                            }}
                          >
                            {issue.title}
                          </button>

                          <div
                            style={{
                              display:
                                "flex",
                              alignItems:
                                "center",
                              gap: 9,
                              flexWrap:
                                "wrap",
                              marginTop: 6,
                            }}
                          >
                            <span
                              style={{
                                color:
                                  "var(--muted)",
                                fontSize: 11,
                                fontFamily:
                                  "monospace",
                              }}
                            >
                              {issueNumber(
                                issue,
                              )}
                            </span>

                            <span
                              style={{
                                color:
                                  "var(--muted)",
                                opacity:
                                  0.7,
                                fontSize: 11,
                              }}
                            >
                              •
                            </span>

                            <span
                              style={{
                                color:
                                  "var(--muted)",
                                fontSize: 11,
                              }}
                            >
                              {isOpen
                                ? "Open"
                                : "Closed"}
                            </span>

                            <span
                              style={{
                                color:
                                  "var(--muted)",
                                opacity:
                                  0.7,
                                fontSize: 11,
                              }}
                            >
                              •
                            </span>

                            <span
                              style={{
                                color:
                                  "var(--muted)",
                                fontSize: 11,
                              }}
                            >
                              {issue.author_id}
                            </span>

                            <span
                              style={{
                                color:
                                  "var(--muted)",
                                opacity:
                                  0.7,
                                fontSize: 11,
                              }}
                            >
                              •
                            </span>

                            <span
                              title={formatDate(
                                issue.created_at,
                              )}
                              style={{
                                color:
                                  "var(--muted)",
                                fontSize: 11,
                              }}
                            >
                              opened{" "}
                              {formatRelativeDate(
                                issue.created_at,
                              )}
                            </span>
                          </div>

                          {issue.body && (
                            <div
                              style={{
                                marginTop: 8,
                                color:
                                  "var(--muted)",
                                fontSize: 12,
                                lineHeight:
                                  1.55,
                                display:
                                  "-webkit-box",
                                WebkitLineClamp:
                                  2,
                                WebkitBoxOrient:
                                  "vertical",
                                overflow:
                                  "hidden",
                                maxWidth:
                                  860,
                              }}
                            >
                              {issue.body}
                            </div>
                          )}
                        </div>

                        {/* Actions */}
                        <div
                          style={{
                            display:
                              "flex",
                            alignItems:
                              "center",
                            gap: 5,
                            flexShrink: 0,
                          }}
                        >
                          <button
                            onClick={() =>
                              void handleToggleStatus(
                                issue,
                              )
                            }
                            disabled={
                              isUpdating ||
                              isDeleting
                            }
                            title={
                              isOpen
                                ? "Close issue"
                                : "Reopen issue"
                            }
                            style={{
                              width: 32,
                              height: 32,
                              borderRadius:
                                6,
                              border:
                                "1px solid var(--line)",
                              background:
                                "var(--bg-page)",
                              color:
                                "var(--muted)",
                              cursor:
                                "pointer",
                              display:
                                "flex",
                              alignItems:
                                "center",
                              justifyContent:
                                "center",
                              opacity:
                                isUpdating ||
                                isDeleting
                                  ? 0.45
                                  : 1,
                            }}
                          >
                            {isUpdating ? (
                              <Loader2
                                size={14}
                                className="spin"
                              />
                            ) : isOpen ? (
                              <Check
                                size={14}
                              />
                            ) : (
                              <CircleDot
                                size={14}
                              />
                            )}
                          </button>

                          <button
                            onClick={() =>
                              setConfirmDeleteId(
                                issue.id,
                              )
                            }
                            disabled={
                              isUpdating ||
                              isDeleting
                            }
                            title="Delete issue"
                            style={{
                              width: 32,
                              height: 32,
                              borderRadius:
                                6,
                              border:
                                "1px solid var(--line)",
                              background:
                                "var(--bg-page)",
                              color:
                                "#f87171",
                              cursor:
                                "pointer",
                              display:
                                "flex",
                              alignItems:
                                "center",
                              justifyContent:
                                "center",
                              opacity:
                                isUpdating ||
                                isDeleting
                                  ? 0.45
                                  : 1,
                            }}
                          >
                            {isDeleting ? (
                              <Loader2
                                size={14}
                                className="spin"
                              />
                            ) : (
                              <Trash2
                                size={14}
                              />
                            )}
                          </button>
                        </div>
                      </div>

                      {/* Delete confirmation */}
                      {isConfirmingDelete && (
                        <div
                          style={{
                            marginTop: 12,
                            marginLeft: 31,
                            padding:
                              "10px 12px",
                            borderRadius:
                              7,
                            background:
                              "rgba(239,68,68,0.06)",
                            border:
                              "1px solid rgba(239,68,68,0.18)",
                            display:
                              "flex",
                            alignItems:
                              "center",
                            gap: 10,
                          }}
                        >
                          <Trash2
                            size={14}
                            style={{
                              color:
                                "#f87171",
                              flexShrink: 0,
                            }}
                          />

                          <span
                            style={{
                              flex: 1,
                              color:
                                "var(--fg)",
                              fontSize:
                                12,
                            }}
                          >
                            Delete this issue permanently?
                          </span>

                          <button
                            className="btn"
                            onClick={() =>
                              setConfirmDeleteId(
                                null,
                              )
                            }
                            disabled={
                              isDeleting
                            }
                            style={{
                              height: 30,
                              fontSize:
                                11,
                            }}
                          >
                            Cancel
                          </button>

                          <button
                            className="btn"
                            onClick={() =>
                              void handleDelete(
                                issue,
                              )
                            }
                            disabled={
                              isDeleting
                            }
                            style={{
                              height: 30,
                              fontSize:
                                11,
                              background:
                                "#7f1d1d",
                              borderColor:
                                "#991b1b",
                              color:
                                "#fff",
                            }}
                          >
                            {isDeleting
                              ? "Deleting..."
                              : "Delete"}
                          </button>
                        </div>
                      )}
                    </div>
                  );
                },
              )}
            </div>
          )}
        </div>
      </div>

      <style jsx>{`
        .issue-row:hover {
          background: rgba(255, 255, 255, 0.018);
        }

        .spin {
          animation: issue-spin 1s linear infinite;
        }

        @keyframes issue-spin {
          from {
            transform: rotate(0deg);
          }

          to {
            transform: rotate(360deg);
          }
        }
      `}</style>
    </AppShell>
  );
}