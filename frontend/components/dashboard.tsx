"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { Badge, Btn, Card, PageHead, Pipeline, Stat } from "./shell";
import { I } from "../lib/icons";
import { dashboardService, type DashboardData } from "../lib/dashboard";
import { repositoryService, type Repository } from "../lib/repositories";

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

function formatDeploymentStatus(status: string | null | undefined): string {
  if (!status) return "No deployments yet";

  return status
    .replaceAll("_", " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function RepositoryCard({ repo }: { repo: Repository }) {
  return (
    <Link
      href={`/repositories/${encodeURIComponent(repo.name)}`}
      className="card repo-card"
    >
      <div className="row">
        <div className="repo-name">{repo.name}</div>
        <Badge tone={repo.visibility === "private" ? "neutral" : "green"}>
          {repo.visibility}
        </Badge>
      </div>

      <div className="repo-desc">
        {repo.description || "No repository description."}
      </div>

      <div className="row">
        <span className="meta">{repo.default_branch || "No branch"}</span>
        <span className="meta">{relativeTime(repo.updated_at)}</span>
      </div>
    </Link>
  );
}

export function Dashboard() {
  const [data, setData] = useState<DashboardData | null>(null);
  const [repositories, setRepositories] = useState<Repository[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    const load = async (forceRefresh = false) => {
      try {
        if (!data) setLoading(true);
        setError(null);

        const [dashboard, repos] = await Promise.all([
          dashboardService.get({ forceRefresh }),
          repositoryService.listRepositories({ forceRefresh }),
        ]);

        if (cancelled) return;

        setData(dashboard);
        setRepositories(repos);
      } catch (err: any) {
        console.error("Failed to load dashboard:", err);

        if (!cancelled && !data) {
          setError(
            err?.detail ||
              err?.message ||
              "Failed to load workspace dashboard",
          );
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    };

    void load(false);

    // Auto-refresh workspace overview every 20 minutes (1,200,000 ms)
    const refresh = window.setInterval(() => {
      void load(true);
    }, 20 * 60 * 1000);

    return () => {
      cancelled = true;
      window.clearInterval(refresh);
    };
  }, []);

  const ciPassRate = data?.ci.pass_rate;
  const deploymentStatus = data?.deployments.last_status;

  return (
    <>
      <PageHead
        eyebrow="Personal workspace"
        title="Your workspace"
        sub={
          loading
            ? "Loading live engineering activity…"
            : `${data?.repository_count ?? repositories.length} repositories in your workspace.`
        }
        action={
          <>
            <Link href="/changes">
              <Btn>Changes</Btn>
            </Link>
            <Link href="/repositories">
              <Btn>Repositories</Btn>
            </Link>
          </>
        }
      />

      {error && (
        <Card
          style={{
            marginBottom: 14,
            borderColor: "rgba(255,127,146,.25)",
          }}
        >
          <div className="card-pad">
            <div className="sub" style={{ color: "#ff8fa0" }}>
              {error}
            </div>
          </div>
        </Card>
      )}

      {/* Actionable Engineering Attention Strip */}
      {!loading && !error && (
        <Card style={{ marginBottom: 16 }}>
          <div className="card-head" style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <div>
              <div className="h2" style={{ fontSize: 16 }}>Attention Needed</div>
              <div className="sub">Actionable signals requiring engineering or governance intervention</div>
            </div>
            {((data?.blocked_changes ?? 0) > 0 || (data?.changes_needing_review ?? 0) > 0 || (data?.failed_ci_jobs ?? 0) > 0 || (data?.blocked_tasks ?? 0) > 0) ? (
              <Badge tone="amber">Action required</Badge>
            ) : (
              <Badge tone="green">All clear</Badge>
            )}
          </div>
          <div className="card-pad" style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))", gap: 12 }}>
            <Link href="/changes" className="btn outline" style={{ justifyContent: "space-between", display: "flex", padding: "10px 14px", textDecoration: "none" }}>
              <span>Changes needing review</span>
              <span className="badge" style={{ color: (data?.changes_needing_review ?? 0) > 0 ? "var(--cyan)" : "inherit" }}>
                {data?.changes_needing_review ?? 0}
              </span>
            </Link>
            <Link href="/changes" className="btn outline" style={{ justifyContent: "space-between", display: "flex", padding: "10px 14px", textDecoration: "none" }}>
              <span>Blocked changes</span>
              <span className="badge" style={{ color: (data?.blocked_changes ?? 0) > 0 ? "var(--red, #ef4444)" : "inherit" }}>
                {data?.blocked_changes ?? 0}
              </span>
            </Link>
            <Link href="/ci" className="btn outline" style={{ justifyContent: "space-between", display: "flex", padding: "10px 14px", textDecoration: "none" }}>
              <span>Failing CI jobs</span>
              <span className="badge" style={{ color: (data?.failed_ci_jobs ?? 0) > 0 ? "var(--red, #ef4444)" : "inherit" }}>
                {data?.failed_ci_jobs ?? 0}
              </span>
            </Link>
            <Link href="/tasks" className="btn outline" style={{ justifyContent: "space-between", display: "flex", padding: "10px 14px", textDecoration: "none" }}>
              <span>Blocked / failed tasks</span>
              <span className="badge" style={{ color: (data?.blocked_tasks ?? 0) > 0 ? "var(--amber, #f59e0b)" : "inherit" }}>
                {data?.blocked_tasks ?? 0}
              </span>
            </Link>
          </div>
        </Card>
      )}

      <div className="kpi-strip">
        <Link href="/changes" style={{ textDecoration: "none", color: "inherit", display: "block" }}>
          <Card className="card-hover">
            <div className="stat">
              <div className="eyebrow" style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <span>Open changes</span>
                <span style={{ fontSize: 11, color: "var(--accent)", fontWeight: 500 }}>View &rarr;</span>
              </div>
              <div className="num">{loading ? "—" : data?.open_changes ?? 0}</div>
              <div className="delta">
                {loading
                  ? "Loading…"
                  : `${data?.changes_needing_review ?? 0} need review`}
              </div>
            </div>
          </Card>
        </Link>

        <Card>
          <div className="stat">
            <div className="eyebrow">Active agent sessions</div>
            <div className="num">
              {loading ? "—" : data?.active_agent_sessions ?? 0}
            </div>
            <div className="sub">
              Real authenticated agent sessions.
            </div>
          </div>
        </Card>

        <Card>
          <div className="stat">
            <div className="eyebrow">CI pass rate</div>
            <div className="num">
              {loading
                ? "—"
                : ciPassRate === null || ciPassRate === undefined
                  ? "—"
                  : `${ciPassRate}%`}
            </div>
            <div className="sub">
              {loading
                ? "Loading…"
                : `${data?.ci.passed ?? 0} passed · ${data?.ci.failed ?? 0} failed`}
            </div>
          </div>
        </Card>

        <Card>
          <div className="stat">
            <div className="eyebrow">Deployments</div>
            <div className="num">
              {loading ? "—" : data?.deployments.total ?? 0}
            </div>
            <div className="sub">
              {loading
                ? "Loading…"
                : `${formatDeploymentStatus(deploymentStatus)} · ${relativeTime(
                    data?.deployments.last_created_at,
                  )}`}
            </div>
          </div>
        </Card>
      </div>

      <div className="grid g2">
        <Card>
          <div className="card-head">
            <div>
              <div className="h2">Your repositories</div>
              <div className="sub">Live repositories from the SUTRA API</div>
            </div>
            <Link href="/repositories" className="badge orange">
              View all
            </Link>
          </div>

          {loading ? (
            <div className="card-pad">
              <div className="sub">Loading repositories…</div>
            </div>
          ) : repositories.length === 0 ? (
            <div className="card-pad">
              <div className="eyebrow">No repositories</div>
              <div className="h2">Create your first repository.</div>
              <div className="sub" style={{ marginTop: 8 }}>
                SUTRA will populate this workspace automatically once a repository exists.
              </div>
            </div>
          ) : (
            <div className="grid g2" style={{ padding: 14 }}>
              {repositories.slice(0, 4).map((repo) => (
                <RepositoryCard key={repo.id} repo={repo} />
              ))}
            </div>
          )}
        </Card>

        <Card>
          <div className="card-head">
            <div>
              <div className="h2">Live activity</div>
              <div className="sub">Changes, tasks, and deployments from your workspace</div>
            </div>
            <Badge tone="green">Live</Badge>
          </div>

          {loading ? (
            <div className="card-pad">
              <div className="sub">Loading activity…</div>
            </div>
          ) : !data?.activity.length ? (
            <div className="card-pad">
              <div className="sub">No recent activity yet.</div>
            </div>
          ) : (
            <div className="list">
              {data.activity.map((activity) => (
                <Link
                  href={`/repositories/${encodeURIComponent(activity.repo_name)}`}
                  className="activity"
                  key={activity.id}
                >
                  <span className="activity-dot" />
                  <div style={{ minWidth: 0, flex: 1 }}>
                    <p>
                      <b>{activity.actor_name}</b> {activity.action}
                    </p>
                    <span>
                      {activity.repo_name} · {activity.target} · {relativeTime(activity.created_at)}
                    </span>
                  </div>
                </Link>
              ))}
            </div>
          )}
        </Card>
      </div>

      <div className="grid g3" style={{ marginTop: 14 }}>
        <Link href="/changes?actor_type=agent" style={{ textDecoration: "none", color: "inherit", display: "block" }}>
          <Card className="card-hover">
            <div className="stat">
              <div className="eyebrow" style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <span>Agent / human changes</span>
                <span style={{ fontSize: 11, color: "var(--accent)", fontWeight: 500 }}>Agent changes &rarr;</span>
              </div>
              <div className="num">
                {loading
                  ? "—"
                  : `${data?.agent_changes ?? 0} / ${data?.human_changes ?? 0}`}
              </div>
              <div className="sub">
                Actual Change actors in your repositories.
              </div>
            </div>
          </Card>
        </Link>

        <Card>
          <div className="stat">
            <div className="eyebrow">Open security findings</div>
            <div className="num">
              {loading ? "—" : data?.security.open_findings ?? 0}
            </div>
            <div className="sub">
              {loading
                ? "Loading…"
                : `${data?.security.critical ?? 0} critical · ${data?.security.high ?? 0} high · ${
                    data?.security.medium ?? 0
                  } medium · ${data?.security.low ?? 0} low`}
            </div>
          </div>
        </Card>
      </div>
    </>
  );
}
