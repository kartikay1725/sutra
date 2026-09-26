"use client";

import React, { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import { searchService, type SearchResult } from "@/lib/search";
import { I } from "../lib/icons";
import { apiAuth } from "../lib/api";
import { TaskModal } from "@/components/TaskModal";
import { ConfirmModal } from "@/components/ConfirmModal";
import {
  notificationService,
  type NotificationItem,
} from "@/lib/notifications";
import NewTaskModal from "@/components/NewTaskModal";
import { taskService } from "@/lib/tasks";
import {
  issueService,
  type Issue,
  type IssueResolution,
} from "@/lib/issues";
import {
  Badge,
  Btn,
  Card,
  PageHead,
  Pipeline,
  Stat,
  Skeleton,
  SkeletonRepoOverview,
  SkeletonRepoSettings,
} from "./shell";
import { authService } from "../lib/auth";
import {
  repositoryService,
  type Repository,
} from "../lib/repositories";
import {
  branchProtectionService,
  type BranchProtectionRule,
} from "../lib/branch_protection";
import {
  insightsService,
  type InsightsData,
} from "../lib/insights";
import { clientCache, CACHE_TTL } from "../lib/cache";
import { GitHubSyncButton } from "./GitHubSyncButton";

/* -------------------------------------------------------------------------- */
/* Existing screen implementations                                            */
/* -------------------------------------------------------------------------- */

const repos = [
  ["sutra-core", "Autonomous engineering runtime", "12 changes", "2h ago", "aqua"],
  ["agent-sdk", "Agent orchestration primitives", "4 changes", "5h ago", "violet"],
  ["dashboard", "SUTRA developer workspace", "8 changes", "1d ago", "green"],
  ["knowledge-engine", "Semantic code graph", "3 changes", "2d ago", "aqua"],
  ["infra", "Deployment and environment config", "1 change", "3d ago", "amber"],
  ["docs", "Product documentation", "0 changes", "5d ago", "green"],
];

function Repo({
  r,
}: {
  r: string[];
}) {
  return (
    <Link
      href="/repositories/sutra-core"
      className="card repo-card"
    >
      <div className="row">
        <div className="repo-name">{r[0]}</div>
        <Badge tone={r[4]}>{r[3]}</Badge>
      </div>

      <div className="repo-desc">{r[1]}</div>

      <div className="row">
        <span className="meta">{r[2]}</span>
        <span className="meta">main · 98%</span>
      </div>
    </Link>
  );
}

function ActivityList() {
  return (
    <div className="list">
      <div className="activity">
        <span className="activity-dot" />
        <div>
          <p>
            <b>Atlas</b> opened Change #482
          </p>
          <span>sutra-core · 2 minutes ago</span>
        </div>
      </div>

      <div className="activity">
        <span className="activity-dot" />
        <div>
          <p>
            CI passed for <b>agent-sdk</b>
          </p>
          <span>All 184 tests passed · 8 minutes ago</span>
        </div>
      </div>

      <div className="activity">
        <span className="activity-dot" />
        <div>
          <p>
            <b>You</b> approved a deployment
          </p>
          <span>staging · 14 minutes ago</span>
        </div>
      </div>

      <div className="activity">
        <span className="activity-dot" />
        <div>
          <p>Security scan completed</p>
          <span>2 low findings · 21 minutes ago</span>
        </div>
      </div>
    </div>
  );
}

export function Dashboard() {
  type DashboardCommit = {
    sha: string;
    short_sha: string;
    author_name: string;
    author_email: string;
    committed_at: number;
    subject: string;
    repository: string;
    owner: string;
  };

  const [repositories, setRepositories] = useState<
    Repository[]
  >([]);

  const [recentCommits, setRecentCommits] =
    useState<DashboardCommit[]>([]);

  const [loading, setLoading] =
    useState(true);

  const [error, setError] =
    useState<string | null>(null);

  const formatRelativeTime = (
    timestamp: number | string,
  ) => {
    const value =
      typeof timestamp === "string"
        ? new Date(timestamp).getTime()
        : timestamp * 1000;

    if (!Number.isFinite(value)) {
      return "Unknown time";
    }

    const diff = Math.max(
      0,
      Date.now() - value,
    );

    const minutes = Math.floor(
      diff / 60000,
    );

    if (minutes < 1) {
      return "just now";
    }

    if (minutes < 60) {
      return `${minutes}m ago`;
    }

    const hours = Math.floor(
      minutes / 60,
    );

    if (hours < 24) {
      return `${hours}h ago`;
    }

    const days = Math.floor(
      hours / 24,
    );

    if (days < 30) {
      return `${days}d ago`;
    }

    const months = Math.floor(
      days / 30,
    );

    return `${months}mo ago`;
  };

  useEffect(() => {
    let cancelled = false;

    const loadDashboard = async () => {
      try {
        setLoading(true);
        setError(null);

        const repos =
          await repositoryService.listRepositories();

        if (cancelled) {
          return;
        }

        setRepositories(repos);

        const commitResults =
          await Promise.all(
            repos.slice(0, 10).map(
              async (repo) => {
                if (!repo.owner) {
                  return [];
                }

                try {
                  const response =
                    await apiAuth<{
                      ref: string;
                      head: string;
                      commits: Array<{
                        sha: string;
                        short_sha: string;
                        author_name: string;
                        author_email: string;
                        committed_at: number;
                        subject: string;
                      }>;
                    }>(
                      `/v1/repositories/${encodeURIComponent(
                        repo.owner,
                      )}/${encodeURIComponent(
                        repo.name,
                      )}/commits?ref=${encodeURIComponent(
                        repo.default_branch ||
                        "main",
                      )}&limit=5`,
                    );

                  return (
                    response.commits || []
                  ).map(
                    (commit) => ({
                      ...commit,
                      repository:
                        repo.name,
                      owner:
                        repo.owner || "",
                    }),
                  );
                } catch (commitError) {
                  console.warn(
                    `Unable to load commits for ${repo.name}`,
                    commitError,
                  );

                  return [];
                }
              },
            ),
          );

        if (cancelled) {
          return;
        }

        const commits =
          commitResults
            .flat()
            .sort(
              (a, b) =>
                b.committed_at -
                a.committed_at,
            )
            .slice(0, 12);

        setRecentCommits(commits);
      } catch (err: any) {
        console.error(
          "Failed to load dashboard:",
          err,
        );

        if (!cancelled) {
          setError(
            err?.detail ||
            err?.message ||
            "Failed to load workspace data",
          );
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    };

    void loadDashboard();

    return () => {
      cancelled = true;
    };
  }, []);

  const latestRepositories =
    repositories.slice(0, 4);

  return (
    <>
      <PageHead
        eyebrow="Personal workspace"
        title="Your workspace"
        sub={
          loading
            ? "Loading your engineering activity…"
            : `${repositories.length} ${repositories.length === 1
              ? "repository"
              : "repositories"
            } available in your workspace.`
        }
        action={
          <>
            <Btn>Customize</Btn>


          </>
        }
      />

      <Pipeline />

      {error && (
        <Card
          style={{
            marginBottom: 14,
            borderColor:
              "rgba(255,127,146,.22)",
          }}
        >
          <div className="card-pad">
            <div
              className="sub"
              style={{
                color: "#ff8fa0",
              }}
            >
              {error}
            </div>
          </div>
        </Card>
      )}

      <div className="kpi-strip">
        <Card>
          <div className="stat">
            <div className="eyebrow">
              Repositories
            </div>

            <div className="num">
              {loading
                ? "—"
                : repositories.length}
            </div>

            <div className="delta">
              Actual workspace repositories
            </div>
          </div>
        </Card>

        <Card>
          <div className="stat">
            <div className="eyebrow">
              Recent commits
            </div>

            <div className="num">
              {loading
                ? "—"
                : recentCommits.length}
            </div>

            <div className="delta">
              Loaded from Git history
            </div>
          </div>
        </Card>

        <Card>
          <div className="stat">
            <div className="eyebrow">
              Active runs
            </div>

            <div className="num">—</div>

            <div className="sub">
              Agent-run API is not connected
              to the workspace dashboard yet.
            </div>
          </div>
        </Card>

        <Card>
          <div className="stat">
            <div className="eyebrow">
              Deployments
            </div>

            <div className="num">—</div>

            <div className="sub">
              Deployment metrics are not
              exposed by the current dashboard API.
            </div>
          </div>
        </Card>
      </div>

      <div className="grid g2">
        <Card>
          <div className="card-head">
            <div>
              <div className="h2">
                Your repositories
              </div>

              <div className="sub">
                Live data from your SUTRA workspace
              </div>
            </div>

            <Link
              href="/repositories"
              className="badge aqua"
            >
              View all
            </Link>
          </div>

          {loading ? (
            <div className="card-pad">
              <div className="sub">
                Loading repositories…
              </div>
            </div>
          ) : latestRepositories.length ===
            0 ? (
            <div className="card-pad">
              <div className="eyebrow">
                No repositories
              </div>

              <div className="h2">
                Your workspace is empty.
              </div>

              <div
                className="sub"
                style={{
                  marginTop: 8,
                  marginBottom: 16,
                }}
              >
                Create your first repository
                to start building with SUTRA.
              </div>

            </div>
          ) : (
            <div
              className="grid g2"
              style={{ padding: 14 }}
            >
              {latestRepositories.map(
                (repo) => (
                  <Link
                    key={repo.id}
                    href={`/repositories/${encodeURIComponent(
                      repo.name,
                    )}`}
                    className="card repo-card"
                  >
                    <div className="row">
                      <div className="repo-name">
                        {repo.name}
                      </div>

                      <Badge
                        tone={
                          repo.visibility ===
                            "private"
                            ? "violet"
                            : "green"
                        }
                      >
                        {repo.visibility}
                      </Badge>
                    </div>

                    <div className="repo-desc">
                      {repo.description ||
                        "No repository description."}
                    </div>

                    <div className="row">
                      <span className="meta">
                        {repo.default_branch ||
                          "No branch"}
                      </span>

                      <span className="meta">
                        {formatRelativeTime(
                          repo.updated_at,
                        )}
                      </span>
                    </div>
                  </Link>
                ),
              )}
            </div>
          )}
        </Card>

        <Card>
          <div className="card-head">
            <div>
              <div className="h2">
                Recent activity
              </div>

              <div className="sub">
                Real commits across your repositories
              </div>
            </div>

            <Badge tone="aqua">
              Git
            </Badge>
          </div>

          {loading ? (
            <div className="card-pad">
              <div className="sub">
                Loading activity…
              </div>
            </div>
          ) : recentCommits.length ===
            0 ? (
            <div className="card-pad">
              <div className="sub">
                No recent commits found.
              </div>
            </div>
          ) : (
            <div className="list">
              {recentCommits.map(
                (commit) => (
                  <Link
                    href={`/repositories/${encodeURIComponent(
                      commit.repository,
                    )}/code?ref=${encodeURIComponent(
                      repositories.find(
                        (repo) =>
                          repo.name ===
                          commit.repository,
                      )?.default_branch ||
                      "main",
                    )}`}
                    className="activity"
                    key={`${commit.repository}-${commit.sha}`}
                  >
                    <span className="activity-dot" />

                    <div
                      style={{
                        minWidth: 0,
                        flex: 1,
                      }}
                    >
                      <p>
                        <b>
                          {commit.subject ||
                            "No commit message"}
                        </b>
                      </p>

                      <span>
                        {commit.repository} ·{" "}
                        {commit.author_name ||
                          "Unknown author"}{" "}
                        ·{" "}
                        {formatRelativeTime(
                          commit.committed_at,
                        )}
                      </span>
                    </div>

                    <span className="code meta">
                      {commit.short_sha}
                    </span>
                  </Link>
                ),
              )}
            </div>
          )}
        </Card>
      </div>

      <div
        className="grid g3"
        style={{ marginTop: 14 }}
      >
        <Card>
          <div className="stat">
            <div className="eyebrow">
              Open changes
            </div>

            <div className="num">—</div>

            <div className="sub">
              Change API is not connected to
              the dashboard yet.
            </div>
          </div>
        </Card>

        <Card>
          <div className="stat">
            <div className="eyebrow">
              CI pass rate
            </div>

            <div className="num">—</div>

            <div className="sub">
              CI metrics are not currently
              exposed by the workspace API.
            </div>
          </div>
        </Card>

        <Card>
          <div className="stat">
            <div className="eyebrow">
              Security findings
            </div>

            <div className="num">—</div>

            <div className="sub">
              Security metrics are not currently
              exposed by the workspace API.
            </div>
          </div>
        </Card>
      </div>
    </>
  );
}
/* -------------------------------------------------------------------------- */
/* Generic screens                                                            */
/* -------------------------------------------------------------------------- */

export function MyWork() {
  type WorkRow = {
    id: string;
    title: string;
    repo_name: string;
    status: string;
    updated_at: string;
    type: "task" | "pr";
    prId?: string;
  };

  const router = useRouter();
  const [workItems, setWorkItems] = useState<WorkRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadWork = async () => {
    try {
      setLoading(true);
      setError(null);

      const [meWorkRes, allTasksRes, prsRes, repositories] = await Promise.all([
        apiAuth<
          Array<{
            id: string;
            title: string;
            repo_name: string;
            status: string;
            updated_at: string;
          }>
        >("/v1/me/work").catch(() => []),
        taskService.listAllTasks().catch(() => []),
        apiAuth<
          Array<{
            id: string;
            repository_id: string;
            author_id: string;
            source_change_id: string;
            title: string;
            description: string | null;
            target_branch: string;
            status: string;
            created_at: string;
            updated_at: string;
            merged_at: string | null;
            closed_at: string | null;
          }>
        >("/v1/pull-requests?limit=50").catch(() => []),
        repositoryService.listRepositories().catch(() => []),
      ]);

      const repoById = new Map(
        repositories.map((repo) => [repo.id, repo]),
      );

      const taskMap = new Map<string, WorkRow>();

      // 1. Add tasks from /v1/me/work
      for (const task of meWorkRes) {
        taskMap.set(task.id, {
          id: task.id,
          title: task.title,
          repo_name: task.repo_name || "Repository",
          status: task.status,
          updated_at: task.updated_at,
          type: "task",
        });
      }

      // 2. Add and enrich with workspace tasks from /v1/tasks
      for (const task of allTasksRes) {
        if (!taskMap.has(task.id)) {
          const repo = repoById.get(task.repository_id);
          taskMap.set(task.id, {
            id: task.id,
            title: task.title,
            repo_name: repo?.name || "Repository",
            status: task.status,
            updated_at: task.updated_at || task.created_at,
            type: "task",
          });
        }
      }

      // 3. Add pull requests
      const prRows: WorkRow[] = prsRes.map((pr) => {
        const repository = repoById.get(pr.repository_id);

        return {
          id: `pr-${pr.id}`,
          prId: pr.id,
          title: pr.title,
          type: "pr",
          repo_name:
            repository?.name ||
            "Repository",
          status: pr.status,
          updated_at: pr.updated_at || pr.created_at,
        };
      });

      const combined = [
        ...Array.from(taskMap.values()),
        ...prRows,
      ].sort(
        (a, b) =>
          new Date(b.updated_at).getTime() -
          new Date(a.updated_at).getTime(),
      );

      setWorkItems(combined);
    } catch (err: any) {
      console.error(
        "Failed to load My Work:",
        err,
      );

      setError(
        err?.detail ||
        err?.message ||
        "Failed to load your work",
      );
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void loadWork();
  }, []);

  const assignedCount = workItems.filter(
    (item) => item.type === "task",
  ).length;

  const reviewCount = workItems.filter(
    (item) =>
      item.type === "pr" &&
      [
        "open",
        "review",
        "awaiting_review",
        "pending_review",
      ].includes(
        item.status.toLowerCase(),
      ),
  ).length;

  const prCount = workItems.filter(
    (item) => item.type === "pr",
  ).length;

  const blockedCount = workItems.filter(
    (item) =>
      ["blocked", "failed", "rejected"].includes(
        item.status.toLowerCase(),
      ),
  ).length;

  const statusLabel = (status: string) =>
    status
      .replaceAll("_", " ")
      .replace(/\b\w/g, (char) =>
        char.toUpperCase(),
      );

  const statusTone = (
    status: string,
  ): string => {
    const normalized =
      status.toLowerCase();

    if (
      ["done", "completed", "merged"].includes(
        normalized,
      )
    ) {
      return "green";
    }

    if (
      [
        "in_progress",
        "running",
        "open",
        "review",
        "awaiting_review",
        "pending_review",
      ].includes(normalized)
    ) {
      return "aqua";
    }

    if (
      ["blocked", "failed", "rejected"].includes(
        normalized,
      )
    ) {
      return "red";
    }

    return "amber";
  };

  const openTask = (
    item: WorkRow,
  ) => {
    if (item.repo_name && item.repo_name !== "Repository") {
      router.push(`/repositories/${encodeURIComponent(item.repo_name)}`);
      return;
    }

    router.push("/repositories");
  };

  return (
    <>
      <PageHead
        eyebrow="Personal queue"
        title="My Work"
        sub="Your real tasks and pull requests from SUTRA."
      />

      {error && (
        <Card
          style={{
            marginBottom: 16,
            borderColor:
              "rgba(255,127,146,.22)",
          }}
        >
          <div className="card-pad">
            <div
              className="sub"
              style={{
                color: "#ff8fa0",
              }}
            >
              {error}
            </div>
          </div>
        </Card>
      )}

      <div
        style={{
          display: "grid",
          gridTemplateColumns:
            "repeat(auto-fill, minmax(180px, 1fr))",
          gap: 14,
          marginBottom: 20,
        }}
      >
        <Stat
          label="Assigned"
          value={loading ? "—" : assignedCount.toString()}
        />

        <Stat
          label="In review"
          value={loading ? "—" : reviewCount.toString()}
        />

        <Stat
          label="PRs"
          value={loading ? "—" : prCount.toString()}
        />

        <Stat
          label="Blocked"
          value={loading ? "—" : blockedCount.toString()}
        />
      </div>

      <Card>
        <div className="card-head">
          <div>
            <div className="h2">
              Priority queue
            </div>

            <div className="sub">
              Tasks and pull requests currently connected
              to your account.
            </div>
          </div>
        </div>

        <div className="list">
          {loading ? (
            <div
              className="muted"
              style={{ padding: 18 }}
            >
              Loading your work…
            </div>
          ) : workItems.length === 0 ? (
            <div
              className="muted"
              style={{ padding: 18 }}
            >
              Your queue is empty.
            </div>
          ) : (
            workItems.map((item) => (
              <div
                key={item.id}
                className="list-row"
                style={{
                  cursor: "pointer",
                  padding: "14px 20px",
                  gap: 14,
                }}
                onClick={() =>
                  openTask(item)
                }
              >
                <div
                  className="avatar"
                  style={{
                    width: 30,
                    height: 30,
                  }}
                >
                  {item.type === "pr" ? (
                    <I.GitPullRequest size={14} />
                  ) : (
                    <I.ListTodo size={14} />
                  )}
                </div>

                <div
                  style={{
                    flex: 1,
                    minWidth: 0,
                  }}
                >
                  <div className="title-sm">
                    {item.title}
                  </div>

                  <div className="meta">
                    {item.repo_name} ·{" "}
                    {item.type === "pr"
                      ? "pull request"
                      : "task"}{" "}
                    · updated{" "}
                    {new Date(
                      item.updated_at,
                    ).toLocaleString()}
                  </div>
                </div>

                <Badge
                  tone={statusTone(
                    item.status,
                  )}
                >
                  {statusLabel(
                    item.status,
                  )}
                </Badge>

                <I.ChevronRight
                  size={15}
                  className="muted"
                />
              </div>
            ))
          )}
        </div>
      </Card>
    </>
  );
}
export function Explore() {
  return (
    <>
      <PageHead
        eyebrow="Network"
        title="Explore"
        sub="Discover active repositories, agents, and engineering patterns across SUTRA."
      />

      <div className="grid g3">
        <Card>
          <div className="card-pad">
            <div className="eyebrow">Trending repository</div>
            <div className="h2">open-agent-protocol</div>
            <p className="sub">
              A portable interface for autonomous coding agents.
            </p>
            <div className="row">
              <Badge tone="aqua">1.2k stars</Badge>
              <span className="meta">+84 today</span>
            </div>
          </div>
        </Card>

        <Card>
          <div className="card-pad">
            <div className="eyebrow">Featured agent</div>
            <div className="h2">Atlas</div>
            <p className="sub">
              High-confidence implementation and refactoring agent.
            </p>
            <Badge tone="violet">4.8k runs</Badge>
          </div>
        </Card>

        <Card>
          <div className="card-pad">
            <div className="eyebrow">Discussion</div>
            <div className="h2">
              What should an agent be allowed to merge?
            </div>
            <p className="sub">
              218 developers are discussing approval boundaries.
            </p>
          </div>
        </Card>
      </div>

      <div
        className="grid g2"
        style={{ marginTop: 14 }}
      >
        <Card>
          <div className="card-head">
            <div className="h2">Recently active</div>
          </div>

          <div className="list">
            {repos.map((r) => (
              <Repo key={r[0]} r={r} />
            ))}
          </div>
        </Card>

        <Card>
          <div className="card-head">
            <div className="h2">Engineering signals</div>
          </div>

          <div className="card-pad">
            <div className="eyebrow">Fastest growing</div>
            <div className="h2">
              Agent-assisted review
            </div>
            <div
              className="sub"
              style={{ margin: "7px 0 18px" }}
            >
              Teams using automated review are resolving
              changes 31% faster.
            </div>

            <div className="progress">
              <span style={{ width: "74%" }} />
            </div>
          </div>
        </Card>
      </div>
    </>
  );
}

export function Repositories() {
  const [repositories, setRepositories] = useState<Repository[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [githubConnected, setGithubConnected] = useState(false);

  const [currentPage, setCurrentPage] = useState(1);
  const [isMobile, setIsMobile] = useState(false);

  useEffect(() => {
    const checkMobile = () => setIsMobile(window.innerWidth <= 640);
    checkMobile();
    window.addEventListener("resize", checkMobile);
    return () => window.removeEventListener("resize", checkMobile);
  }, []);

  const loadRepositories = async () => {
    try {
      setLoading(true);
      setError(null);

      const rows = await repositoryService.listRepositories();
      // Sort alphabetically by repository name (case-insensitive) for both desktop and mobile
      const sorted = [...rows].sort((a, b) =>
        (a.name || "").localeCompare(b.name || "", undefined, { sensitivity: "base" })
      );
      setRepositories(sorted);
    } catch (err: any) {
      console.error("Failed to load repositories:", err);
      setError(
        err?.detail ||
        err?.message ||
        "Failed to load repositories",
      );
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    let cancelled = false;

    const loadGithubStatus = async () => {
      try {
        const { integrationService } = await import("../lib/integrations");
        const status = await integrationService.getGitHubStatus();
        if (!cancelled) setGithubConnected(status.connected);
      } catch {
        // GitHub status is non-critical — don't block repo listing
      }
    };

    void loadRepositories();
    void loadGithubStatus();

    const handleSynced = () => {
      void loadRepositories();
    };
    window.addEventListener("sutra:github-synced", handleSynced);

    return () => {
      cancelled = true;
      window.removeEventListener("sutra:github-synced", handleSynced);
    };
  }, []);

  const handleConnectGitHub = async () => {
    try {
      const { integrationService } = await import("../lib/integrations");
      const { redirect_url } = await integrationService.getGitHubConnectUrl();
      window.location.href = redirect_url;
    } catch (err: any) {
      console.error("GitHub connect failed:", err);
    }
  };

  return (
    <>
      <PageHead
        eyebrow="Workspace"
        title="Repositories"
        sub="Connected codebases, branch policies, and governance controls."
        action={
          <div className="row" style={{ gap: 8, alignItems: "center" }}>
            <GitHubSyncButton onSynced={() => void loadRepositories()} />
            {!githubConnected && (
              <Btn onClick={handleConnectGitHub}>
                <I.GitBranch size={14} />
                Connect GitHub
              </Btn>
            )}
          </div>
        }
      />

      {loading && (
        <Card>
          <div className="card-pad">
            <div className="sub">
              Loading your repositories…
            </div>
          </div>
        </Card>
      )}

      {!loading && error && (
        <Card>
          <div className="card-pad">
            <div
              className="sub"
              style={{ color: "#ff8fa0" }}
            >
              {error}
            </div>
          </div>
        </Card>
      )}

      {!loading &&
        !error &&
        repositories.length === 0 && (
          <Card>
            <div
              className="card-pad"
              style={{
                textAlign: "center",
                paddingTop: 50,
                paddingBottom: 50,
              }}
            >
              <div className="eyebrow">
                No repositories
              </div>

              <div className="h2">
                Your workspace is empty.
              </div>

              <div
                className="sub"
                style={{
                  marginTop: 8,
                  marginBottom: 18,
                }}
              >
                Connect GitHub to discover existing repositories or synchronize newly added repositories.
              </div>

              <div className="row" style={{ justifyContent: "center", gap: 10 }}>
                {githubConnected ? (
                  <GitHubSyncButton onSynced={() => void loadRepositories()} />
                ) : (
                  <Btn onClick={handleConnectGitHub}>
                    <I.GitBranch size={14} />
                    Connect GitHub
                  </Btn>
                )}
              </div>
            </div>
          </Card>
        )}

      {!loading &&
        !error &&
        repositories.length > 0 &&
        (() => {
          const pageSize = 12;
          const totalPages = Math.ceil(repositories.length / pageSize);
          const safeCurrentPage = Math.min(currentPage, totalPages || 1);
          const startIndex = (safeCurrentPage - 1) * pageSize;
          const visibleRepos = repositories.slice(startIndex, startIndex + pageSize);

          return (
            <>
              <div className="grid g3">
                {visibleRepos.map((repo) => (
                  <Link
                    key={repo.id}
                    href={`/repositories/${encodeURIComponent(
                      repo.name,
                    )}`}
                    className="card interactive"
                    style={{
                      padding: 16,
                      display: "flex",
                      flexDirection: "column",
                      justifyContent: "space-between",
                      gap: 12,
                    }}
                  >
                    <div>
                      <div
                        className="row"
                        style={{
                          justifyContent: "space-between",
                          alignItems: "center",
                          marginBottom: 8,
                        }}
                      >
                        <span
                          className="mono"
                          style={{
                            fontSize: 14,
                            fontWeight: 600,
                            color: "var(--fg)",
                          }}
                        >
                          {repo.name}
                        </span>

                        <Badge
                          tone={
                            repo.visibility === "public"
                              ? "green"
                              : "neutral"
                          }
                        >
                          {repo.visibility || "private"}
                        </Badge>
                      </div>

                      <div
                        className="sub"
                        style={{
                          fontSize: 13,
                          lineHeight: 1.45,
                          minHeight: 38,
                        }}
                      >
                        {repo.description || "No description provided."}
                      </div>
                    </div>

                    <div
                      className="row"
                      style={{
                        justifyContent: "space-between",
                        alignItems: "center",
                        fontSize: 12,
                        color: "var(--muted)",
                        paddingTop: 10,
                        borderTop: "1px solid var(--line)",
                      }}
                    >
                      <span className="mono">
                        {repo.default_branch || "main"}
                      </span>

                      <span>
                        {(repo as any).provider_type === "github" || (repo as any).provider === "github"
                          ? "GitHub"
                          : (repo as any).provider_owner || repo.owner
                            ? `@${(repo as any).provider_owner || repo.owner}`
                            : "Owned by you"}
                      </span>
                    </div>
                  </Link>
                ))}
              </div>

              {/* Repositories Pagination (12 per page) */}
              {totalPages > 1 && (
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
                    Page {safeCurrentPage} of {totalPages} ({repositories.length} repositories)
                  </span>
                  <div style={{ display: "flex", gap: 8 }}>
                    <Btn
                      disabled={safeCurrentPage <= 1}
                      onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
                    >
                      <I.ChevronLeft size={14} /> Previous
                    </Btn>
                    <Btn
                      disabled={safeCurrentPage >= totalPages}
                      onClick={() => setCurrentPage((p) => Math.min(totalPages, p + 1))}
                    >
                      Next <I.ChevronRight size={14} />
                    </Btn>
                  </div>
                </div>
              )}
            </>
          );
        })()}
    </>
  );
}
export function Notifications() {
  const [notifications, setNotifications] = useState<
    NotificationItem[]
  >([]);
  const [loading, setLoading] = useState(true);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [markingAll, setMarkingAll] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadNotifications = async () => {
    try {
      setLoading(true);
      setError(null);

      const rows =
        await notificationService.getNotifications();

      setNotifications(rows);
    } catch (err) {
      console.error(
        "Failed to load notifications",
        err,
      );

      setError(
        err instanceof Error
          ? err.message
          : "Failed to load notifications.",
      );
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void loadNotifications();
  }, []);

  const unreadCount = notifications.filter(
    (notification) => !notification.is_read,
  ).length;

  const handleMarkRead = async (
    notification: NotificationItem,
  ) => {
    if (notification.is_read || busyId) {
      return;
    }

    try {
      setBusyId(notification.id);
      setError(null);

      await notificationService.markAsRead(
        notification.id,
      );

      setNotifications((current) =>
        current.map((item) =>
          item.id === notification.id
            ? {
              ...item,
              is_read: true,
            }
            : item,
        ),
      );
    } catch (err) {
      console.error(
        "Failed to mark notification as read",
        err,
      );

      setError(
        err instanceof Error
          ? err.message
          : "Failed to mark notification as read.",
      );
    } finally {
      setBusyId(null);
    }
  };

  const handleMarkAllRead = async () => {
    if (markingAll || unreadCount === 0) {
      return;
    }

    try {
      setMarkingAll(true);
      setError(null);

      await notificationService.markAllAsRead();

      setNotifications((current) =>
        current.map((item) => ({
          ...item,
          is_read: true,
        })),
      );
    } catch (err) {
      console.error(
        "Failed to mark all notifications as read",
        err,
      );

      setError(
        err instanceof Error
          ? err.message
          : "Failed to mark all notifications as read.",
      );
    } finally {
      setMarkingAll(false);
    }
  };

  const handleOpen = async (
    notification: NotificationItem,
  ) => {
    if (!notification.is_read) {
      await handleMarkRead(notification);
    }

    if (notification.link) {
      window.location.href = notification.link;
    }
  };

  return (
    <>
      <PageHead
        eyebrow="Inbox"
        title="Notifications"
        sub="Review requests, agent events, CI failures, mentions, and deployment signals."
        action={
          <Btn
            onClick={() => void handleMarkAllRead()}
            disabled={
              markingAll || unreadCount === 0
            }
          >
            {markingAll
              ? "Marking..."
              : "Mark all read"}
          </Btn>
        }
      />

      {error && (
        <Card style={{ marginBottom: 16 }}>
          <div className="meta" style={{ color: "#f87171" }}>
            {error}
          </div>
        </Card>
      )}

      <Card>
        <div className="card-head">
          <div className="h2">
            {notifications.length === 0
              ? "Notifications"
              : "Recent notifications"}
          </div>

          <Badge
            tone={
              loading
                ? "gray"
                : unreadCount > 0
                  ? "amber"
                  : "aqua"
            }
          >
            {loading ? "Loading..." : `${unreadCount} unread`}
          </Badge>
        </div>

        {loading ? (
          <div
            className="meta"
            style={{ padding: "24px 0" }}
          >
            Loading notifications...
          </div>
        ) : notifications.length === 0 ? (
          <div
            className="meta"
            style={{
              padding: "32px 0",
              textAlign: "center",
            }}
          >
            You're all caught up. No notifications yet.
          </div>
        ) : (
          <div className="list">
            {notifications.map(
              (notification) => (
                <div
                  className="list-row"
                  key={notification.id}
                  onClick={() =>
                    void handleOpen(notification)
                  }
                  style={{
                    cursor: notification.link
                      ? "pointer"
                      : "default",
                    opacity:
                      busyId === notification.id
                        ? 0.6
                        : 1,
                  }}
                >
                  <div
                    className="avatar"
                    style={{
                      width: 27,
                      height: 27,
                    }}
                  >
                    {notification.type
                      .slice(0, 1)
                      .toUpperCase() || "S"}
                  </div>

                  <div
                    style={{
                      flex: 1,
                      minWidth: 0,
                    }}
                  >
                    <div className="title-sm">
                      {notification.title}
                    </div>

                    {notification.message && (
                      <div
                        className="meta"
                        style={{
                          marginTop: 3,
                        }}
                      >
                        {notification.message}
                      </div>
                    )}

                    <div
                      className="meta"
                      style={{
                        marginTop: 4,
                      }}
                    >
                      {new Date(
                        notification.created_at,
                      ).toLocaleString()}
                    </div>
                  </div>

                  {!notification.is_read && (
                    <button
                      className="btn"
                      type="button"
                      onClick={(event) => {
                        event.stopPropagation();
                        void handleMarkRead(
                          notification,
                        );
                      }}
                      disabled={
                        busyId ===
                        notification.id
                      }
                    >
                      Mark read
                    </button>
                  )}

                  {!notification.is_read && (
                    <span
                      className="dot"
                      style={{
                        width: 7,
                        height: 7,
                      }}
                    />
                  )}
                </div>
              ),
            )}
          </div>
        )}
      </Card>
    </>
  );
}
/* -------------------------------------------------------------------------- */
/* Repository overview                                                        */
/* -------------------------------------------------------------------------- */

export function RepoOverview() {
  const params = useParams<{ name: string }>();
  const repoName = decodeURIComponent(params?.name || "");

  const [repo, setRepo] = useState<Repository | null>(null);
  const [commits, setCommits] = useState<
    Array<{
      sha: string;
      short_sha: string;
      author_name: string;
      committed_at: number;
      subject: string;
    }>
  >([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    const load = async (forceRefresh = false) => {
      try {
        if (!repo) setLoading(true);
        setError(null);

        const overviewKey = `overview:repo:${repoName.toLowerCase()}`;
        const overviewData = await clientCache.fetch(
          overviewKey,
          async () => {
            const user = await authService.getCurrentUser().catch(() => null);
            const repositories =
              await repositoryService.listRepositories({ forceRefresh });

            const userMatch = user ? repositories.find(
              (item) =>
                item.name.toLowerCase() === repoName.toLowerCase() &&
                (item.owner?.toLowerCase() === user.username.toLowerCase() || item.owner_id === user.id),
            ) : null;

            const matched = userMatch || repositories.find(
              (item) =>
                item.name.toLowerCase() ===
                repoName.toLowerCase(),
            );

            if (!matched) {
              throw new Error(
                `Repository "${repoName}" was not found`,
              );
            }

            const owner = matched.owner;

            if (!owner) {
              throw new Error(
                "Repository owner is missing from repository metadata",
              );
            }

            const actualRepo =
              await repositoryService.getRepository(
                owner,
                matched.name,
                { forceRefresh }
              );

            const commitKey = `commits:${owner.toLowerCase()}/${actualRepo.name.toLowerCase()}:${actualRepo.default_branch}:10`;
            const commitResponse = await clientCache.fetch(
              commitKey,
              () =>
                apiAuth<{
                  ref: string;
                  head: string;
                  commits: Array<{
                    sha: string;
                    short_sha: string;
                    author_name: string;
                    author_email: string;
                    committed_at: number;
                    subject: string;
                  }>;
                }>(
                  `/v1/repositories/${encodeURIComponent(
                    owner,
                  )}/${encodeURIComponent(
                    actualRepo.name,
                  )}/commits?ref=${encodeURIComponent(
                    actualRepo.default_branch,
                  )}&limit=10`,
                ),
              { ...CACHE_TTL.COMMITS, forceRefresh }
            );

            return {
              repo: actualRepo,
              commits: Array.isArray(commitResponse.commits)
                ? commitResponse.commits
                : [],
            };
          },
          {
            ...CACHE_TTL.OVERVIEW,
            forceRefresh,
          }
        );

        if (cancelled) return;

        setRepo(overviewData.repo);
        setCommits(overviewData.commits);
      } catch (err: any) {
        console.error(
          "Failed to load repository overview:",
          err,
        );

        if (!cancelled && !repo) {
          setError(
            err?.detail ||
            err?.message ||
            "Failed to load repository",
          );
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    };

    if (repoName) {
      void load(false);

      // Auto-refresh repository overview every 20 minutes (1,200,000 ms)
      const refresh = window.setInterval(() => {
        void load(true);
      }, 20 * 60 * 1000);

      return () => {
        cancelled = true;
        window.clearInterval(refresh);
      };
    }

    return () => {
      cancelled = true;
    };
  }, [repoName]);

  if (loading) {
    return (
      <>
        <PageHead
          eyebrow={`Repository · ${repoName}`}
          title={repoName || "Loading repository…"}
          sub="Fetching repository data from SUTRA."
        />

        <SkeletonRepoOverview />
      </>
    );
  }

  if (error || !repo) {
    return (
      <>
        <PageHead
          eyebrow="Repository"
          title="Repository unavailable"
          sub={error || "Repository not found."}
        />

        <Card>
          <div className="card-pad">
            <div
              className="sub"
              style={{ color: "#ff8fa0" }}
            >
              {error ||
                "SUTRA could not load this repository."}
            </div>
          </div>
        </Card>
      </>
    );
  }

  const latestCommit = commits[0];

  return (
    <>
      <PageHead
        eyebrow={`Repository · ${repo.name}`}
        title={repo.name}
        sub={
          repo.description ||
          "No repository description."
        }
        action={
          <Badge tone={repo.visibility === "private" ? "violet" : "green"}>
            {repo.visibility === "private"
              ? "Private"
              : "Public"}
          </Badge>
        }
      />

      <Pipeline />

      <div className="grid g4">
        <Stat
          label="Default branch"
          value={repo.default_branch || "—"}
        />

        <Stat
          label="Visibility"
          value={repo.visibility || "—"}
        />

        <Stat
          label="Commit history"
          value={String(commits.length)}
          delta={
            commits.length > 0
              ? "Latest commits loaded"
              : "No commits found"
          }
        />

        <Stat
          label="Repository created"
          value={
            repo.created_at
              ? new Date(
                repo.created_at,
              ).toLocaleDateString()
              : "—"
          }
        />
      </div>

      <div
        className="grid g2"
        style={{ marginTop: 14 }}
      >
        <Card>
          <div className="card-head">
            <div>
              <div className="h2">
                Repository
              </div>

              <div className="sub">
                Live repository metadata
              </div>
            </div>

            <Badge
              tone={
                repo.visibility ===
                  "private"
                  ? "violet"
                  : "green"
              }
            >
              {repo.visibility}
            </Badge>
          </div>

          <div className="card-pad">
            <div className="eyebrow">
              Description
            </div>

            <div className="sub">
              {repo.description ||
                "No description has been added yet."}
            </div>

            <div
              className="grid g2"
              style={{
                marginTop: 24,
              }}
            >
              <div>
                <div className="eyebrow">
                  Owner
                </div>

                <div className="title-sm">
                  {repo.owner || "—"}
                </div>
              </div>

              <div>
                <div className="eyebrow">
                  Default branch
                </div>

                <div className="title-sm code">
                  {repo.default_branch ||
                    "—"}
                </div>
              </div>

              <div>
                <div className="eyebrow">
                  Repository ID
                </div>

                <div
                  className="code"
                  style={{
                    wordBreak:
                      "break-all",
                  }}
                >
                  {repo.id}
                </div>
              </div>

              <div>
                <div className="eyebrow">
                  Updated
                </div>

                <div className="title-sm">
                  {repo.updated_at
                    ? new Date(
                      repo.updated_at,
                    ).toLocaleString()
                    : "—"}
                </div>
              </div>
            </div>
          </div>
        </Card>

        <Card>
          <div className="card-head">
            <div>
              <div className="h2">
                Recent commits
              </div>

              <div className="sub">
                {repo.default_branch ||
                  "default branch"}
              </div>
            </div>

            <Badge tone="aqua">
              {commits.length} loaded
            </Badge>
          </div>

          {commits.length === 0 ? (
            <div className="card-pad">
              <div className="sub">
                No commits are available on the
                default branch.
              </div>
            </div>
          ) : (
            <div className="list">
              {commits.map((commit) => (
                <div
                  className="list-row"
                  key={commit.sha}
                >
                  <I.GitCommit
                    size={15}
                    className="muted"
                  />

                  <div
                    style={{
                      flex: 1,
                      minWidth: 0,
                    }}
                  >
                    <div className="title-sm">
                      {commit.subject ||
                        "No commit message"}
                    </div>

                    <div className="meta">
                      {commit.author_name ||
                        "Unknown author"}{" "}
                      ·{" "}
                      {commit.committed_at
                        ? new Date(
                          commit.committed_at *
                          1000,
                        ).toLocaleString()
                        : "Unknown time"}
                    </div>
                  </div>

                  <span className="code meta">
                    {commit.short_sha}
                  </span>
                </div>
              ))}
            </div>
          )}
        </Card>
      </div>
    </>
  );
}
/* -------------------------------------------------------------------------- */
/* Code Browser                                                               */
/* -------------------------------------------------------------------------- */

export function CodeBrowser() {
  return (
    <>
      <PageHead
        eyebrow="sutra-core / src"
        title="Code Browser"
        sub="Browse the repository with history and branches in context."
        action={
          <>
            <Btn>
              main <I.ChevronDown size={13} />
            </Btn>
            <Btn>
              <I.GitCommit size={13} /> Commit
            </Btn>
          </>
        }
      />

      <Card>
        <div className="split">
          <div className="tree">
            <div className="eyebrow">Files</div>
            {[
              "src",
              "  agents",
              "    executor.ts",
              "    context.ts",
              "  changes",
              "    change.ts",
              "  ci",
              "    runner.ts",
              "  repositories",
              "    repo.ts",
              "lib",
              "  events.ts",
              "tests",
              "  executor.test.ts",
              "package.json",
            ].map((x, i) => (
              <div
                className={`tree-item ${i === 3 ? "sel" : ""}`}
                key={x}
              >
                {x}
              </div>
            ))}
          </div>

          <div className="editor">
            <div
              className="row"
              style={{ marginBottom: 16 }}
            >
              <div>
                <div className="title-sm">
                  src/agents/executor.ts
                </div>
                <div className="meta">
                  Last changed 8 minutes ago by Atlas
                </div>
              </div>
              <Badge tone="aqua">main</Badge>
            </div>

            <div className="code">
              {Array.from({ length: 27 }, (_, i) => (
                <div key={i}>
                  <span className="ln">{i + 1}</span>
                  {
                    [
                      "import { AgentContext } from './context';",
                      "import { Trace } from '../events';",
                      "",
                      "export async function execute(",
                      "  task: Task, context: AgentContext",
                      "  ): Promise<ExecutionResult> {",
                      "  const trace = new Trace(context.runId);",
                      "",
                      "  trace.emit('agent.started', {",
                      "    taskId: task.id,",
                      "    repository: context.repository,",
                      "  });",
                      "",
                      "  const plan = await context.plan(task);",
                      "  const result = await context.apply(plan);",
                      "",
                      "  await context.tests.run();",
                      "  await context.changes.open(result);",
                      "",
                      "  trace.emit('agent.completed', {",
                      "    changeId: result.changeId,",
                      "    durationMs: trace.duration(),",
                      "  });",
                      "",
                      "  return result;",
                      "}",
                    ][i]
                  }
                </div>
              ))}
            </div>
          </div>
        </div>
      </Card>
    </>
  );
}

/* -------------------------------------------------------------------------- */
/* Issues                                                                      */
/* -------------------------------------------------------------------------- */

export function Issues() {
  const [issues, setIssues] = useState<Issue[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [closeIssue, setCloseIssue] =
    useState<Issue | null>(null);

  const [closeResolution, setCloseResolution] =
    useState<IssueResolution>("completed");

  const [closeComment, setCloseComment] =
    useState("");

  const [closing, setClosing] =
    useState(false);

  const [reopenIssue, setReopenIssue] =
    useState<Issue | null>(null);

  const [reopenComment, setReopenComment] =
    useState("");

  const [reopening, setReopening] =
    useState(false);

  const [filter, setFilter] = useState<
    "all" | "open" | "closed"
  >("open");

  const [search, setSearch] = useState("");

  const [sort, setSort] = useState<
    "newest" | "oldest"
  >("newest");

  const [repoName, setRepoName] =
    useState<string | null>(null);

  const loadIssues = async () => {
    try {
      setLoading(true);
      setError(null);

      const pathname =
        typeof window !== "undefined"
          ? window.location.pathname
          : "";

      const parts = pathname
        .split("/")
        .filter(Boolean);

      const repositoriesIndex =
        parts.indexOf("repositories");

      const repository =
        repositoriesIndex >= 0
          ? parts[repositoriesIndex + 1]
          : null;

      if (!repository) {
        throw new Error(
          "Repository could not be determined.",
        );
      }

      setRepoName(repository);

      const user =
        await authService.getCurrentUser();
      setOwnerName(user.username);

      const data =
        await issueService.listIssues(
          user.username,
          repository,
        );

      setIssues(data);
    } catch (err: any) {
      console.error(
        "Failed to load repository issues:",
        err,
      );

      setError(
        err?.detail ||
        err?.message ||
        "Failed to load issues.",
      );
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void loadIssues();
  }, []);

  const filteredIssues = issues
    .filter((issue) => {
      const state =
        issue.state ||
        issue.status ||
        "open";

      if (
        filter !== "all" &&
        state !== filter
      ) {
        return false;
      }

      const query =
        search.trim().toLowerCase();

      if (!query) {
        return true;
      }

      return (
        issue.title
          .toLowerCase()
          .includes(query) ||
        issue.body
          .toLowerCase()
          .includes(query) ||
        String(
          issue.number ?? "",
        ).includes(query)
      );
    })
    .sort((a, b) => {
      const aTime =
        new Date(a.updated_at).getTime();

      const bTime =
        new Date(b.updated_at).getTime();

      return sort === "newest"
        ? bTime - aTime
        : aTime - bTime;
    });

  const openCount = issues.filter(
    (issue) =>
      (issue.state ||
        issue.status ||
        "open") === "open",
  ).length;

  const closedCount = issues.filter(
    (issue) =>
      (issue.state ||
        issue.status ||
        "open") === "closed",
  ).length;

  const [ownerName, setOwnerName] =
    useState<string | null>(null);

  const openGitHubIssues = () => {
    if (!repoName) return;
    const targetOwner = ownerName || "github";
    window.open(
      `https://github.com/${encodeURIComponent(targetOwner)}/${encodeURIComponent(repoName)}/issues`,
      "_blank",
      "noopener,noreferrer"
    );
  };

  const submitClose = async () => {
    if (!repoName || !closeIssue) {
      return;
    }

    if (!closeComment.trim()) {
      setError(
        "Add a closing comment before closing the issue.",
      );
      return;
    }

    try {
      setClosing(true);
      setError(null);

      const user =
        await authService.getCurrentUser();

      await issueService.updateIssueStatus(
        user.username,
        repoName,
        closeIssue.id,
        {
          status: "closed",
          resolution: closeResolution,
          comment: closeComment.trim(),
        },
      );

      setIssues((current) =>
        current.map((item) =>
          item.id === closeIssue.id
            ? {
              ...item,
              status: "closed",
              state: "closed",
              closed_at:
                new Date().toISOString(),
              updated_at:
                new Date().toISOString(),
            }
            : item,
        ),
      );

      setCloseIssue(null);
      setCloseComment("");
      setCloseResolution("completed");
    } catch (err: any) {
      setError(
        err?.detail ||
        err?.message ||
        "Failed to close issue.",
      );
    } finally {
      setClosing(false);
    }
  };

  const submitReopen = async () => {
    if (!repoName || !reopenIssue) {
      return;
    }

    try {
      setReopening(true);
      setError(null);

      const user =
        await authService.getCurrentUser();

      await issueService.updateIssueStatus(
        user.username,
        repoName,
        reopenIssue.id,
        {
          status: "open",
          comment:
            reopenComment.trim() || undefined,
        },
      );

      setIssues((current) =>
        current.map((item) =>
          item.id === reopenIssue.id
            ? {
              ...item,
              status: "open",
              state: "open",
              closed_at: null,
              updated_at:
                new Date().toISOString(),
            }
            : item,
        ),
      );

      setReopenIssue(null);
      setReopenComment("");
    } catch (err: any) {
      setError(
        err?.detail ||
        err?.message ||
        "Failed to reopen issue.",
      );
    } finally {
      setReopening(false);
    }
  };

  return (
    <>
      <PageHead
        eyebrow={repoName || "repository"}
        title="Issues"
        sub="Track bugs, problems, and engineering work for this repository."
        action={
          <Btn
            primary
            onClick={openGitHubIssues}
          >
            <I.ExternalLink size={14} />
            Open on GitHub
          </Btn>
        }
      />

      {error && (
        <Card
          style={{
            marginBottom: 12,
            borderColor:
              "rgba(255,127,146,.25)",
          }}
        >
          <div className="card-pad">
            <div
              className="sub"
              style={{
                color: "#ff7f92",
              }}
            >
              {error}
            </div>
          </div>
        </Card>
      )}

      <Card>
        <div className="card-head">
          <div className="actions">
            <Btn
              primary={filter === "open"}
              onClick={() =>
                setFilter("open")
              }
            >
              Open {openCount}
            </Btn>

            <Btn
              primary={filter === "closed"}
              onClick={() =>
                setFilter("closed")
              }
            >
              Closed {closedCount}
            </Btn>

            <Btn
              primary={filter === "all"}
              onClick={() =>
                setFilter("all")
              }
            >
              All {issues.length}
            </Btn>
          </div>

          <div
            className="actions"
            style={{
              flexWrap: "wrap",
            }}
          >
            <div
              style={{
                position: "relative",
              }}
            >
              <I.Search
                size={13}
                style={{
                  position: "absolute",
                  left: 10,
                  top: "50%",
                  transform:
                    "translateY(-50%)",
                  opacity: 0.55,
                }}
              />

              <input
                className="input"
                placeholder="Search issues..."
                value={search}
                onChange={(event) =>
                  setSearch(
                    event.target.value,
                  )
                }
                style={{
                  width: 220,
                  paddingLeft: 30,
                }}
              />
            </div>

            <Btn
              onClick={() =>
                setSort((current) =>
                  current === "newest"
                    ? "oldest"
                    : "newest",
                )
              }
            >
              {sort === "newest"
                ? "Newest"
                : "Oldest"}
            </Btn>
          </div>
        </div>

        {loading ? (
          <div className="card-pad">
            <div className="sub">
              Loading issues…
            </div>
          </div>
        ) : filteredIssues.length === 0 ? (
          <div
            className="card-pad"
            style={{
              textAlign: "center",
              paddingTop: 56,
              paddingBottom: 56,
            }}
          >
            <div
              style={{
                width: 42,
                height: 42,
                border:
                  "1px solid var(--line)",
                borderRadius: 12,
                display: "grid",
                placeItems: "center",
                margin:
                  "0 auto 14px",
              }}
            >
              <I.CircleDot size={18} />
            </div>

            <div className="h2">
              {issues.length === 0
                ? "No issues yet"
                : "No matching issues"}
            </div>

            <div
              className="sub"
              style={{
                maxWidth: 420,
                margin:
                  "8px auto 18px",
              }}
            >
              {issues.length === 0
                ? "This repository does not have any issues yet."
                : "Try changing the filter or search query."}
            </div>

            {issues.length === 0 && (
              <Btn
                primary
                onClick={openGitHubIssues}
              >
                <I.ExternalLink size={14} />
                Open on GitHub
              </Btn>
            )}
          </div>
        ) : (
          <div className="list">
            {filteredIssues.map(
              (issue) => {
                const state =
                  issue.state ||
                  issue.status ||
                  "open";

                const isOpen =
                  state === "open";

                return (
                  <div
                    className="list-row"
                    key={issue.id}
                    style={{
                      alignItems:
                        "flex-start",
                    }}
                  >
                    <div
                      style={{
                        width: 28,
                        height: 28,
                        border:
                          "1px solid var(--line)",
                        borderRadius: 7,
                        display: "grid",
                        placeItems: "center",
                        flexShrink: 0,
                      }}
                    >
                      {isOpen ? (
                        <I.CircleDot
                          size={14}
                          style={{
                            color:
                              "#55e0bd",
                          }}
                        />
                      ) : (
                        <I.CheckCircle2
                          size={14}
                          style={{
                            color:
                              "#8d95a7",
                          }}
                        />
                      )}
                    </div>

                    <div
                      style={{
                        flex: 1,
                        minWidth: 0,
                      }}
                    >
                      <Link
                        href={`/repositories/${encodeURIComponent(
                          repoName || "",
                        )}/issues/${encodeURIComponent(
                          issue.id,
                        )}`}
                        className="title-sm"
                        style={{
                          textDecoration:
                            "none",
                        }}
                      >
                        {issue.number
                          ? `#${issue.number} `
                          : ""}
                        {issue.title}
                      </Link>

                      <div
                        className="meta"
                        style={{
                          marginTop: 4,
                        }}
                      >
                        {isOpen
                          ? "Open"
                          : "Closed"}{" "}
                        ·{" "}
                        {new Date(
                          issue.updated_at,
                        ).toLocaleDateString()}
                      </div>

                      {issue.body && (
                        <div
                          className="sub"
                          style={{
                            marginTop: 7,
                            display:
                              "-webkit-box",
                            WebkitLineClamp: 2,
                            WebkitBoxOrient:
                              "vertical",
                            overflow: "hidden",
                          }}
                        >
                          {issue.body}
                        </div>
                      )}
                    </div>

                    <div
                      className="actions"
                      style={{
                        alignSelf:
                          "center",
                      }}
                    >
                      <Badge
                        tone={
                          isOpen
                            ? "aqua"
                            : undefined
                        }
                      >
                        {isOpen
                          ? "Open"
                          : "Closed"}
                      </Badge>

                      {isOpen ? (
                        <Btn
                          onClick={() => {
                            setCloseIssue(issue);
                            setCloseResolution(
                              "completed",
                            );
                            setCloseComment("");
                          }}
                        >
                          Close
                        </Btn>
                      ) : (
                        <Btn
                          onClick={() => {
                            setReopenIssue(issue);
                            setReopenComment("");
                          }}
                        >
                          Reopen
                        </Btn>
                      )}
                    </div>
                  </div>
                );
              },
            )}
          </div>
        )}
      </Card>

      {closeIssue && (
        <div
          style={{
            position: "fixed",
            inset: 0,
            zIndex: 200,
            background:
              "rgba(0,0,0,.85)",
            display: "grid",
            placeItems: "center",
            padding: 20,
          }}
          onMouseDown={(event) => {
            if (
              event.target ===
              event.currentTarget
            ) {
              setCloseIssue(null);
            }
          }}
        >
          <Card
            style={{
              width:
                "min(100%, 560px)",
            }}
          >
            <div className="card-head">
              <div>
                <div className="h2">
                  Close issue
                </div>

                <div className="sub">
                  {closeIssue.number
                    ? `#${closeIssue.number} `
                    : ""}
                  {closeIssue.title}
                </div>
              </div>

              <button
                type="button"
                className="iconbtn"
                onClick={() =>
                  setCloseIssue(null)
                }
              >
                <I.X size={15} />
              </button>
            </div>

            <div className="card-pad">
              <div
                className="sub"
                style={{
                  marginBottom: 8,
                }}
              >
                Resolution
              </div>

              <select
                className="input"
                value={closeResolution}
                onChange={(event) =>
                  setCloseResolution(
                    event.target
                      .value as IssueResolution,
                  )
                }
              >
                <option value="completed">
                  Completed
                </option>

                <option value="not_planned">
                  Not planned
                </option>

                <option value="duplicate">
                  Duplicate
                </option>
              </select>

              <div
                className="sub"
                style={{
                  marginTop: 16,
                  marginBottom: 8,
                }}
              >
                Closing comment
              </div>

              <textarea
                className="input"
                value={closeComment}
                onChange={(event) =>
                  setCloseComment(
                    event.target.value,
                  )
                }
                placeholder={
                  closeResolution ===
                    "duplicate"
                    ? "Explain which issue this duplicates..."
                    : closeResolution ===
                      "not_planned"
                      ? "Explain why this will not be planned..."
                      : "Explain how this issue was resolved..."
                }
                style={{
                  minHeight: 120,
                  resize: "vertical",
                }}
              />

              <div
                className="actions"
                style={{
                  justifyContent:
                    "flex-end",
                  marginTop: 18,
                }}
              >
                <Btn
                  onClick={() =>
                    setCloseIssue(null)
                  }
                >
                  Cancel
                </Btn>

                <Btn
                  primary
                  disabled={
                    closing ||
                    !closeComment.trim()
                  }
                  onClick={submitClose}
                >
                  {closing
                    ? "Closing..."
                    : "Close with comment"}
                </Btn>
              </div>
            </div>
          </Card>
        </div>
      )}

      {reopenIssue && (
        <div
          style={{
            position: "fixed",
            inset: 0,
            zIndex: 200,
            background:
              "rgba(0,0,0,.85)",
            display: "grid",
            placeItems: "center",
            padding: 20,
          }}
          onMouseDown={(event) => {
            if (
              event.target ===
              event.currentTarget
            ) {
              setReopenIssue(null);
            }
          }}
        >
          <Card
            style={{
              width:
                "min(100%, 560px)",
            }}
          >
            <div className="card-head">
              <div>
                <div className="h2">
                  Reopen issue
                </div>

                <div className="sub">
                  {reopenIssue.number
                    ? `#${reopenIssue.number} `
                    : ""}
                  {reopenIssue.title}
                </div>
              </div>

              <button
                type="button"
                className="iconbtn"
                onClick={() =>
                  setReopenIssue(null)
                }
              >
                <I.X size={15} />
              </button>
            </div>

            <div className="card-pad">
              <div
                className="sub"
                style={{
                  marginBottom: 8,
                }}
              >
                Reopen comment
                <span
                  style={{
                    opacity: 0.55,
                  }}
                >
                  {" "}
                  (optional)
                </span>
              </div>

              <textarea
                className="input"
                value={reopenComment}
                onChange={(event) =>
                  setReopenComment(
                    event.target.value,
                  )
                }
                placeholder="Why is this issue being reopened?"
                style={{
                  minHeight: 120,
                  resize: "vertical",
                }}
              />

              <div
                className="actions"
                style={{
                  justifyContent:
                    "flex-end",
                  marginTop: 18,
                }}
              >
                <Btn
                  onClick={() =>
                    setReopenIssue(null)
                  }
                >
                  Cancel
                </Btn>

                <Btn
                  primary
                  disabled={reopening}
                  onClick={submitReopen}
                >
                  {reopening
                    ? "Reopening..."
                    : "Reopen issue"}
                </Btn>
              </div>
            </div>
          </Card>
        </div>
      )}
    </>
  );
}
/* -------------------------------------------------------------------------- */
/* Tasks                                                                       */
/* -------------------------------------------------------------------------- */

export function Tasks() {
  const params = useParams<{ name?: string }>();
  const repoName = params?.name ? decodeURIComponent(params.name) : null;

  type TaskRow = {
    id: string;
    title: string;
    repo_name: string;
    status: string;
    updated_at: string;
  };

  const [tasks, setTasks] =
    useState<TaskRow[]>([]);

  const [loading, setLoading] =
    useState(true);

  const [error, setError] =
    useState<string | null>(null);

  const [isNewTaskModalOpen, setIsNewTaskModalOpen] =
    useState(false);

  const [selectedTaskId, setSelectedTaskId] =
    useState<string | null>(null);

  const [taskToTerminate, setTaskToTerminate] =
    useState<TaskRow | null>(null);

  const [terminating, setTerminating] =
    useState(false);

  const executeTerminateTask = async () => {
    if (!taskToTerminate) return;
    setTerminating(true);
    try {
      await taskService.terminateTask(taskToTerminate.id);
      setTasks((prev) =>
        prev.map((t) =>
          t.id === taskToTerminate.id
            ? { ...t, status: "cancelled" }
            : t,
        ),
      );
      setTaskToTerminate(null);
    } catch (err: any) {
      console.error("Failed to terminate task:", err);
    } finally {
      setTerminating(false);
    }
  };

  const loadTasks = async () => {
    try {
      setLoading(true);
      setError(null);

      const data =
        await apiAuth<TaskRow[]>(
          "/v1/me/work",
        );

      const allTasks = Array.isArray(data) ? data : [];
      setTasks(
        repoName
          ? allTasks.filter(
              (task) =>
                task.repo_name?.toLowerCase() ===
                repoName.toLowerCase(),
            )
          : allTasks,
      );
    } catch (err: any) {
      console.error(
        "Failed to load tasks:",
        err,
      );

      setError(
        err?.detail ||
        err?.message ||
        "Failed to load tasks.",
      );
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void loadTasks();
  }, []);

  const normalizeStatus = (
    status: string,
  ) => {
    const value =
      status
        .toLowerCase()
        .trim()
        .replaceAll("-", "_")
        .replaceAll(" ", "_");

    if (
      [
        "cancelled",
        "canceled",
        "terminated",
        "aborted",
        "failed",
      ].includes(value)
    ) {
      return "cancelled";
    }

    if (
      [
        "todo",
        "backlog",
        "open",
        "pending",
        "created",
      ].includes(value)
    ) {
      return "backlog";
    }

    if (
      [
        "in_progress",
        "running",
        "active",
        "claimed",
        "started",
      ].includes(value)
    ) {
      return "in_progress";
    }

    if (
      [
        "review",
        "in_review",
        "awaiting_review",
        "pending_review",
      ].includes(value)
    ) {
      return "review";
    }

    if (
      [
        "done",
        "completed",
        "complete",
        "closed",
      ].includes(value)
    ) {
      return "done";
    }

    return "backlog";
  };

  const columns = [
    {
      key: "backlog",
      title: "Backlog",
      tone: "amber" as const,
    },
    {
      key: "in_progress",
      title: "In Progress",
      tone: "aqua" as const,
    },
    {
      key: "review",
      title: "In Review",
      tone: "violet" as const,
    },
    {
      key: "done",
      title: "Done",
      tone: "green" as const,
    },
    {
      key: "cancelled",
      title: "Cancelled",
      tone: "red" as const,
    },
  ];

  const groupedTasks = columns.map(
    (column) => ({
      ...column,
      tasks: tasks
        .filter(
          (task) =>
            normalizeStatus(
              task.status,
            ) === column.key,
        )
        .sort(
          (a, b) =>
            new Date(
              b.updated_at,
            ).getTime() -
            new Date(
              a.updated_at,
            ).getTime(),
        ),
    }),
  );

  const openCount = tasks.filter(
    (task) => {
      const s = normalizeStatus(task.status);
      return s === "in_progress" || s === "review" || s === "backlog";
    },
  ).length;

  const completedCount = tasks.filter(
    (task) =>
      normalizeStatus(
        task.status,
      ) === "done",
  ).length;

  const cancelledCount = tasks.filter(
    (task) =>
      normalizeStatus(
        task.status,
      ) === "cancelled",
  ).length;

  return (
    <>
      <PageHead
        eyebrow={repoName ? `Repository · ${repoName}` : "Execution"}
        title="Tasks"
        sub={repoName ? `Autonomous and team engineering tasks for ${repoName}.` : "Real tasks from your SUTRA workspace."}
        action={
          <Btn
            primary
            onClick={() =>
              setIsNewTaskModalOpen(true)
            }
          >
            <I.Plus size={14} />
            New Task
          </Btn>
        }
      />

      {isNewTaskModalOpen && (
        <NewTaskModal
          onClose={() =>
            setIsNewTaskModalOpen(false)
          }
          onSuccess={() => {
            setIsNewTaskModalOpen(false);
            void loadTasks();
          }}
        />
      )}

      {selectedTaskId && (
        <TaskModal
          taskId={selectedTaskId}
          onClose={() => {
            setSelectedTaskId(null);
            void loadTasks();
          }}
          onTaskUpdated={() => {
            void loadTasks();
          }}
        />
      )}

      {error && (
        <Card
          style={{
            marginBottom: 16,
            borderColor:
              "rgba(255,127,146,.22)",
          }}
        >
          <div className="card-pad">
            <div
              className="sub"
              style={{
                color: "#ff8fa0",
              }}
            >
              {error}
            </div>
          </div>
        </Card>
      )}

      <div
        className="grid g3"
        style={{
          marginBottom: 16,
        }}
      >
        <Stat
          label="Active"
          value={
            loading
              ? "—"
              : String(openCount)
          }
        />

        <Stat
          label="Completed"
          value={
            loading
              ? "—"
              : String(completedCount)
          }
        />

        <Stat
          label="Cancelled"
          value={
            loading
              ? "—"
              : String(cancelledCount)
          }
        />
      </div>

      {loading ? (
        <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
          {[1, 2, 3, 4].map((i) => (
            <Card key={i} style={{ padding: "16px 20px" }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <div style={{ display: "flex", alignItems: "center", gap: 12, flex: 1 }}>
                  <Skeleton width={18} height={18} borderRadius={4} />
                  <div style={{ display: "flex", flexDirection: "column", gap: 6, flex: 1 }}>
                    <Skeleton width={`${45 + (i % 3) * 15}%`} height={15} borderRadius={4} />
                    <Skeleton width={120} height={12} borderRadius={3} />
                  </div>
                </div>
                <Skeleton width={75} height={22} borderRadius={11} />
              </div>
            </Card>
          ))}
        </div>
      ) : tasks.length === 0 ? (
        <Card>
          <div
            className="card-pad"
            style={{
              textAlign: "center",
              paddingTop: 60,
              paddingBottom: 60,
            }}
          >
            <div className="h2">
              No tasks yet
            </div>

            <div
              className="sub"
              style={{
                maxWidth: 420,
                margin:
                  "8px auto 18px",
              }}
            >
              Create a task and it will appear
              here as it moves through the
              execution workflow.
            </div>

            <Btn
              primary
              onClick={() =>
                setIsNewTaskModalOpen(true)
              }
            >
              <I.Plus size={14} />
              Create task
            </Btn>
          </div>
        </Card>
      ) : (
        <div className="kanban-board">
          {groupedTasks.map(
            (column) => (
              <Card
                key={column.key}
              >
                <div className="card-head">
                  <div>
                    <div className="h2">
                      {column.title}
                    </div>

                    <div className="meta">
                      {column.tasks.length}{" "}
                      {column.tasks.length === 1
                        ? "task"
                        : "tasks"}
                    </div>
                  </div>

                  <Badge
                    tone={
                      column.tone
                    }
                  >
                    {column.tasks.length}
                  </Badge>
                </div>

                <div className="list">
                  {column.tasks.length ===
                    0 ? (
                    <div
                      className="card-pad"
                    >
                      <div className="meta">
                        No tasks here.
                      </div>
                    </div>
                  ) : (
                    column.tasks.map(
                      (task) => (
                        <button
                          key={task.id}
                          type="button"
                          className="card-pad"
                          onClick={() =>
                            setSelectedTaskId(
                              task.id,
                            )
                          }
                          style={{
                            width: "100%",
                            textAlign:
                              "left",
                            border: 0,
                            borderBottom:
                              "1px solid var(--line)",
                            background:
                              "transparent",
                            color:
                              "inherit",
                            cursor:
                              "pointer",
                          }}
                        >
                          <div
                            className="title-sm"
                            style={{
                              marginBottom: 7,
                            }}
                          >
                            {task.title}
                          </div>

                          <div
                            className="meta"
                            style={{
                              marginBottom: 10,
                            }}
                          >
                            {task.repo_name ||
                              "Repository"}
                          </div>

                          <div className="row" style={{ display: "flex", justifyContent: "space-between", alignItems: "center", width: "100%", gap: 6 }}>
                            <Badge
                              tone={
                                column.tone
                              }
                            >
                              {task.status
                                .replaceAll(
                                  "_",
                                  " ",
                                )}
                            </Badge>

                            <span className="meta" style={{ flex: 1, minWidth: 0, textAlign: "right", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
                              {new Date(
                                task.updated_at,
                              ).toLocaleDateString()}
                            </span>

                            {(normalizeStatus(task.status) === "in_progress" || normalizeStatus(task.status) === "backlog") && (
                              <span
                                role="button"
                                tabIndex={0}
                                onClick={(e) => {
                                  e.stopPropagation();
                                  setTaskToTerminate(task);
                                }}
                                className="badge red"
                                style={{
                                  cursor: "pointer",
                                  padding: "2px 6px",
                                  fontSize: "10px",
                                  background: "rgba(239, 68, 68, 0.12)",
                                  border: "1px solid rgba(239, 68, 68, 0.3)",
                                  color: "#ef4444",
                                  fontWeight: 600,
                                  borderRadius: 4,
                                  flexShrink: 0,
                                }}
                                title="Terminate task"
                              >
                                Terminate
                              </span>
                            )}
                          </div>
                        </button>
                      ),
                    )
                  )}
                </div>
              </Card>
            ),
          )}
        </div>
      )}

      <ConfirmModal
        isOpen={Boolean(taskToTerminate)}
        onClose={() => setTaskToTerminate(null)}
        onConfirm={executeTerminateTask}
        title="Terminate Task"
        description={
          <>
            Are you sure you want to terminate <strong>&ldquo;{taskToTerminate?.title}&rdquo;</strong>? Active execution will be cancelled immediately and marked as cancelled.
          </>
        }
        confirmText="Terminate Task"
        confirmTone="danger"
        loading={terminating}
      />
    </>
  );
}


/* -------------------------------------------------------------------------- */
/* Repository Settings — fixed implementation                                 */
/* -------------------------------------------------------------------------- */

type RepositoryBranch = {
  name: string;
  commit: string;
  protected?: boolean;
};

type DangerAction =
  | "visibility"
  | "transfer"
  | "delete"
  | "";

const EMPTY_RULE = (
  repositoryId: string,
  branch: string,
): BranchProtectionRule => ({
  id: "",
  repository_id: repositoryId,
  branch_pattern: branch || "main",
  enabled: true,
  required_approvals: 1,
  require_change_review: true,
  require_clean_conflict: true,
  require_resolved_threads: true,
  require_agent_review: false,
  require_no_blocking_agent_findings: false,
  allow_author_self_approval: false,
  require_ci_passed: true,
  created_by: "",
  updated_by: "",
  created_at: "",
  updated_at: "",
});

export function RepoSettings() {
  const params = useParams<{ name: string }>();
  const router = useRouter();

  const repoParam = decodeURIComponent(params?.name || "");

  const [repo, setRepo] = useState<Repository | null>(null);
  const [repoOwner, setRepoOwner] = useState("");
  const [branches, setBranches] = useState<RepositoryBranch[]>([]);
  const [rules, setRules] = useState<BranchProtectionRule[]>([]);

  const [settingsLoading, setSettingsLoading] =
    useState(true);

  const [savingGeneral, setSavingGeneral] =
    useState(false);
  const [savingRule, setSavingRule] =
    useState(false);
  const [deletingRule, setDeletingRule] =
    useState<string | null>(null);

  const [editName, setEditName] = useState("");
  const [editBranch, setEditBranch] = useState("");
  const [editDesc, setEditDesc] = useState("");

  const [newRule, setNewRule] =
    useState<BranchProtectionRule | null>(null);
  const [editingRuleId, setEditingRuleId] =
    useState<string | null>(null);

  const [dangerModal, setDangerModal] = useState<{
    open: boolean;
    action: DangerAction;
  }>({
    open: false,
    action: "",
  });

  const [confirmInput, setConfirmInput] =
    useState("");
  const [newOwnerInput, setNewOwnerInput] =
    useState("");

  const [newVisibility, setNewVisibility] =
    useState<"public" | "private">("private");

  const [executing, setExecuting] =
    useState(false);

  const [toast, setToast] = useState<{
    msg: string;
    ok: boolean;
  } | null>(null);

  const showToast = (
    msg: string,
    ok = true,
  ) => {
    setToast({ msg, ok });

    window.setTimeout(() => {
      setToast((current) =>
        current?.msg === msg
          ? null
          : current,
      );
    }, 3500);
  };

  /*
   * IMPORTANT:
   * Do not assume the current user's username is the repository owner.
   * Resolve the repository from the authenticated user's actual
   * repository list first. The repository object's owner is then
   * used for owner-scoped endpoints.
   */
  const resolveRepository = async (): Promise<{
    repository: Repository;
    owner: string;
  }> => {
    const user = await authService.getCurrentUser();

    const allRepos =
      await repositoryService.listRepositories();

    const userMatch = allRepos.find(
      (candidate) =>
        candidate.name.toLowerCase() ===
        repoParam.toLowerCase() &&
        (candidate.owner?.toLowerCase() === user.username.toLowerCase() || candidate.owner_id === user.id),
    );

    const directMatch = userMatch || allRepos.find(
      (candidate) =>
        candidate.name.toLowerCase() ===
        repoParam.toLowerCase(),
    );

    if (!directMatch) {
      /*
       * Fall back to the current username only if the
       * repository exists there. This preserves compatibility
       * with older backend deployments.
       */
      const fallback =
        await repositoryService.getRepository(
          user.username,
          repoParam,
        );

      return {
        repository: fallback,
        owner: fallback.owner || user.username,
      };
    }

    return {
      repository: directMatch,
      owner:
        directMatch.owner ||
        user.username,
    };
  };

  const loadSettings = async () => {
    setSettingsLoading(true);

    try {
      if (!repoParam) {
        throw new Error(
          "Repository name is missing from the URL",
        );
      }

      const resolved =
        await resolveRepository();

      const repository = resolved.repository;
      const owner = resolved.owner;

      // `listRepositories()` already returned the
      // repository object. Do not perform a second
      // owner/name lookup that can fail for repositories
      // whose route identity differs from the current user.
      const authoritative = repository;

      const branchData =
        await repositoryService.getBranches(
          owner,
          authoritative.name,
        );

      const repositoryBranches: RepositoryBranch[] =
        Array.isArray(branchData?.branches)
          ? branchData.branches
          : [];

      setRepo({
        ...authoritative,
        owner,
      });

      setRepoOwner(owner);

      setBranches(repositoryBranches);

      const preferredBranch =
        authoritative.default_branch ||
        branchData?.default_branch ||
        repositoryBranches[0]?.name ||
        "main";

      setEditName(authoritative.name || "");
      setEditBranch(preferredBranch);
      setEditDesc(authoritative.description || "");

      const loadedRules =
        await branchProtectionService.list(
          authoritative.id,
        );

      setRules(
        Array.isArray(loadedRules)
          ? loadedRules
          : [],
      );
    } catch (err: any) {
      console.error(
        "Failed to load repository settings:",
        err,
      );

      showToast(
        err?.detail ||
        err?.message ||
        "Failed to load repository settings",
        false,
      );
    } finally {
      setSettingsLoading(false);
    }
  };

  useEffect(() => {
    void loadSettings();

    // Repository settings should reload when the URL repo changes.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [repoParam]);

  const handleSaveGeneral = async () => {
    if (!repo) return;

    const name = editName.trim();
    const description = editDesc.trim();
    const defaultBranch = editBranch.trim();

    if (!name) {
      showToast(
        "Repository name cannot be empty",
        false,
      );
      return;
    }

    if (!defaultBranch) {
      showToast(
        "Default branch cannot be empty",
        false,
      );
      return;
    }

    if (
      !branches.some(
        (branch) => branch.name === defaultBranch,
      )
    ) {
      showToast(
        `Branch "${defaultBranch}" does not exist`,
        false,
      );
      return;
    }

    setSavingGeneral(true);

    try {
      const res =
        await repositoryService.updateSettings(
          repoOwner,
          repo.name,
          {
            name,
            default_branch: defaultBranch,
            description,
          },
        );

      const nextRepo: Repository = {
        ...repo,
        ...res,
        owner: res.owner || repoOwner,
        visibility:
          res.visibility ||
          repo.visibility,
        is_private:
          (res.visibility ||
            repo.visibility) === "private",
      };

      setRepo(nextRepo);

      showToast(
        "Repository settings saved",
      );

      if (
        res.name &&
        res.name !== repo.name
      ) {
        router.replace(
          `/repositories/${encodeURIComponent(
            res.name,
          )}/settings`,
        );
      }
    } catch (err: any) {
      showToast(
        err?.detail ||
        err?.message ||
        "Failed to save repository settings",
        false,
      );
    } finally {
      setSavingGeneral(false);
    }
  };

  const openDangerModal = (
    action: Exclude<DangerAction, "">,
  ) => {
    setConfirmInput("");
    setNewOwnerInput("");

    setNewVisibility(
      repo?.visibility === "private"
        ? "public"
        : "private",
    );

    setDangerModal({
      open: true,
      action,
    });
  };

  const closeDangerModal = () => {
    if (executing) return;

    setDangerModal({
      open: false,
      action: "",
    });

    setConfirmInput("");
    setNewOwnerInput("");
  };

  const executeDangerAction = async () => {
    if (!repo || !dangerModal.action) {
      return;
    }

    setExecuting(true);

    try {
      if (
        dangerModal.action ===
        "delete"
      ) {
        await repositoryService.deleteRepository(
          repoOwner,
          repo.name,
        );

        showToast(
          "Repository deleted",
        );

        setDangerModal({
          open: false,
          action: "",
        });

        router.replace("/repositories");
        return;
      }

      if (
        dangerModal.action ===
        "visibility"
      ) {
        await repositoryService.updateVisibility(
          repoOwner,
          repo.name,
          newVisibility,
        );

        setRepo((current) =>
          current
            ? {
              ...current,
              visibility:
                newVisibility,
              is_private:
                newVisibility ===
                "private",
            }
            : current,
        );

        closeDangerModal();

        showToast(
          `Repository is now ${newVisibility}`,
        );

        return;
      }

      if (
        dangerModal.action ===
        "transfer"
      ) {
        const nextOwner =
          newOwnerInput.trim();

        await repositoryService.transferRepository(
          repoOwner,
          repo.name,
          nextOwner,
        );

        closeDangerModal();

        showToast(
          `Repository transferred to ${nextOwner}`,
        );

        router.replace("/repositories");

        return;
      }
    } catch (err: any) {
      showToast(
        err?.detail ||
        err?.message ||
        "Action failed",
        false,
      );
    } finally {
      setExecuting(false);
    }
  };

  const confirmEnabled = useMemo(() => {
    if (!repo) return false;

    if (
      dangerModal.action ===
      "delete"
    ) {
      return confirmInput === repo.name;
    }

    if (
      dangerModal.action ===
      "visibility"
    ) {
      return (
        confirmInput ===
        `make ${newVisibility}`
      );
    }

    if (
      dangerModal.action ===
      "transfer"
    ) {
      return (
        !!newOwnerInput.trim() &&
        confirmInput ===
        "transfer ownership"
      );
    }

    return false;
  }, [
    confirmInput,
    dangerModal.action,
    newOwnerInput,
    newVisibility,
    repo,
  ]);

  const createBlankRule =
    (): BranchProtectionRule => {
      return EMPTY_RULE(
        repo?.id || "",
        editBranch ||
        repo?.default_branch ||
        "main",
      );
    };

  const saveRule = async (
    rule: BranchProtectionRule,
  ) => {
    if (!repo) return;

    const branchPattern =
      rule.branch_pattern.trim();

    if (!branchPattern) {
      showToast(
        "Branch pattern is required",
        false,
      );
      return;
    }

    if (
      !Number.isInteger(
        rule.required_approvals,
      ) ||
      rule.required_approvals < 0
    ) {
      showToast(
        "Required approvals must be a non-negative integer",
        false,
      );
      return;
    }

    setSavingRule(true);

    try {
      const payload = {
        branch_pattern:
          branchPattern,
        enabled: rule.enabled,
        required_approvals:
          rule.required_approvals,
        require_change_review:
          rule.require_change_review,
        require_clean_conflict:
          rule.require_clean_conflict,
        require_resolved_threads:
          rule.require_resolved_threads,
        require_agent_review:
          rule.require_agent_review,
        require_no_blocking_agent_findings:
          rule.require_no_blocking_agent_findings,
        allow_author_self_approval:
          rule.allow_author_self_approval,
        require_ci_passed:
          rule.require_ci_passed,
      };

      const saved = rule.id
        ? await branchProtectionService.update(
          repo.id,
          rule.id,
          payload,
        )
        : await branchProtectionService.create(
          repo.id,
          payload,
        );

      setRules((previous) =>
        rule.id
          ? previous.map((item) =>
            item.id === saved.id
              ? saved
              : item,
          )
          : [...previous, saved],
      );

      setNewRule(null);
      setEditingRuleId(null);

      showToast(
        "Branch protection rule saved",
      );
    } catch (err: any) {
      showToast(
        err?.detail ||
        err?.message ||
        "Failed to save branch protection rule",
        false,
      );
    } finally {
      setSavingRule(false);
    }
  };

  const deleteRule = async (
    rule: BranchProtectionRule,
  ) => {
    if (!repo || !rule.id) return;

    setDeletingRule(rule.id);

    try {
      await branchProtectionService.remove(
        repo.id,
        rule.id,
      );

      setRules((previous) =>
        previous.filter(
          (item) => item.id !== rule.id,
        ),
      );

      showToast(
        "Branch protection rule deleted",
      );
    } catch (err: any) {
      showToast(
        err?.detail ||
        err?.message ||
        "Failed to delete branch protection rule",
        false,
      );
    } finally {
      setDeletingRule(null);
    }
  };

  if (settingsLoading) {
    return (
      <>
        <PageHead
          eyebrow="Repository settings"
          title="Repository settings"
          sub="Fetching repository metadata, branches, and protection rules."
        />

        <SkeletonRepoSettings />
      </>
    );
  }

  if (!repo) {
    return (
      <>
        <PageHead
          eyebrow="Repository settings"
          title="Repository unavailable"
          sub="SUTRA could not resolve this repository from your current workspace."
          action={
            <Btn
              onClick={() => {
                void loadSettings();
              }}
            >
              Retry
            </Btn>
          }
        />

        <Card>
          <div className="card-pad">
            <div className="sub">
              Check that you have access to this repository
              and that the repository still exists.
            </div>
          </div>
        </Card>

        {toast && (
          <div
            className="card"
            style={{
              position: "fixed",
              right: 24,
              bottom: 24,
              zIndex: 50,
              maxWidth: 420,
            }}
          >
            <div className="card-pad">
              <div className="title-sm">
                {toast.msg}
              </div>
            </div>
          </div>
        )}
      </>
    );
  }

  return (
    <>
      <PageHead
        eyebrow={`Repository · ${repo.name}`}
        title="Repository settings"
        sub={`Manage configuration, branch protection, visibility, and ownership for ${repo.name}.`}
      />

      <div
        className="grid g2"
        style={{ alignItems: "start" }}
      >
        {/* ---------------------------------------------------------------- */}
        {/* General                                                         */}
        {/* ---------------------------------------------------------------- */}

        <Card>
          <div className="card-head">
            <div>
              <div className="h2">
                General
              </div>
              <div className="sub">
                Repository identity and branch configuration.
              </div>
            </div>

            <Badge tone="aqua">
              {repoOwner || "Repository owner"}
            </Badge>
          </div>

          <div className="card-pad form">
            <div className="field">
              <label
                className="label"
                htmlFor="repo-name"
              >
                Repository name
              </label>

              <input
                id="repo-name"
                className="input"
                value={editName}
                onChange={(event) =>
                  setEditName(
                    event.target.value,
                  )
                }
                disabled={savingGeneral}
              />
            </div>

            <div className="field">
              <label
                className="label"
                htmlFor="repo-description"
              >
                Description
              </label>

              <input
                id="repo-description"
                className="input"
                value={editDesc}
                onChange={(event) =>
                  setEditDesc(
                    event.target.value,
                  )
                }
                disabled={savingGeneral}
              />
            </div>

            <div className="field">
              <label
                className="label"
                htmlFor="repo-default-branch"
              >
                Default branch
              </label>

              <select
                id="repo-default-branch"
                className="input"
                value={editBranch}
                onChange={(event) =>
                  setEditBranch(
                    event.target.value,
                  )
                }
                disabled={savingGeneral}
              >
                {branches.map(
                  (branch) => (
                    <option
                      value={branch.name}
                      key={branch.name}
                    >
                      {branch.name}
                    </option>
                  ),
                )}
              </select>

              <div className="meta">
                Only real Git branches can be
                selected.
              </div>
            </div>

            <div className="field">
              <label className="label">
                Visibility
              </label>

              <div className="row">
                <Badge
                  tone={
                    repo.visibility ===
                      "private"
                      ? "violet"
                      : "green"
                  }
                >
                  {repo.visibility}
                </Badge>

                <Btn
                  onClick={() =>
                    openDangerModal(
                      "visibility",
                    ) as any
                  }
                >
                  Change visibility
                </Btn>
              </div>
            </div>

            <div
              className="row"
              style={{ marginTop: 18 }}
            >
              <div>
                <div className="title-sm">
                  Repository ID
                </div>
                <div className="meta">
                  {repo.id}
                </div>
              </div>
            </div>

            <div
              className="actions"
              style={{ marginTop: 18 }}
            >
              <Btn
                primary
                onClick={
                  handleSaveGeneral as any
                }
                disabled={
                  savingGeneral
                }
              >
                {savingGeneral
                  ? "Saving…"
                  : "Save changes"}
              </Btn>
            </div>
          </div>
        </Card>

        {/* ---------------------------------------------------------------- */}
        {/* Branch Protection                                                */}
        {/* ---------------------------------------------------------------- */}

        <Card>
          <div className="card-head">
            <div>
              <div className="h2">
                Branch protection
              </div>
              <div className="sub">
                Rules enforced by the SUTRA backend.
              </div>
            </div>

            <Btn
              primary
              onClick={() =>
                setNewRule(
                  createBlankRule(),
                )
              }
            >
              <I.Plus size={14} /> Add rule
            </Btn>
          </div>

          {rules.length === 0 &&
            !newRule && (
              <div className="card-pad">
                <div className="eyebrow">
                  No rules configured
                </div>

                <div className="h2">
                  This repository has no branch protection rules.
                </div>

                <div
                  className="sub"
                  style={{ marginTop: 8 }}
                >
                  Add a rule for{" "}
                  {repo.default_branch ||
                    editBranch ||
                    "main"}{" "}
                  to enforce review and CI requirements.
                </div>
              </div>
            )}

          {(newRule ||
            rules.length > 0) && (
              <div className="list">
                {newRule && (
                  <BranchProtectionEditor
                    key="new-rule"
                    rule={newRule}
                    onChange={
                      setNewRule
                    }
                    onCancel={() =>
                      setNewRule(null)
                    }
                    onSave={saveRule}
                    saving={savingRule}
                  />
                )}

                {rules.map((rule) => (
                  <div
                    className="list-row"
                    key={rule.id}
                    style={{
                      alignItems: "flex-start",
                      flexDirection: "column",
                    }}
                  >
                    {editingRuleId ===
                      rule.id ? (
                      <BranchProtectionEditor
                        rule={rule}
                        onChange={(
                          updated,
                        ) =>
                          setRules(
                            (previous) =>
                              previous.map(
                                (
                                  item,
                                ) =>
                                  item.id ===
                                    rule.id
                                    ? updated
                                    : item,
                              ),
                          )
                        }
                        onCancel={() =>
                          setEditingRuleId(
                            null,
                          )
                        }
                        onSave={saveRule}
                        saving={savingRule}
                      />
                    ) : (
                      <>
                        <div
                          className="row"
                          style={{
                            width: "100%",
                          }}
                        >
                          <div>
                            <div className="row">
                              <div className="title-sm">
                                {rule.branch_pattern}
                              </div>

                              <Badge
                                tone={
                                  rule.enabled
                                    ? "green"
                                    : "amber"
                                }
                              >
                                {rule.enabled
                                  ? "Enabled"
                                  : "Disabled"}
                              </Badge>
                            </div>

                            <div className="meta">
                              {rule.required_approvals} approval
                              {rule.required_approvals ===
                                1
                                ? ""
                                : "s"}{" "}
                              required
                            </div>
                          </div>

                          <div className="actions">
                            <Btn
                              onClick={() =>
                                setEditingRuleId(
                                  rule.id,
                                )
                              }
                            >
                              Edit
                            </Btn>

                            <Btn
                              onClick={() => {
                                const confirmed = window.confirm(
                                  `Delete branch protection rule "${rule.branch_pattern}"?`
                                );

                                if (confirmed) {
                                  void deleteRule(rule);
                                }
                              }}>Delete</Btn>
                          </div>
                        </div>

                        <div
                          className="grid g3"
                          style={{
                            width: "100%",
                            marginTop: 12,
                          }}
                        >
                          <ProtectionFlag
                            enabled={
                              rule.require_change_review
                            }
                            label="Change review"
                          />

                          <ProtectionFlag
                            enabled={
                              rule.require_ci_passed
                            }
                            label="CI required"
                          />

                          <ProtectionFlag
                            enabled={
                              rule.require_clean_conflict
                            }
                            label="Clean conflicts"
                          />

                          <ProtectionFlag
                            enabled={
                              rule.require_resolved_threads
                            }
                            label="Resolved threads"
                          />

                          <ProtectionFlag
                            enabled={
                              rule.require_agent_review
                            }
                            label="Agent review"
                          />

                          <ProtectionFlag
                            enabled={
                              rule.require_no_blocking_agent_findings
                            }
                            label="No blocking agent findings"
                          />

                          <ProtectionFlag
                            enabled={
                              rule.allow_author_self_approval
                            }
                            label="Author self-approval"
                          />
                        </div>
                      </>
                    )}
                  </div>
                ))}
              </div>
            )}
        </Card>

        {/* ---------------------------------------------------------------- */}
        {/* Branch list                                                       */}
        {/* ---------------------------------------------------------------- */}

        <Card>
          <div className="card-head">
            <div>
              <div className="h2">
                Branches
              </div>
              <div className="sub">
                Branches currently present in the Git repository.
              </div>
            </div>

            <Badge tone="aqua">
              {branches.length}
            </Badge>
          </div>

          {branches.length === 0 ? (
            <div className="card-pad">
              <div className="sub">
                No Git branches were returned by the repository browser.
              </div>
            </div>
          ) : (
            <div className="list">
              {branches.map(
                (branch) => (
                  <div
                    className="list-row"
                    key={branch.name}
                  >
                    <I.GitBranch
                      size={15}
                      className="muted"
                    />

                    <div
                      style={{
                        flex: 1,
                      }}
                    >
                      <div className="title-sm">
                        {branch.name}
                      </div>
                      <div className="meta">
                        {branch.commit}
                      </div>
                    </div>

                    {branch.name ===
                      repo.default_branch && (
                        <Badge tone="green">
                          Default
                        </Badge>
                      )}

                    {branch.protected && (
                      <Badge tone="violet">
                        Protected
                      </Badge>
                    )}
                  </div>
                ),
              )}
            </div>
          )}
        </Card>

        {/* ---------------------------------------------------------------- */}
        {/* Repository details                                               */}
        {/* ---------------------------------------------------------------- */}

        <Card>
          <div className="card-head">
            <div>
              <div className="h2">
                Repository details
              </div>
              <div className="sub">
                Current backend-backed repository metadata.
              </div>
            </div>
          </div>

          <div className="card-pad">
            <div
              className="row"
              style={{
                padding: "10px 0",
                borderBottom:
                  "1px solid var(--line)",
              }}
            >
              <span className="meta">
                Owner
              </span>
              <span className="title-sm">
                {repoOwner}
              </span>
            </div>

            <div
              className="row"
              style={{
                padding: "10px 0",
                borderBottom:
                  "1px solid var(--line)",
              }}
            >
              <span className="meta">
                Repository
              </span>
              <span className="title-sm">
                {repo.name}
              </span>
            </div>

            <div
              className="row"
              style={{
                padding: "10px 0",
              }}
            >
              <span className="meta">
                Default branch
              </span>
              <span className="code">
                {repo.default_branch}
              </span>
            </div>
          </div>
        </Card>
      </div>

      {/* ------------------------------------------------------------------ */}
      {/* Danger Zone                                                        */}
      {/* ------------------------------------------------------------------ */}

      <Card
        style={{
          marginTop: 14,
          borderColor:
            "rgba(255,127,146,.18)",
        }}
      >
        <div className="card-head">
          <div>
            <div className="h2">
              Danger zone
            </div>
            <div className="sub">
              Destructive and ownership-changing repository actions.
            </div>
          </div>

          <Badge tone="red">
            Restricted
          </Badge>
        </div>

        <div className="card-pad">
          <div
            className="grid g3"
            style={{ alignItems: "stretch" }}
          >
            <DangerActionCard
              title="Change visibility"
              description="Make this repository public or private."
              actionLabel="Change visibility"
              onClick={() =>
                openDangerModal(
                  "visibility",
                )
              }
            />

            <DangerActionCard
              title="Transfer ownership"
              description="Move this repository to another supported owner."
              actionLabel="Transfer"
              onClick={() =>
                openDangerModal(
                  "transfer",
                )
              }
            />

            <DangerActionCard
              title="Delete repository"
              description="Permanently delete this repository and its Git storage."
              actionLabel="Delete"
              danger
              onClick={() =>
                openDangerModal(
                  "delete",
                )
              }
            />
          </div>
        </div>
      </Card>

      {/* ------------------------------------------------------------------ */}
      {/* Danger modal                                                       */}
      {/* ------------------------------------------------------------------ */}

      {dangerModal.open && (
        <div
          style={{
            position: "fixed",
            inset: 0,
            background:
              "rgba(0,0,0,.85)",
            display: "grid",
            placeItems: "center",
            padding: 20,
            zIndex: 100,
          }}
          onMouseDown={(event) => {
            if (
              event.target ===
              event.currentTarget
            ) {
              closeDangerModal();
            }
          }}
        >
          <Card
            style={{
              width: "min(100%, 520px)",
            }}
          >
            <div className="card-head">
              <div>
                <div className="h2">
                  {dangerModal.action ===
                    "delete" &&
                    "Delete repository"}

                  {dangerModal.action ===
                    "visibility" &&
                    "Change visibility"}

                  {dangerModal.action ===
                    "transfer" &&
                    "Transfer ownership"}
                </div>

                <div className="sub">
                  This action is performed against
                  the SUTRA backend.
                </div>
              </div>

              <button
                className="iconbtn"
                onClick={closeDangerModal}
                disabled={executing}
              >
                <I.X size={15} />
              </button>
            </div>

            <div className="card-pad">
              {dangerModal.action ===
                "delete" && (
                  <>
                    <div className="sub">
                      This permanently deletes{" "}
                      <b>{repo.name}</b>. Type the exact
                      repository name to continue.
                    </div>

                    <div
                      className="field"
                      style={{ marginTop: 16 }}
                    >
                      <label
                        className="label"
                        htmlFor="confirm-delete"
                      >
                        Repository name
                      </label>

                      <input
                        id="confirm-delete"
                        className="input"
                        value={confirmInput}
                        onChange={(event) =>
                          setConfirmInput(
                            event.target.value,
                          )
                        }
                        autoFocus
                      />
                    </div>
                  </>
                )}

              {dangerModal.action ===
                "visibility" && (
                  <>
                    <div className="sub">
                      Change{" "}
                      <b>{repo.name}</b> from{" "}
                      <b>{repo.visibility}</b> to{" "}
                      <b>{newVisibility}</b>.
                    </div>

                    <div
                      className="field"
                      style={{ marginTop: 16 }}
                    >
                      <label
                        className="label"
                        htmlFor="new-visibility"
                      >
                        New visibility
                      </label>

                      <select
                        id="new-visibility"
                        className="input"
                        value={newVisibility}
                        onChange={(event) =>
                          setNewVisibility(
                            event.target
                              .value as
                            | "public"
                            | "private",
                          )
                        }
                      >
                        <option value="public">
                          Public
                        </option>
                        <option value="private">
                          Private
                        </option>
                      </select>
                    </div>

                    <div
                      className="field"
                      style={{ marginTop: 16 }}
                    >
                      <label
                        className="label"
                        htmlFor="confirm-visibility"
                      >
                        Type confirmation
                      </label>

                      <input
                        id="confirm-visibility"
                        className="input"
                        placeholder={`make ${newVisibility}`}
                        value={confirmInput}
                        onChange={(event) =>
                          setConfirmInput(
                            event.target.value,
                          )
                        }
                      />
                    </div>
                  </>
                )}

              {dangerModal.action ===
                "transfer" && (
                  <>
                    <div className="sub">
                      Transfer{" "}
                      <b>{repo.name}</b> from{" "}
                      <b>{repoOwner}</b> to another owner.
                    </div>

                    <div
                      className="field"
                      style={{ marginTop: 16 }}
                    >
                      <label
                        className="label"
                        htmlFor="new-owner"
                      >
                        New owner
                      </label>

                      <input
                        id="new-owner"
                        className="input"
                        placeholder="username"
                        value={newOwnerInput}
                        onChange={(event) =>
                          setNewOwnerInput(
                            event.target.value,
                          )
                        }
                      />
                    </div>

                    <div className="field">
                      <label
                        className="label"
                        htmlFor="confirm-transfer"
                      >
                        Type confirmation
                      </label>

                      <input
                        id="confirm-transfer"
                        className="input"
                        placeholder="transfer ownership"
                        value={confirmInput}
                        onChange={(event) =>
                          setConfirmInput(
                            event.target.value,
                          )
                        }
                      />
                    </div>
                  </>
                )}

              <div
                className="actions"
                style={{
                  marginTop: 18,
                  justifyContent:
                    "flex-end",
                }}
              >
                <Btn
                  onClick={closeDangerModal}
                  disabled={executing}
                >
                  Cancel
                </Btn>

                <Btn
                  primary={
                    dangerModal.action !==
                    "delete"
                  }
                  onClick={() =>
                    void executeDangerAction()
                  }
                  disabled={
                    !confirmEnabled ||
                    executing
                  }
                >
                  {executing
                    ? "Working…"
                    : dangerModal.action ===
                      "delete"
                      ? "Delete repository"
                      : dangerModal.action ===
                        "visibility"
                        ? "Change visibility"
                        : "Transfer ownership"}
                </Btn>
              </div>
            </div>
          </Card>
        </div>
      )}

      {toast && (
        <div
          className="card"
          style={{
            position: "fixed",
            right: 24,
            bottom: 24,
            zIndex: 120,
            maxWidth: 420,
            borderColor: toast.ok
              ? "rgba(105,230,168,.22)"
              : "rgba(255,127,146,.25)",
          }}
        >
          <div className="card-pad">
            <div className="title-sm">
              {toast.msg}
            </div>
          </div>
        </div>
      )}
    </>
  );
}

function ProtectionFlag({
  enabled,
  label,
}: {
  enabled: boolean;
  label: string;
}) {
  return (
    <div
      className="row"
      style={{
        justifyContent: "flex-start",
        gap: 8,
      }}
    >
      {enabled ? (
        <I.CheckCircle2
          size={14}
          style={{ color: "#69e6a8" }}
        />
      ) : (
        <I.XCircle
          size={14}
          style={{ color: "#637983" }}
        />
      )}

      <span className="meta">
        {label}
      </span>
    </div>
  );
}

function BranchProtectionEditor({
  rule,
  onChange,
  onCancel,
  onSave,
  saving,
}: {
  rule: BranchProtectionRule;
  onChange: (
    rule: BranchProtectionRule,
  ) => void;
  onCancel: () => void;
  onSave: (
    rule: BranchProtectionRule,
  ) => Promise<void>;
  saving: boolean;
}) {
  const update = (
    patch: Partial<BranchProtectionRule>,
  ) => {
    onChange({
      ...rule,
      ...patch,
    });
  };

  return (
    <div style={{ width: "100%" }}>
      <div className="field">
        <label className="label">
          Branch pattern
        </label>

        <input
          className="input"
          value={rule.branch_pattern}
          onChange={(event) =>
            update({
              branch_pattern:
                event.target.value,
            })
          }
          disabled={saving}
        />
      </div>

      <div className="field">
        <label className="label">
          Required approvals
        </label>

        <input
          className="input"
          type="number"
          min={0}
          step={1}
          value={
            rule.required_approvals
          }
          onChange={(event) =>
            update({
              required_approvals:
                Number.isFinite(
                  Number(event.target.value),
                )
                  ? Number(
                    event.target.value,
                  )
                  : 0,
            })
          }
          disabled={saving}
        />
      </div>

      <div className="grid g2">
        <ToggleField
          label="Enabled"
          checked={rule.enabled}
          onChange={(checked) =>
            update({
              enabled: checked,
            })
          }
        />

        <ToggleField
          label="Require change review"
          checked={
            rule.require_change_review
          }
          onChange={(checked) =>
            update({
              require_change_review:
                checked,
            })
          }
        />

        <ToggleField
          label="Require clean conflicts"
          checked={
            rule.require_clean_conflict
          }
          onChange={(checked) =>
            update({
              require_clean_conflict:
                checked,
            })
          }
        />

        <ToggleField
          label="Require resolved threads"
          checked={
            rule.require_resolved_threads
          }
          onChange={(checked) =>
            update({
              require_resolved_threads:
                checked,
            })
          }
        />

        <ToggleField
          label="Require agent review"
          checked={
            rule.require_agent_review
          }
          onChange={(checked) =>
            update({
              require_agent_review:
                checked,
            })
          }
        />

        <ToggleField
          label="Block blocking agent findings"
          checked={
            rule.require_no_blocking_agent_findings
          }
          onChange={(checked) =>
            update({
              require_no_blocking_agent_findings:
                checked,
            })
          }
        />

        <ToggleField
          label="Allow author self-approval"
          checked={
            rule.allow_author_self_approval
          }
          onChange={(checked) =>
            update({
              allow_author_self_approval:
                checked,
            })
          }
        />

        <ToggleField
          label="Require CI passed"
          checked={
            rule.require_ci_passed
          }
          onChange={(checked) =>
            update({
              require_ci_passed:
                checked,
            })
          }
        />
      </div>

      <div
        className="actions"
        style={{ marginTop: 16 }}
      >
        <Btn
          onClick={onCancel}
          disabled={saving}
        >
          Cancel
        </Btn>

        <Btn
          primary
          onClick={() =>
            void onSave(rule)
          }
          disabled={saving}
        >
          {saving
            ? "Saving…"
            : rule.id
              ? "Save rule"
              : "Create rule"}
        </Btn>
      </div>
    </div>
  );
}

function ToggleField({
  label,
  checked,
  onChange,
}: {
  label: string;
  checked: boolean;
  onChange: (checked: boolean) => void;
}) {
  return (
    <button
      type="button"
      className="btn"
      onClick={() =>
        onChange(!checked)
      }
      style={{
        minHeight: 38,
        justifyContent:
          "space-between",
        textAlign: "left",
      }}
    >
      <span>{label}</span>

      <Badge
        tone={
          checked ? "green" : ""
        }
      >
        {checked
          ? "Enabled"
          : "Disabled"}
      </Badge>
    </button>
  );
}

function DangerActionCard({
  title,
  description,
  actionLabel,
  onClick,
  danger = false,
}: {
  title: string;
  description: string;
  actionLabel: string;
  onClick: () => void;
  danger?: boolean;
}) {
  return (
    <div
      className="card"
      style={{
        borderColor: danger
          ? "rgba(255,127,146,.18)"
          : "var(--line)",
      }}
    >
      <div className="card-pad">
        <div className="h2">
          {title}
        </div>

        <div
          className="sub"
          style={{
            margin:
              "8px 0 16px",
          }}
        >
          {description}
        </div>

        <Btn
          onClick={onClick}
          style={{
            width: "100%",
            justifyContent:
              "center",
          } as React.CSSProperties}
        >
          {actionLabel}
        </Btn>
      </div>
    </div>
  );
}

/* -------------------------------------------------------------------------- */
/* New Repository                                                             */
/* -------------------------------------------------------------------------- */


/* -------------------------------------------------------------------------- */
/* Changes                                                                    */
/* -------------------------------------------------------------------------- */

export function Changes() {
  return (
    <>
      <PageHead
        eyebrow="Engineering"
        title="Changes"
        sub="Every proposed code change, from agent draft to human-approved merge."
        action={
          <Btn primary>
            <I.Plus size={14} /> New Change
          </Btn>
        }
      />

      <div
        className="grid g4"
        style={{ marginBottom: 15 }}
      >
        <Stat label="Open" value="12" />
        <Stat label="Agent-authored" value="7" />
        <Stat
          label="Awaiting review"
          value="4"
        />
        <Stat label="Blocked" value="1" />
      </div>

      <Card>
        <div className="list">
          {[
            "Add trace event streaming",
            "Refactor repository permission checks",
            "Improve CI artifact viewer",
            "Add rollback safety guard",
            "Fix stale task assignment",
            "Update agent tool policy",
          ].map((x, i) => (
            <Link
              href={`/changes/${482 - i}`}
              className="list-row"
              key={x}
            >
              <div
                className="avatar"
                style={{
                  width: 29,
                  height: 29,
                }}
              >
                {i % 2 ? "AS" : "A"}
              </div>

              <div
                style={{ flex: 1 }}
              >
                <div className="title-sm">
                  {x}
                </div>
                <div className="meta">
                  #{482 - i} ·{" "}
                  {i % 2
                    ? "Alex Sharma"
                    : "Atlas"}{" "}
                  · target main ·{" "}
                  {i + 2}h ago
                </div>
              </div>

              <Badge
                tone={
                  i === 0
                    ? "aqua"
                    : i === 3
                      ? "amber"
                      : "green"
                }
              >
                {
                  [
                    "In review",
                    "Checks passed",
                    "Draft",
                    "Blocked",
                    "Ready",
                    "In review",
                  ][i]
                }
              </Badge>

              <span className="meta">
                CI {i === 3 ? "×" : "✓"}
              </span>
            </Link>
          ))}
        </div>
      </Card>
    </>
  );
}

/* -------------------------------------------------------------------------- */
/* Change Detail                                                              */
/* -------------------------------------------------------------------------- */

export function ChangeDetail() {
  return (
    <>
      <PageHead
        eyebrow="Change #482"
        title="Add trace event streaming"
        sub="Atlas → main · opened 14 minutes ago"
        action={
          <>
            <Btn>
              Request changes
            </Btn>
            <Btn primary>
              <I.Check size={14} /> Approve & merge
            </Btn>
          </>
        }
      />

      <Pipeline />

      <div className="grid g2">
        <Card>
          <div className="card-head">
            <div>
              <div className="h2">
                Diff
              </div>
              <div className="sub">
                7 files · +184 −39
              </div>
            </div>

            <Badge tone="green">
              Clean
            </Badge>
          </div>

          <div className="diff">
            <div className="ctx">
              @@ src/events/stream.ts
            </div>

            <div className="del">
              - export function emit(event: Event) {"{"}
            </div>

            <div className="add">
              + export async function emit(event: Event) {"{"}
            </div>

            <div className="add">
              + await bus.publish(event);
            </div>

            <div className="ctx">
              {"}"}
            </div>

            <br />

            <div className="ctx">
              @@ src/agents/executor.ts
            </div>

            <div className="add">
              + trace.stream('agent.step', step);
            </div>

            <div className="add">
              + trace.stream('tool.call', toolCall);
            </div>
          </div>
        </Card>

        <Card>
          <div className="card-head">
            <div className="h2">
              Checks
            </div>
            <Badge tone="green">
              Passed
            </Badge>
          </div>

          <div className="list">
            {[
              "CI / unit tests",
              "TypeScript",
              "Security scan",
              "Branch protection",
              "Agent review",
            ].map((x, i) => (
              <div
                className="list-row"
                key={x}
              >
                <I.CheckCircle2
                  size={15}
                  style={{
                    color: "#69e6a8",
                  }}
                />

                <div
                  style={{
                    flex: 1,
                  }}
                >
                  <div className="title-sm">
                    {x}
                  </div>
                  <div className="meta">
                    {i === 4
                      ? "1 finding · low"
                      : `Passed in ${i + 2}m`}
                  </div>
                </div>
              </div>
            ))}
          </div>

          <div className="card-pad">
            <div className="eyebrow">
              Review summary
            </div>

            <div className="sub">
              The change is scoped, tests cover the
              streaming path, and no new high-risk
              permissions are introduced.
            </div>
          </div>
        </Card>
      </div>

      <Card style={{ marginTop: 14 }}>
        <div className="card-head">
          <div className="h2">
            Discussion
          </div>
          <Badge>
            4 comments
          </Badge>
        </div>

        <div className="card-pad">
          <div className="activity">
            <div className="avatar">
              AS
            </div>

            <div>
              <div className="title-sm">
                Looks good. Can we keep event payloads immutable?
              </div>
              <div className="meta">
                Alex · 8 minutes ago
              </div>
            </div>
          </div>

          <div className="activity">
            <div className="avatar">
              AT
            </div>

            <div>
              <div className="title-sm">
                Yes — the stream receives a frozen snapshot.
              </div>
              <div className="meta">
                Atlas · 6 minutes ago
              </div>
            </div>
          </div>
        </div>
      </Card>
    </>
  );
}

/* -------------------------------------------------------------------------- */
/* Pull Requests                                                              */
/* -------------------------------------------------------------------------- */

export function PullRequests() {
  return (
    <>
      <PageHead
        eyebrow="Delivery"
        title="Pull Requests"
        sub="Finalized changes ready for merge, release, or audit."
        action={<Btn>Filter</Btn>}
      />

      <Card>
        <div className="list">
          {[
            "Stream trace events into live UI",
            "Harden agent permissions",
            "Update production deploy pipeline",
            "Add environment approval gates",
            "Refactor CI runner",
          ].map((x, i) => (
            <Link
              href={`/pull-requests/${91 - i}`}
              className="list-row"
              key={x}
            >
              <I.GitPullRequest
                size={15}
                style={{
                  color:
                    i === 2
                      ? "#69e6a8"
                      : "#63e5e8",
                }}
              />

              <div
                style={{
                  flex: 1,
                }}
              >
                <div className="title-sm">
                  {x}
                </div>
                <div className="meta">
                  PR #{91 - i} · opened by{" "}
                  {i % 2 ? "Alex" : "Atlas"} ·{" "}
                  {i + 1}d ago
                </div>
              </div>

              <Badge
                tone={
                  i === 2
                    ? "green"
                    : i === 3
                      ? "amber"
                      : "aqua"
                }
              >
                {
                  [
                    "Ready",
                    "Approved",
                    "Merged",
                    "Pending",
                    "Ready",
                  ][i]
                }
              </Badge>

              <span className="meta">
                {12 + i * 4} comments
              </span>
            </Link>
          ))}
        </div>
      </Card>
    </>
  );
}

/* -------------------------------------------------------------------------- */
/* Pull Request Detail                                                        */
/* -------------------------------------------------------------------------- */

export function PullRequestDetail() {
  return (
    <>
      <PageHead
        eyebrow="Pull Request #91"
        title="Stream trace events into live UI"
        sub="sutra-core · feature/trace-stream → main"
        action={
          <>
            <Btn>Close</Btn>
            <Btn primary>
              <I.GitMerge size={14} /> Merge
            </Btn>
          </>
        }
      />

      <div className="grid g3">
        <Stat label="Commits" value="8" />
        <Stat
          label="Files changed"
          value="7"
        />
        <Stat
          label="Approvals"
          value="2 / 2"
        />
      </div>

      <div
        className="grid g2"
        style={{ marginTop: 14 }}
      >
        <Card>
          <div className="card-head">
            <div className="h2">
              Conversation
            </div>
            <Badge tone="green">
              Approved
            </Badge>
          </div>

          <div className="card-pad">
            <div className="activity">
              <div className="avatar">
                AS
              </div>

              <div>
                <div className="title-sm">
                  Ready to merge after final CI.
                </div>
                <div className="meta">
                  Alex · 12 minutes ago
                </div>
              </div>
            </div>

            <div className="activity">
              <div className="avatar">
                JM
              </div>

              <div>
                <div className="title-sm">
                  Approved. Security review is clean.
                </div>
                <div className="meta">
                  Jordan · 9 minutes ago
                </div>
              </div>
            </div>
          </div>
        </Card>

        <Card>
          <div className="card-head">
            <div className="h2">
              Checks
            </div>
          </div>

          <div className="list">
            {[
              "Build",
              "Tests · 184",
              "Security",
              "Preview deployment",
            ].map((x) => (
              <div
                className="list-row"
                key={x}
              >
                <I.CheckCircle2
                  size={15}
                  style={{
                    color: "#69e6a8",
                  }}
                />
                <span className="title-sm">
                  {x}
                </span>
                <span
                  className="meta"
                  style={{
                    marginLeft: "auto",
                  }}
                >
                  passed
                </span>
              </div>
            ))}
          </div>
        </Card>
      </div>
    </>
  );
}

/* -------------------------------------------------------------------------- */
/* Remaining existing UI screens                                               */
/* -------------------------------------------------------------------------- */

export function Agents() {
  return (
    <>
      <PageHead
        eyebrow="Autonomy"
        title="Agent Gateway"
        sub="Registered agents, credentials, capabilities, and current runs."

      />

      <div className="grid g3">
        {[
          [
            "Atlas",
            "Implementation agent",
            "active",
            "4,821",
          ],
          [
            "Sentinel",
            "Security review",
            "idle",
            "1,982",
          ],
          [
            "Forge",
            "Test generation",
            "active",
            "3,114",
          ],
          [
            "Muse",
            "Documentation",
            "idle",
            "842",
          ],
          [
            "Pilot",
            "Deployment assistant",
            "active",
            "1,203",
          ],
          [
            "Scout",
            "Repository analysis",
            "idle",
            "674",
          ],
        ].map((a, i) => (
          <Link
            href={`/agents/${i + 1}`}
            className="card repo-card"
            key={a[0]}
          >
            <div className="row">
              <div
                className="row"
                style={{
                  justifyContent:
                    "flex-start",
                }}
              >
                <div className="avatar">
                  <I.Bot size={15} />
                </div>

                <div>
                  <div className="repo-name">
                    {a[0]}
                  </div>
                  <div className="meta">
                    {a[1]}
                  </div>
                </div>
              </div>

              <Badge
                tone={
                  a[2] === "active"
                    ? "green"
                    : ""
                }
              >
                {a[2]}
              </Badge>
            </div>

            <div
              className="row"
              style={{ marginTop: 18 }}
            >
              <span className="meta">
                Runs
              </span>
              <span className="title-sm">
                {a[3]}
              </span>
            </div>
          </Link>
        ))}
      </div>
    </>
  );
}

export function AgentDetail() {
  return (
    <>
      <PageHead
        eyebrow="Agent · Atlas"
        title="Atlas"
        sub="Implementation agent · authorized for sutra-core and agent-sdk"
        action={
          <Btn>Rotate token</Btn>
        }
      />

      <div className="grid g4">
        <Stat
          label="Status"
          value="Active"
        />
        <Stat
          label="Runs"
          value="4,821"
        />
        <Stat
          label="Success rate"
          value="96.8%"
        />
        <Stat
          label="Median run"
          value="7m 42s"
        />
      </div>

      <Card style={{ marginTop: 14 }}>
        <div className="card-head">
          <div className="h2">
            Recent runs
          </div>
          <Badge tone="aqua">
            Live
          </Badge>
        </div>

        <div className="list">
          {[
            "Add trace event streaming",
            "Refactor execution context",
            "Fix CI retry policy",
            "Improve change summary",
            "Update repository index",
          ].map((x, i) => (
            <Link
              href={`/agents/1/runs/${8831 - i}`}
              className="list-row"
              key={x}
            >
              <I.Bot
                size={15}
                style={{
                  color: "#63e5e8",
                }}
              />

              <div
                style={{
                  flex: 1,
                }}
              >
                <div className="title-sm">
                  {x}
                </div>
                <div className="meta">
                  Run #{8831 - i} ·{" "}
                  {i + 2} minutes ago · sutra-core
                </div>
              </div>

              <Badge
                tone={
                  i === 2
                    ? "red"
                    : "green"
                }
              >
                {i === 2
                  ? "failed"
                  : "completed"}
              </Badge>

              <span className="meta">
                {
                  [
                    "8m 12s",
                    "5m 49s",
                    "2m 03s",
                    "11m 18s",
                    "4m 31s",
                  ][i]
                }
              </span>
            </Link>
          ))}
        </div>
      </Card>
    </>
  );
}

export function AgentTrace() {
  return (
    <>
      <PageHead
        eyebrow="Run #8831 · Atlas"
        title="Execution Trace"
        sub="Add trace event streaming · 8m 12s · completed successfully"
        action={
          <>
            <Btn>Replay</Btn>
            <Btn primary>
              <I.GitBranch size={14} /> Open Change
            </Btn>
          </>
        }
      />

      <div className="grid g2">
        <Card>
          <div className="card-head">
            <div className="h2">
              Timeline
            </div>
            <Badge tone="green">
              Completed
            </Badge>
          </div>

          <div className="card-pad">
            <div className="timeline">
              {[
                [
                  "Read task context",
                  "12 files inspected · 18s",
                ],
                [
                  "Build execution plan",
                  "6 steps · 41s",
                ],
                [
                  "Inspect repository",
                  "src/events + src/agents · 1m 02s",
                ],
                [
                  "Write implementation",
                  "7 files changed · 2m 48s",
                ],
                [
                  "Run tests",
                  "184 passed · 2m 06s",
                ],
                [
                  "Open Change",
                  "#482 · 37s",
                ],
                [
                  "Final review",
                  "1 low-risk note · 40s",
                ],
              ].map((s) => (
                <div
                  className="step"
                  key={s[0]}
                >
                  <div className="step-card">
                    <div className="step-title">
                      {s[0]}
                    </div>
                    <div className="step-meta">
                      {s[1]}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </Card>

        <Card>
          <div className="card-head">
            <div className="h2">
              Live context
            </div>
            <Badge tone="violet">
              Replayable
            </Badge>
          </div>

          <div className="card-pad">
            <div className="eyebrow">
              Files touched
            </div>

            {[
              "src/events/stream.ts",
              "src/agents/executor.ts",
              "src/agents/context.ts",
              "tests/stream.test.ts",
              "lib/bus.ts",
            ].map((x) => (
              <div
                className="list-row"
                style={{
                  paddingLeft: 0,
                  paddingRight: 0,
                }}
                key={x}
              >
                <I.FileCode2
                  size={14}
                  className="muted"
                />
                <span className="code">
                  {x}
                </span>
              </div>
            ))}

            <div
              className="eyebrow"
              style={{ marginTop: 18 }}
            >
              Result
            </div>

            <div className="sub">
              Change #482 created and all required
              checks passed.
            </div>
          </div>
        </Card>
      </div>
    </>
  );
}

export function RepoAgents() {
  return (
    <>
      <PageHead
        eyebrow="sutra-core"
        title="Repo Agents"
        sub="Agents with access to this repository and the capabilities they can exercise."
        action={
          <Btn primary>
            <I.Plus size={14} /> Add agent
          </Btn>
        }
      />

      <Card>
        <table className="table">
          <thead>
            <tr>
              <th>Agent</th>
              <th>Capabilities</th>
              <th>Last activity</th>
              <th>Status</th>
              <th />
            </tr>
          </thead>

          <tbody>
            {[
              [
                "Atlas",
                "read · write · test · change",
                "2m ago",
                "Active",
              ],
              [
                "Sentinel",
                "read · security scan · review",
                "18m ago",
                "Idle",
              ],
              [
                "Forge",
                "read · test · change",
                "1h ago",
                "Idle",
              ],
              [
                "Pilot",
                "read · deploy · rollback",
                "3h ago",
                "Idle",
              ],
            ].map((a) => (
              <tr key={a[0]}>
                <td>
                  <div
                    className="row"
                    style={{
                      justifyContent:
                        "flex-start",
                    }}
                  >
                    <div
                      className="avatar"
                      style={{
                        width: 25,
                        height: 25,
                      }}
                    >
                      <I.Bot size={13} />
                    </div>
                    <span>{a[0]}</span>
                  </div>
                </td>

                <td>{a[1]}</td>
                <td>{a[2]}</td>

                <td>
                  <Badge
                    tone={
                      a[3] === "Active"
                        ? "green"
                        : ""
                    }
                  >
                    {a[3]}
                  </Badge>
                </td>

                <td>
                  <I.MoreHorizontal size={15} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </Card>
    </>
  );
}

export function Assistant() {
  return (
    <>
      <PageHead
        eyebrow="Intelligence"
        title="AI Assistant"
        sub="Ask questions about your repository's code, dependencies, changes, and history."
        action={
          <Badge tone="aqua">
            Knowledge Graph connected
          </Badge>
        }
      />

      <Card>
        <div
          style={{
            minHeight: 560,
            display: "flex",
            flexDirection: "column",
          }}
        >
          <div
            className="card-pad"
            style={{ flex: 1 }}
          >
            <div className="activity">
              <div className="avatar">
                <I.Sparkles size={14} />
              </div>

              <div>
                <div className="title-sm">
                  SUTRA Assistant
                </div>

                <div
                  className="sub"
                  style={{ marginTop: 6 }}
                >
                  I have indexed{" "}
                  <b>842 files</b>, 12 open changes,
                  and the current main branch. Ask me
                  anything about the system.
                </div>
              </div>
            </div>

            <div
              className="card"
              style={{
                margin:
                  "30px 80px",
                padding: 16,
              }}
            >
              <div className="title-sm">
                What does auth middleware
                depend on?
              </div>

              <div
                className="sub"
                style={{ marginTop: 8 }}
              >
                auth/middleware.ts depends on
                session.ts, policy.ts, and the
                repository identity provider. The path
                is 4 nodes deep.
              </div>
            </div>
          </div>

          <div
            style={{
              padding: 14,
              borderTop:
                "1px solid var(--line)",
            }}
          >
            <div className="row">
              <input
                className="input"
                placeholder="Ask about this repository..."
              />

              <Btn primary>
                <I.ArrowUpRight size={14} /> Ask
              </Btn>
            </div>
          </div>
        </div>
      </Card>
    </>
  );
}

export function CI() {
  return (
    <>
      <PageHead
        eyebrow="Delivery"
        title="CI / Pipelines"
        sub="Every build, test, scan, and preview run across your repositories."
        action={<Btn>New pipeline</Btn>}
      />

      <div className="grid g4">
        <Stat label="Running" value="03" />
        <Stat
          label="Passed today"
          value="182"
        />
        <Stat
          label="Failed today"
          value="04"
        />
        <Stat
          label="Median build"
          value="4m 12s"
        />
      </div>

      <Card style={{ marginTop: 14 }}>
        <div className="list">
          {[
            "sutra-core · Change #482",
            "agent-sdk · PR #88",
            "dashboard · main",
            "infra · deploy-prod",
            "knowledge-engine · PR #71",
            "sutra-core · nightly",
          ].map((x, i) => (
            <Link
              href={`/ci/${1200 - i}`}
              className="list-row"
              key={x}
            >
              <div
                className="activity-dot"
                style={{
                  background:
                    i === 3
                      ? "#63e5e8"
                      : i === 2
                        ? "#ffd37b"
                        : "#69e6a8",
                }}
              />

              <div
                style={{ flex: 1 }}
              >
                <div className="title-sm">
                  {x}
                </div>
                <div className="meta">
                  build #{1200 - i} · triggered{" "}
                  {i + 2}m ago
                </div>
              </div>

              <Badge
                tone={
                  i === 2
                    ? "amber"
                    : i === 3
                      ? "aqua"
                      : "green"
                }
              >
                {
                  [
                    "passed",
                    "passed",
                    "running",
                    "running",
                    "passed",
                    "passed",
                  ][i]
                }
              </Badge>

              <span className="meta">
                {
                  [
                    "4m 18s",
                    "3m 42s",
                    "1m 08s",
                    "2m 31s",
                    "5m 04s",
                    "6m 12s",
                  ][i]
                }
              </span>
            </Link>
          ))}
        </div>
      </Card>
    </>
  );
}

export function CIJob() {
  return (
    <>
      <PageHead
        eyebrow="Build #1200"
        title="sutra-core / Change #482"
        sub="CI job · 4m 18s · exit code 0"
        action={
          <>
            <Btn>Download logs</Btn>
            <Btn primary>
              Rerun
            </Btn>
          </>
        }
      />

      <div className="grid g3">
        <Stat
          label="Status"
          value="Passed"
        />
        <Stat
          label="Tests"
          value="184 / 184"
        />
        <Stat
          label="Artifacts"
          value="06"
        />
      </div>

      <Card style={{ marginTop: 14 }}>
        <div className="card-head">
          <div className="h2">
            Job output
          </div>
          <Badge tone="green">
            exit 0
          </Badge>
        </div>

        <div className="terminal">
          <div>$ sutra ci run --change 482</div>
          <div>
            Preparing isolated runner...
          </div>
          <div>
            Installing dependencies ..............{" "}
            <span className="ok">
              done
            </span>
          </div>
          <div>
            Type checking .........................{" "}
            <span className="ok">
              passed
            </span>
          </div>
          <div>
            Unit tests ............................{" "}
            <span className="ok">
              184 passed
            </span>
          </div>
          <div>
            Integration tests ....................{" "}
            <span className="ok">
              42 passed
            </span>
          </div>
          <div>
            Security scan .........................{" "}
            <span className="warn">
              2 low findings
            </span>
          </div>
          <div>
            Building artifact: sutra-core.tgz .....{" "}
            <span className="ok">
              done
            </span>
          </div>
          <div>
            Uploading artifacts ...................{" "}
            <span className="ok">
              done
            </span>
          </div>
          <div>
            <br />
            Process exited with code 0
          </div>
        </div>
      </Card>
    </>
  );
}

export function Environments() {
  return (
    <>
      <PageHead
        eyebrow="Delivery"
        title="Environments"
        sub="Understand what is running where before you ship."
        action={
          <Btn>
            Manage environments
          </Btn>
        }
      />

      <div className="grid g3">
        {[
          [
            "Development",
            "main",
            "a91d02",
            "2m ago",
            "green",
          ],
          [
            "Staging",
            "release/aug",
            "c92b1e",
            "18m ago",
            "aqua",
          ],
          [
            "Production",
            "release/aug",
            "7b91aa",
            "2h ago",
            "violet",
          ],
        ].map((e) => (
          <Card key={e[0]}>
            <div className="card-pad">
              <div className="row">
                <div>
                  <div className="eyebrow">
                    {e[0]}
                  </div>
                  <div className="h2">
                    {e[1]}
                  </div>
                </div>
                <Badge tone={e[4]}>
                  {e[0] === "Production"
                    ? "Healthy"
                    : "Online"}
                </Badge>
              </div>

              <div
                className="code"
                style={{ marginTop: 20 }}
              >
                {e[2]}
              </div>

              <div
                className="meta"
                style={{ marginTop: 6 }}
              >
                Deployed {e[3]}
              </div>

              <div
                className="progress"
                style={{ marginTop: 16 }}
              >
                <span
                  style={{
                    width:
                      e[0] ===
                        "Production"
                        ? "100%"
                        : "78%",
                  }}
                />
              </div>
            </div>
          </Card>
        ))}
      </div>
    </>
  );
}

export function Deployments() {
  return (
    <>
      <PageHead
        eyebrow="Delivery"
        title="Deployments"
        sub="A chronological record of what shipped, when, and by whom."
        action={
          <Btn primary>
            <I.Rocket size={14} /> New deployment
          </Btn>
        }
      />

      <Card>
        <div className="list">
          {[
            "Production · release/aug",
            "Staging · feature/trace-stream",
            "Production · hotfix/auth",
            "Development · main",
            "Staging · agent-sdk",
          ].map((x, i) => (
            <div
              className="list-row"
              key={x}
            >
              <div
                className="activity-dot"
                style={{
                  background:
                    i === 2
                      ? "#ffd37b"
                      : "#69e6a8",
                }}
              />

              <div
                style={{ flex: 1 }}
              >
                <div className="title-sm">
                  {x}
                </div>
                <div className="meta">
                  SHA{" "}
                  {
                    [
                      "7b91aa",
                      "c92b1e",
                      "44fa81",
                      "a91d02",
                      "bc8821",
                    ][i]
                  }{" "}
                  · {i + 1}h ago ·{" "}
                  {i % 2
                    ? "Atlas"
                    : "Alex"}
                </div>
              </div>

              <Badge
                tone={
                  i === 2
                    ? "amber"
                    : "green"
                }
              >
                {i === 2
                  ? "Rolled back"
                  : "Deployed"}
              </Badge>

              <Btn>View</Btn>
            </div>
          ))}
        </div>
      </Card>
    </>
  );
}

export function KnowledgeGraph() {
  return (
    <>
      <PageHead
        eyebrow="Semantic map"
        title="Knowledge Graph"
        sub="Explore dependencies between files, functions, classes, tasks, and changes."
        action={
          <>
            <Btn>
              <I.Search size={13} /> Find symbol
            </Btn>
            <Btn>
              Layout{" "}
              <I.ChevronDown size={13} />
            </Btn>
          </>
        }
      />

      <Card>
        <div className="graph">
          <svg
            viewBox="0 0 900 510"
            preserveAspectRatio="none"
          >
            <path
              d="M120 120 L310 180 L470 110 L640 210 L780 130 M310 180 L390 340 L640 210 L560 390 L780 130 M470 110 L560 390"
              fill="none"
              stroke="rgba(99,229,232,.28)"
              strokeWidth="1"
            />

            <path
              d="M120 120 L390 340 L780 130"
              fill="none"
              stroke="rgba(139,125,255,.22)"
              strokeWidth="1"
            />
          </svg>

          <div
            className="gnode"
            style={{
              left: "10%",
              top: "18%",
            }}
          >
            auth.ts
          </div>

          <div
            className="gnode"
            style={{
              left: "31%",
              top: "31%",
            }}
          >
            session.ts
          </div>

          <div
            className="gnode"
            style={{
              left: "49%",
              top: "17%",
            }}
          >
            policy.ts
          </div>

          <div
            className="gnode"
            style={{
              left: "69%",
              top: "37%",
            }}
          >
            executor.ts
          </div>

          <div
            className="gnode"
            style={{
              left: "42%",
              top: "70%",
            }}
          >
            context.ts
          </div>

          <div
            className="gnode"
            style={{
              left: "83%",
              top: "21%",
            }}
          >
            change.ts
          </div>

          <div
            className="gnode"
            style={{
              left: "61%",
              top: "73%",
            }}
          >
            tests.ts
          </div>
        </div>
      </Card>
    </>
  );
}

export function Insights() {
  const [data, setData] = useState<InsightsData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let mounted = true;
    insightsService.getGlobalInsights()
      .then((res) => {
        if (mounted) {
          setData(res);
          setLoading(false);
        }
      })
      .catch((err) => {
        if (mounted) {
          setError(err?.message || "Failed to load telemetry");
          setLoading(false);
        }
      });
    return () => {
      mounted = false;
    };
  }, []);

  const agentPct = data ? data.agent_changes_percent : 0;
  const humanPct = data ? data.human_changes_percent : 0;
  const leadTimeStr = data ? `${data.lead_time_minutes}m` : "—";
  const deploymentsStr = data ? `${data.deployments_per_week} / wk` : "—";
  const passRateStr = data ? `${data.ci_pass_rate}%` : "—";

  return (
    <>
      <PageHead
        eyebrow="Engineering intelligence"
        title="Insights"
        sub="Signals that explain how your engineering system is behaving across active repositories."
        action={
          <Btn onClick={() => {
            setLoading(true);
            insightsService.getGlobalInsights()
              .then(setData)
              .catch(() => { })
              .finally(() => setLoading(false));
          }}>
            <I.RefreshCw size={13} style={{ marginRight: 6 }} />
            Refresh
          </Btn>
        }
      />

      {loading ? (
        <div style={{ padding: 48, textAlign: "center", color: "var(--muted)" }}>
          <I.Loader size={20} className="spin" style={{ marginBottom: 12 }} />
          <div>Aggregating repository telemetry...</div>
        </div>
      ) : error ? (
        <Card style={{ padding: 24, textAlign: "center" }}>
          <I.AlertCircle size={24} color="var(--red)" style={{ marginBottom: 8 }} />
          <div style={{ color: "var(--fg)", fontWeight: 600 }}>Unable to load insights</div>
          <div style={{ color: "var(--muted)", fontSize: 13, marginTop: 4 }}>{error}</div>
        </Card>
      ) : (
        <>
          <div className="grid g4">
            <Stat
              label="Deployment frequency"
              value={deploymentsStr}
              delta={data && data.deployments_per_week > 0 ? "Active" : "No deployments"}
            />

            <Stat
              label="Avg Lead time"
              value={leadTimeStr}
              delta={data && data.lead_time_minutes > 0 ? "From merged PRs" : "No merges"}
            />

            <Stat
              label="CI pass rate"
              value={passRateStr}
              delta={data && data.ci_pass_rate > 0 ? "Terminal jobs" : "No CI jobs"}
            />

            <Stat
              label="Agent Changes"
              value={`${agentPct}%`}
              delta={`${humanPct}% Human`}
            />
          </div>

          <div
            className="grid g2"
            style={{ marginTop: 14 }}
          >
            <Card>
              <div className="card-head">
                <div className="h2">
                  Agent vs human changes
                </div>
              </div>

              <div className="card-pad">
                <div
                  style={{
                    height: 120,
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    flexDirection: "column",
                    gap: 12,
                  }}
                >
                  <div style={{ display: "flex", gap: 8, width: "100%", height: 24, background: "rgba(255,255,255,0.06)", borderRadius: 6, overflow: "hidden", padding: 3 }}>
                    <div
                      style={{
                        width: `${agentPct || 50}%`,
                        background: "var(--purple)",
                        borderRadius: 4,
                        transition: "width 0.4s ease",
                      }}
                    />
                    <div
                      style={{
                        width: `${humanPct || 50}%`,
                        background: "var(--cyan)",
                        borderRadius: 4,
                        transition: "width 0.4s ease",
                      }}
                    />
                  </div>

                  <div
                    className="row"
                    style={{
                      width: "100%",
                      justifyContent: "space-between",
                    }}
                  >
                    <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                      <span className="meta">Agent</span>
                      <Badge tone="violet">{agentPct}%</Badge>
                      {data && data.agent_lead_time_minutes > 0 && (
                        <span style={{ fontSize: 11, color: "var(--muted)" }}>({data.agent_lead_time_minutes}m avg)</span>
                      )}
                    </div>

                    <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                      <span className="meta">Human</span>
                      <Badge tone="aqua">{humanPct}%</Badge>
                      {data && data.human_lead_time_minutes > 0 && (
                        <span style={{ fontSize: 11, color: "var(--muted)" }}>({data.human_lead_time_minutes}m avg)</span>
                      )}
                    </div>
                  </div>
                </div>
              </div>
            </Card>

            <Card>
              <div className="card-head">
                <div className="h2">
                  Actionable signals
                </div>
              </div>

              <div className="card-pad">
                <div style={{ display: "flex", alignItems: "flex-start", gap: 12, padding: "12px 0" }}>
                  <I.Info size={18} color="var(--cyan)" style={{ marginTop: 2, flexShrink: 0 }} />
                  <div>
                    <div style={{ fontWeight: 600, fontSize: 14, color: "var(--fg)" }}>
                      {data?.actionable_signal || "Telemetry initialized"}
                    </div>
                    <div style={{ fontSize: 13, color: "var(--muted)", marginTop: 4, lineHeight: 1.5 }}>
                      {data?.actionable_signal_details || "SUTRA is monitoring pull requests, changes, CI pipelines, and deployments across all connected repositories."}
                    </div>
                  </div>
                </div>
              </div>
            </Card>
          </div>
        </>
      )}
    </>
  );
}


export function Organizations() {
  return (
    <>
      <PageHead
        eyebrow="Network"
        title="Organizations"
        sub="Teams, repositories, members, and shared engineering policies."
        action={
          <Btn primary>
            <I.Plus size={14} /> Create organization
          </Btn>
        }
      />

      <div className="grid g3">
        {[
          "SUTRA Labs",
          "Northstar Engineering",
          "Open Agent Collective",
        ].map((x, i) => (
          <Card key={x}>
            <div className="card-pad">
              <div className="row">
                <div className="avatar">
                  {x[0]}
                </div>

                <Badge
                  tone={
                    i === 0
                      ? "aqua"
                      : "violet"
                  }
                >
                  {i === 0
                    ? "Owner"
                    : "Member"}
                </Badge>
              </div>

              <div
                className="h2"
                style={{ marginTop: 16 }}
              >
                {x}
              </div>

              <div
                className="sub"
                style={{ marginTop: 6 }}
              >
                {[24, 68, 312][i]} members ·{" "}
                {[18, 42, 128][i]} repositories
              </div>

              <div
                className="row"
                style={{ marginTop: 20 }}
              >
                <span className="meta">
                  Active today
                </span>

                <span className="title-sm">
                  {[12, 34, 119][i]}
                </span>
              </div>
            </div>
          </Card>
        ))}
      </div>
    </>
  );
}

export function Governance() {
  return (
    <>
      <PageHead
        eyebrow="Enterprise"
        title="Governance"
        sub="Set the rules that keep autonomous engineering safe and accountable."
        action={
          <Btn>Export policy</Btn>
        }
      />

      <div className="grid g2">
        <Card>
          <div className="card-head">
            <div className="h2">
              Merge policies
            </div>
            <Badge tone="green">
              Enforced
            </Badge>
          </div>

          <div className="card-pad">
            {[
              "Minimum 2 human approvals",
              "CI must pass on target branch",
              "Security scan required",
              "Agent-created changes require review",
              "Production merges restricted",
            ].map((x) => (
              <div
                className="row"
                style={{
                  padding:
                    "12px 0",
                  borderBottom:
                    "1px solid var(--line)",
                }}
                key={x}
              >
                <span className="title-sm">
                  {x}
                </span>

                <I.CheckCircle2
                  size={15}
                  style={{
                    color:
                      "#69e6a8",
                  }}
                />
              </div>
            ))}
          </div>
        </Card>

        <Card>
          <div className="card-head">
            <div className="h2">
              Agent permissions
            </div>
            <Badge tone="aqua">
              Scoped
            </Badge>
          </div>

          <div className="card-pad">
            {[
              "Read repository",
              "Write branches",
              "Open changes",
              "Trigger CI",
              "Deploy staging",
              "Deploy production",
            ].map((x, i) => (
              <div
                className="row"
                style={{
                  padding:
                    "12px 0",
                  borderBottom:
                    "1px solid var(--line)",
                }}
                key={x}
              >
                <span className="title-sm">
                  {x}
                </span>

                <Badge
                  tone={
                    i < 4
                      ? "green"
                      : "amber"
                  }
                >
                  {i < 4
                    ? "Allowed"
                    : "Approval"}
                </Badge>
              </div>
            ))}
          </div>
        </Card>
      </div>
    </>
  );
}

export function AuditLog() {
  return (
    <>
      <PageHead
        eyebrow="Enterprise"
        title="Audit Log"
        sub="An immutable record of sensitive actions across your organization."
        action={<Btn>Export CSV</Btn>}
      />

      <Card>
        <table className="table">
          <thead>
            <tr>
              <th>Actor</th>
              <th>Action</th>
              <th>Resource</th>
              <th>Time</th>
              <th>Metadata</th>
            </tr>
          </thead>

          <tbody>
            {[
              [
                "Alex Sharma",
                "Approved change",
                "sutra-core #482",
                "2m ago",
                "2 approvals",
              ],
              [
                "Atlas",
                "Opened change",
                "sutra-core #482",
                "14m ago",
                "agent run #8831",
              ],
              [
                "Jordan Mehta",
                "Changed policy",
                "org/governance",
                "41m ago",
                "production rule",
              ],
              [
                "Alex Sharma",
                "Deployed",
                "production",
                "2h ago",
                "SHA 7b91aa",
              ],
              [
                "Sentinel",
                "Security scan",
                "agent-sdk #88",
                "3h ago",
                "0 high findings",
              ],
              [
                "Maya Rao",
                "Invited member",
                "SUTRA Labs",
                "5h ago",
                "m.rao",
              ],
            ].map((a) => (
              <tr key={a.join("-")}>
                <td>{a[0]}</td>
                <td>{a[1]}</td>
                <td className="code">
                  {a[2]}
                </td>
                <td>{a[3]}</td>
                <td>{a[4]}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </Card>
    </>
  );
}

export function Marketplace() {
  return (
    <>
      <PageHead
        eyebrow="Extensions"
        title="Marketplace"
        sub="Agent skills and CI actions that extend your engineering system."
        action={
          <Btn>
            Publish extension
          </Btn>
        }
      />

      <div className="grid g3">
        {[
          [
            "Security Review",
            "Sentinel",
            "Deep security analysis for every Change",
            "4.9",
            "12.4k installs",
          ],
          [
            "Database Migrations",
            "SchemaPilot",
            "Safe, reviewed migration plans",
            "4.8",
            "8.1k installs",
          ],
          [
            "Release Notes",
            "Muse",
            "Generate release notes from merged Changes",
            "4.7",
            "6.2k installs",
          ],
          [
            "Browser Tests",
            "Forge",
            "Generate and run browser regression suites",
            "4.8",
            "5.9k installs",
          ],
          [
            "Dependency Scout",
            "Scout",
            "Find risky dependency updates",
            "4.9",
            "4.2k installs",
          ],
          [
            "Incident Summary",
            "Pulse",
            "Turn deployment incidents into timelines",
            "4.6",
            "2.8k installs",
          ],
        ].map((x) => (
          <Card key={x[0]}>
            <div className="card-pad">
              <div className="row">
                <div className="avatar">
                  <I.Layers3 size={14} />
                </div>

                <Badge tone="violet">
                  Verified
                </Badge>
              </div>

              <div
                className="h2"
                style={{ marginTop: 16 }}
              >
                {x[0]}
              </div>

              <div className="meta">
                {x[1]}
              </div>

              <div
                className="sub"
                style={{
                  margin:
                    "10px 0 16px",
                }}
              >
                {x[2]}
              </div>

              <div className="row">
                <Badge tone="amber">
                  ★ {x[3]}
                </Badge>

                <span className="meta">
                  {x[4]}
                </span>

                <Btn>Install</Btn>
              </div>
            </div>
          </Card>
        ))}
      </div>
    </>
  );
}

export function SearchResults() {
  const searchParams = useSearchParams();
  const initialQ = searchParams?.get("q") || "";
  const [query, setQuery] = useState(initialQ);
  const [results, setResults] = useState<SearchResult[]>([]);
  const [loading, setLoading] = useState(Boolean(initialQ));
  const [error, setError] = useState<string | null>(null);

  const executeSearch = async (term: string) => {
    if (!term || !term.trim()) {
      setResults([]);
      setLoading(false);
      return;
    }
    try {
      setLoading(true);
      setError(null);
      const data = await searchService.search(term.trim());
      setResults(data);
    } catch (err: any) {
      setError(err?.message || "Failed to execute search.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (initialQ) {
      setQuery(initialQ);
      void executeSearch(initialQ);
    }
  }, [initialQ]);

  // Debounced live typing search
  useEffect(() => {
    const trimmed = query.trim();
    if (!trimmed) {
      setResults([]);
      setLoading(false);
      return;
    }
    const handler = setTimeout(() => {
      void executeSearch(trimmed);
    }, 300);
    return () => clearTimeout(handler);
  }, [query]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    void executeSearch(query);
  };

  const repoResults = results.filter(r => r.type === "repository");
  const taskResults = results.filter(r => r.type === "task");
  const prResults = results.filter(r => r.type === "pull_request");
  const issueResults = results.filter(r => r.type === "issue");
  const changeResults = results.filter(r => r.type === "change");
  const actorResults = results.filter(r => r.type === "user" || r.type === "organization");

  return (
    <>
      <PageHead
        eyebrow="Universal Search"
        title="Search"
        sub="Search repositories, tasks, pull requests, issues, changes, and actors across sovereign SUTRA control plane."
      />

      <form onSubmit={handleSubmit} style={{ marginBottom: 20 }}>
        <div
          className="searchbox"
          style={{
            width: "100%",
            height: 44,
            display: "flex",
            alignItems: "center",
            padding: "0 14px",
            background: "var(--card)",
            border: "1px solid var(--line)",
            borderRadius: 8,
            gap: 10,
          }}
        >
          <I.Search size={16} className="muted" />
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search repositories, tasks, PRs, issues, changes... (e.g. 'sutra', '#18', 'sync')"
            style={{
              flex: 1,
              background: "transparent",
              border: "none",
              color: "var(--fg)",
              fontSize: 14,
              outline: "none",
            }}
          />
          <Btn primary sm type="submit" disabled={loading}>
            {loading ? "Searching..." : "Search"}
          </Btn>
        </div>
      </form>

      {error && (
        <Card style={{ marginBottom: 16 }}>
          <div className="card-pad" style={{ color: "#f87171" }}>
            {error}
          </div>
        </Card>
      )}

      {loading ? (
        <Card>
          <div className="card-pad" style={{ textAlign: "center", padding: "48px 20px" }}>
            <div className="sub">Searching engineering control plane...</div>
          </div>
        </Card>
      ) : results.length === 0 && query.trim() ? (
        <Card>
          <div className="card-pad" style={{ textAlign: "center", padding: "48px 20px" }}>
            <I.Search size={32} className="muted" style={{ marginBottom: 12, opacity: 0.4 }} />
            <div className="title-sm" style={{ fontWeight: 600 }}>No results found</div>
            <div className="sub" style={{ marginTop: 4 }}>
              No matches found for &quot;{query}&quot;. Try a repository name, issue #, PR title, or task keyword.
            </div>
          </div>
        </Card>
      ) : results.length === 0 ? (
        <Card>
          <div className="card-pad" style={{ textAlign: "center", padding: "48px 20px" }}>
            <I.Compass size={32} className="muted" style={{ marginBottom: 12, opacity: 0.4 }} />
            <div className="title-sm" style={{ fontWeight: 600 }}>Universal SUTRA Search</div>
            <div className="sub" style={{ marginTop: 4 }}>
              Search across your local and GitHub repositories, tasks, pull requests, issues, changes, and human/agent actors.
            </div>
          </div>
        </Card>
      ) : (
        <div className="grid g2">
          {repoResults.length > 0 && (
            <Card>
              <div className="card-head">
                <div className="h2">Repositories</div>
                <Badge tone="green">{repoResults.length} {repoResults.length === 1 ? "result" : "results"}</Badge>
              </div>
              <div className="list">
                {repoResults.map(repo => (
                  <Link key={repo.url} href={repo.url} className="list-row" style={{ textDecoration: "none", color: "inherit" }}>
                    <I.Box size={16} className="muted" style={{ flexShrink: 0 }} />
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div className="title-sm" style={{ fontWeight: 600 }}>{repo.name}</div>
                      <div className="meta" style={{ marginTop: 2, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                        {repo.description || "Repository"}
                      </div>
                    </div>
                  </Link>
                ))}
              </div>
            </Card>
          )}

          {taskResults.length > 0 && (
            <Card>
              <div className="card-head">
                <div className="h2">Tasks</div>
                <Badge tone="aqua">{taskResults.length} {taskResults.length === 1 ? "result" : "results"}</Badge>
              </div>
              <div className="list">
                {taskResults.map(task => (
                  <Link key={task.url} href={task.url} className="list-row" style={{ textDecoration: "none", color: "inherit" }}>
                    <I.ListTodo size={16} className="cyan" style={{ flexShrink: 0 }} />
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div className="title-sm" style={{ fontWeight: 600 }}>{task.name}</div>
                      <div className="meta" style={{ marginTop: 2, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                        {task.description || "Task"}
                      </div>
                    </div>
                  </Link>
                ))}
              </div>
            </Card>
          )}

          {prResults.length > 0 && (
            <Card>
              <div className="card-head">
                <div className="h2">Pull Requests</div>
                <Badge tone="violet">{prResults.length} {prResults.length === 1 ? "result" : "results"}</Badge>
              </div>
              <div className="list">
                {prResults.map(pr => (
                  <Link key={pr.url} href={pr.url} className="list-row" style={{ textDecoration: "none", color: "inherit" }}>
                    <I.GitPullRequest size={16} className="muted" style={{ flexShrink: 0 }} />
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div className="title-sm" style={{ fontWeight: 600 }}>{pr.name}</div>
                      <div className="meta" style={{ marginTop: 2, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                        {pr.description || "Pull Request"}
                      </div>
                    </div>
                  </Link>
                ))}
              </div>
            </Card>
          )}

          {issueResults.length > 0 && (
            <Card>
              <div className="card-head">
                <div className="h2">Issues</div>
                <Badge tone="amber">{issueResults.length} {issueResults.length === 1 ? "result" : "results"}</Badge>
              </div>
              <div className="list">
                {issueResults.map(issue => (
                  <Link key={issue.url} href={issue.url} className="list-row" style={{ textDecoration: "none", color: "inherit" }}>
                    <I.CircleDot size={16} className="amber" style={{ flexShrink: 0 }} />
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div className="title-sm" style={{ fontWeight: 600 }}>{issue.name}</div>
                      <div className="meta" style={{ marginTop: 2, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                        {issue.description || "Issue"}
                      </div>
                    </div>
                  </Link>
                ))}
              </div>
            </Card>
          )}

          {changeResults.length > 0 && (
            <Card>
              <div className="card-head">
                <div className="h2">Changes</div>
                <Badge tone="blue">{changeResults.length} {changeResults.length === 1 ? "result" : "results"}</Badge>
              </div>
              <div className="list">
                {changeResults.map(change => (
                  <Link key={change.url} href={change.url} className="list-row" style={{ textDecoration: "none", color: "inherit" }}>
                    <I.GitCommit size={16} className="muted" style={{ flexShrink: 0 }} />
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div className="title-sm" style={{ fontWeight: 600 }}>{change.name}</div>
                      <div className="meta" style={{ marginTop: 2, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                        {change.description || "Change"}
                      </div>
                    </div>
                  </Link>
                ))}
              </div>
            </Card>
          )}

          {actorResults.length > 0 && (
            <Card>
              <div className="card-head">
                <div className="h2">Users & Organizations</div>
                <Badge tone="gray">{actorResults.length} {actorResults.length === 1 ? "result" : "results"}</Badge>
              </div>
              <div className="list">
                {actorResults.map(actor => (
                  <Link key={actor.url} href={actor.url} className="list-row" style={{ textDecoration: "none", color: "inherit" }}>
                    <div className="avatar" style={{ width: 28, height: 28, flexShrink: 0 }}>
                      {actor.name.slice(0, 2).toUpperCase()}
                    </div>
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div className="title-sm" style={{ fontWeight: 600 }}>{actor.name}</div>
                      <div className="meta" style={{ marginTop: 2 }}>{actor.type}</div>
                    </div>
                  </Link>
                ))}
              </div>
            </Card>
          )}
        </div>
      )}
    </>
  );
}