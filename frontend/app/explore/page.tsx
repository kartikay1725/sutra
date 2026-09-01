"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { AppShell, Badge, Card, PageHead } from "@/components/shell";
import {
  exploreService,
  type TrendingAgent,
  type TrendingDiscussion,
  type TrendingRepository,
} from "@/lib/explore";

function timeLabel(since: "daily" | "weekly" | "monthly") {
  if (since === "weekly") return "This week";
  if (since === "monthly") return "This month";
  return "Today";
}

export default function Page() {
  const [since, setSince] = useState<"daily" | "weekly" | "monthly">("daily");
  const [repositories, setRepositories] = useState<TrendingRepository[]>([]);
  const [discussions, setDiscussions] = useState<TrendingDiscussion[]>([]);
  const [agents, setAgents] = useState<TrendingAgent[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      setLoading(true);
      setError(null);

      const [repoResult, discussionResult, agentResult] = await Promise.allSettled([
        exploreService.getTrendingRepositories(since),
        exploreService.getTrendingDiscussions(),
        exploreService.getTrendingAgents(),
      ]);

      if (cancelled) return;

      if (repoResult.status === "fulfilled") {
        setRepositories(repoResult.value);
      } else {
        setRepositories([]);
      }

      if (discussionResult.status === "fulfilled") {
        setDiscussions(discussionResult.value);
      } else {
        setDiscussions([]);
      }

      if (agentResult.status === "fulfilled") {
        setAgents(agentResult.value);
      } else {
        setAgents([]);
      }

      const failures = [repoResult, discussionResult, agentResult].filter(
        (result) => result.status === "rejected",
      );

      if (failures.length === 3) {
        setError("Explore could not load data from the workspace API.");
      } else if (failures.length > 0) {
        setError("Some Explore sections could not be loaded.");
      }

      setLoading(false);
    }

    void load();
    return () => {
      cancelled = true;
    };
  }, [since]);

  return (
    <AppShell>
      <PageHead
        eyebrow="Network"
        title="Explore"
        sub="Public repositories and discussions surfaced from real SUTRA activity."
        action={
          <div className="row" style={{ gap: 8 }}>
            {(["daily", "weekly", "monthly"] as const).map((value) => (
              <button
                key={value}
                className={"btn " + (since === value ? "primary" : "")}
                onClick={() => setSince(value)}
                type="button"
              >
                {timeLabel(value)}
              </button>
            ))}
          </div>
        }
      />

      {error && (
        <Card style={{ marginBottom: 14 }}>
          <div className="card-pad">
            <div className="sub">{error}</div>
          </div>
        </Card>
      )}

      <div className="grid g3">
        <Card>
          <div className="card-head">
            <div>
              <div className="eyebrow">Trending repositories</div>
              <div className="h2">{timeLabel(since)}</div>
            </div>
          </div>

          {loading ? (
            <div className="card-pad sub">Loading repositories…</div>
          ) : repositories.length === 0 ? (
            <div className="card-pad sub">No public repositories to show yet.</div>
          ) : (
            <div className="list">
              {repositories.slice(0, 5).map((repo) => (
                <Link
                  key={repo.id}
                  href={`/repositories/${repo.name}`}
                  className="list-row"
                  style={{ textDecoration: "none" }}
                >
                  <div style={{ flex: 1 }}>
                    <div className="title-sm">{repo.owner}/{repo.name}</div>
                    <div className="meta">
                      {repo.description || "No description."}
                    </div>
                  </div>
                  <Badge tone="violet">{repo.stars} stars</Badge>
                </Link>
              ))}
            </div>
          )}
        </Card>

        <Card>
          <div className="card-head">
            <div>
              <div className="eyebrow">Trending discussions</div>
              <div className="h2">Recent activity</div>
            </div>
          </div>

          {loading ? (
            <div className="card-pad sub">Loading discussions…</div>
          ) : discussions.length === 0 ? (
            <div className="card-pad sub">No public discussions yet.</div>
          ) : (
            <div className="list">
              {discussions.map((discussion) => (
                <Link
                  key={discussion.id}
                  href={`/repositories/${discussion.repo_name}/discussions/${discussion.id}`}
                  className="list-row"
                  style={{ textDecoration: "none" }}
                >
                  <div style={{ flex: 1 }}>
                    <div className="title-sm">{discussion.title}</div>
                    <div className="meta">
                      {discussion.repo_name} · {discussion.author}
                    </div>
                  </div>
                  <Badge tone="green">
                    {discussion.comments_count} comments
                  </Badge>
                </Link>
              ))}
            </div>
          )}
        </Card>

        <Card>
          <div className="card-head">
            <div>
              <div className="eyebrow">Agents</div>
              <div className="h2">Connected agents</div>
            </div>
          </div>

          {loading ? (
            <div className="card-pad sub">Loading agents…</div>
          ) : agents.length === 0 ? (
            <div className="card-pad">
              <div className="sub">
                No public agent ranking is available yet. Agent access remains private to their owners and explicitly granted repositories.
              </div>
            </div>
          ) : (
            <div className="list">
              {agents.slice(0, 5).map((agent) => (
                <div key={agent.id} className="list-row">
                  <div style={{ flex: 1 }}>
                    <div className="title-sm">{agent.name}</div>
                    <div className="meta">{agent.description}</div>
                  </div>
                  <Badge tone="violet">{agent.runs} runs</Badge>
                </div>
              ))}
            </div>
          )}
        </Card>
      </div>

      <Card style={{ marginTop: 14 }}>
        <div className="card-head">
          <div>
            <div className="eyebrow">What you are seeing</div>
            <div className="h2">Real workspace data only</div>
          </div>
        </div>
        <div className="card-pad sub">
          Explore no longer invents stars, agents, discussion counts, or engineering-growth percentages. Empty API results stay empty instead of being replaced with demo content.
        </div>
      </Card>
    </AppShell>
  );
}
