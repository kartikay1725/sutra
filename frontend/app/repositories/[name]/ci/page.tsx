"use client";

import {
  use,
  useEffect,
  useMemo,
  useState,
} from "react";
import { useRouter } from "next/navigation";

import {
  AppShell,
  PageHead,
  Card,
  Btn,
  Badge,
  SkeletonCIRuns,
} from "@/components/shell";

import {
  ciService,
  type CIJob,
} from "@/lib/ci";

import {
  pullRequestService,
  type PullRequest,
} from "@/lib/pull-requests";

import { repositoryService } from "@/lib/repositories";
import { authService } from "@/lib/auth";

import * as I from "lucide-react";
import { CIWorkflowSetupCard } from "@/components/CIWorkflowSetupCard";

function timeAgo(
  dateStr: string | null | undefined,
) {
  if (!dateStr) {
    return "—";
  }

  const time =
    new Date(dateStr).getTime();

  if (!Number.isFinite(time)) {
    return "—";
  }

  const diff =
    Date.now() - time;

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

  return `${Math.floor(hours / 24)}d ago`;
}

function duration(
  start: string | null,
  end: string | null,
) {
  if (!start) {
    return "—";
  }

  const started =
    new Date(start).getTime();

  const finished = end
    ? new Date(end).getTime()
    : Date.now();

  if (
    !Number.isFinite(started) ||
    !Number.isFinite(finished)
  ) {
    return "—";
  }

  const seconds = Math.max(
    0,
    Math.floor(
      (finished - started) / 1000,
    ),
  );

  if (seconds < 60) {
    return `${seconds}s`;
  }

  return `${Math.floor(
    seconds / 60,
  )}m ${seconds % 60}s`;
}

function statusTone(
  status: string,
) {
  switch (status) {
    case "passed":
      return "green";

    case "failed":
      return "red";

    case "running":
      return "aqua";

    case "pending":
      return "amber";

    default:
      return undefined;
  }
}

function statusIcon(
  status: string,
) {
  switch (status) {
    case "passed":
      return (
        <I.CheckCircle2 size={16} />
      );

    case "failed":
      return (
        <I.XCircle size={16} />
      );

    case "running":
      return (
        <I.Loader
          size={16}
          className="spin"
        />
      );

    case "pending":
      return (
        <I.Circle size={16} />
      );

    case "cancelled":
      return (
        <I.MinusCircle size={16} />
      );

    default:
      return (
        <I.Circle size={16} />
      );
  }
}

function statusLabel(
  status: string,
) {
  return status
    .replaceAll("_", " ")
    .replace(/\b\w/g, (char) =>
      char.toUpperCase(),
    );
}

export default function CIPage({
  params,
}: {
  params: Promise<{
    name: string;
  }>;
}) {
  const { name: repoName } =
    use(params);

  const router = useRouter();

  const [jobs, setJobs] =
    useState<CIJob[]>([]);

  const [prMap, setPrMap] =
    useState<
      Record<string, PullRequest>
    >({});

  const [loading, setLoading] =
    useState(true);

  const [error, setError] =
    useState<string | null>(null);

  const [filter, setFilter] =
    useState("All");

  const [triggering, setTriggering] =
    useState<string | null>(null);

  const [cancelling, setCancelling] =
    useState<string | null>(null);

  const load = async () => {
    try {
      setLoading(true);
      setError(null);

      const user =
        await authService.getCurrentUser().catch(() => null);

      let repo: any = null;
      if (user?.username) {
        repo = await repositoryService.getRepository(
          user.username,
          repoName,
        ).catch(() => null);
      }

      if (!repo) {
        const repos = await repositoryService.listRepositories().catch(() => []);
        repo = repos.find((r: any) => r.name.toLowerCase() === repoName.toLowerCase() || r.id === repoName);
      }

      if (!repo) {
        setJobs([]);
        return;
      }

      const prs =
        await pullRequestService
          .listPRs(repo.id)
          .catch(
            () =>
              [] as PullRequest[],
          );

      const lookup: Record<
        string,
        PullRequest
      > = {};

      for (const pr of prs) {
        lookup[pr.id] = pr;
      }

      setPrMap(lookup);

      const jobArrays =
        await Promise.all(
          prs.map((pr) =>
            ciService
              .listJobsForPR(pr.id)
              .catch(
                () => [] as CIJob[],
              ),
          ),
        );

      const allJobs =
        jobArrays
          .flat()
          .sort(
            (a, b) =>
              new Date(
                b.created_at,
              ).getTime() -
              new Date(
                a.created_at,
              ).getTime(),
          );

      setJobs(allJobs);
    } catch (err: any) {
      console.error(
        "Failed to load CI:",
        err,
      );

      setError(
        err?.detail ||
          err?.message ||
          "Failed to load CI runs.",
      );
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void load();
  }, [repoName]);

  const filtered = useMemo(() => {
    if (filter === "All") {
      return jobs;
    }

    return jobs.filter(
      (job) =>
        job.status ===
        filter.toLowerCase(),
    );
  }, [jobs, filter]);

  const stats = {
    running: jobs.filter(
      (job) =>
        job.status ===
        "running",
    ).length,

    passed: jobs.filter(
      (job) =>
        job.status ===
        "passed",
    ).length,

    failed: jobs.filter(
      (job) =>
        job.status ===
        "failed",
    ).length,

    pending: jobs.filter(
      (job) =>
        job.status ===
        "pending",
    ).length,
  };

  const completedRuns =
    stats.passed +
    stats.failed;

  const passRate =
    completedRuns > 0
      ? Math.round(
          (stats.passed /
            completedRuns) *
            100,
        )
      : null;

  const handleTrigger = async (
    prId: string,
  ) => {
    try {
      setTriggering(prId);
      setError(null);

      await ciService.triggerRun(
        prId,
      );

      await load();
    } catch (err: any) {
      setError(
        err?.detail ||
          err?.message ||
          "Failed to trigger CI run.",
      );
    } finally {
      setTriggering(null);
    }
  };

  const handleCancel = async (
    job: CIJob,
  ) => {
    try {
      setCancelling(job.id);
      setError(null);

      await ciService.cancelJob(
        job.pull_request_id,
        job.id,
      );

      await load();
    } catch (err: any) {
      setError(
        err?.detail ||
          err?.message ||
          "Failed to cancel CI run.",
      );
    } finally {
      setCancelling(null);
    }
  };

  const recent =
    filtered;

  const openPRs =
    Object.values(prMap).filter(
      (pr) =>
        pr.status === "open",
    );

  return (
    <AppShell>
      <PageHead
        eyebrow={repoName}
        title="CI / Pipelines"
        sub="Build, test and validate every change."
      />

      <div
        style={{
          width: "100%",
        }}
      >
        {error && (
          <Card
            style={{
              marginBottom: 16,
              borderColor:
                "rgba(239,68,68,.25)",
            }}
          >
            <div className="card-pad">
              <div
                className="sub"
                style={{
                  color:
                    "var(--red)",
                }}
              >
                {error}
              </div>
            </div>
          </Card>
        )}

        {/* Real stats */}
        <div className="ci-stats-grid">
          <MetricCard
            label="Running"
            value={stats.running}
            icon={
              <I.Loader size={16} />
            }
            tone="aqua"
          />

          <MetricCard
            label="Passed"
            value={stats.passed}
            icon={
              <I.CheckCircle2
                size={16}
              />
            }
            tone="green"
          />

          <MetricCard
            label="Failed"
            value={stats.failed}
            icon={
              <I.XCircle size={16} />
            }
            tone="red"
          />

          <MetricCard
            label="Pass Rate"
            value={
              passRate === null
                ? "—"
                : `${passRate}%`
            }
            icon={
              <I.TrendingUp
                size={16}
              />
            }
            tone="violet"
          />
        </div>

        {/* Filter */}
        <div
          style={{
            display: "flex",
            gap: 4,
            marginBottom: 20,
            overflowX: "auto",
          }}
        >
          {[
            "All",
            "Running",
            "Failed",
            "Passed",
            "Pending",
            "Cancelled",
          ].map((value) => (
            <button
              key={value}
              type="button"
              onClick={() =>
                setFilter(value)
              }
              style={{
                background:
                  filter === value
                    ? "var(--bg-subtle)"
                    : "transparent",
                border: "1px solid",
                borderColor:
                  filter === value
                    ? "var(--line)"
                    : "transparent",
                color:
                  filter === value
                    ? "var(--fg)"
                    : "var(--muted)",
                padding:
                  "6px 14px",
                borderRadius: 6,
                cursor:
                  "pointer",
                fontSize: 13,
                fontWeight:
                  filter === value
                    ? 600
                    : 400,
                whiteSpace:
                  "nowrap",
              }}
            >
              {value}
            </button>
          ))}
        </div>

        {/* GitHub Actions Setup & CI Policy Card */}
        <div style={{ marginBottom: 20 }}>
          <CIWorkflowSetupCard
            repoName={repoName}
            defaultExpanded={jobs.length === 0}
          />
        </div>

        {loading ? (
          <SkeletonCIRuns count={5} />
        ) : recent.length === 0 ? (
          jobs.length === 0 ? null : (
            <Card>
              <div
                className="card-pad"
                style={{
                  textAlign: "center",
                  paddingTop: 56,
                  paddingBottom: 56,
                }}
              >
                <I.PlaySquare
                  size={30}
                  style={{
                    opacity: 0.35,
                    marginBottom: 12,
                  }}
                />

                <div className="h2">
                  No matching CI runs
                </div>

                <div
                  className="sub"
                  style={{
                    maxWidth: 460,
                    margin: "8px auto 0",
                  }}
                >
                  Try selecting another status filter above.
                </div>
              </div>
            </Card>
          )
        ) : (
          <Card
            style={{
              padding: 0,
              overflow: "hidden",
            }}
          >
            <div
              className="card-head"
              style={{
                padding:
                  "14px 20px",
              }}
            >
              <div>
                <div className="h2">
                  CI Runs
                </div>

                <div className="sub">
                  {recent.length}{" "}
                  {recent.length ===
                  1
                    ? "run"
                    : "runs"}
                </div>
              </div>
            </div>

            <div className="list">
              {recent.map(
                (job) => {
                  const pr =
                    prMap[
                      job.pull_request_id
                    ];

                  const isRunning =
                    job.status ===
                    "running";

                  return (
                    <div
                      key={job.id}
                      className="list-row"
                      style={{
                        alignItems:
                          "flex-start",
                        cursor:
                          "pointer",
                      }}
                      onClick={() =>
                        router.push(
                          `/repositories/${encodeURIComponent(
                            repoName,
                          )}/ci/${encodeURIComponent(
                            job.id,
                          )}?pr=${encodeURIComponent(
                            job.pull_request_id,
                          )}`,
                        )
                      }
                    >
                      <div
                        style={{
                          paddingTop: 2,
                          color:
                            statusTone(
                              job.status,
                            ) ===
                            "green"
                              ? "var(--green)"
                              : statusTone(
                                    job.status,
                                  ) ===
                                  "red"
                                ? "var(--red)"
                                : statusTone(
                                      job.status,
                                    ) ===
                                    "aqua"
                                  ? "var(--cyan)"
                                  : "var(--muted)",
                        }}
                      >
                        {statusIcon(
                          job.status,
                        )}
                      </div>

                      <div
                        style={{
                          flex: 1,
                          minWidth: 0,
                        }}
                      >
                        <div
                          className="title-sm"
                          style={{
                            marginBottom:
                              5,
                          }}
                        >
                          {pr?.title ||
                            `CI Run ${job.id.slice(
                              0,
                              8,
                            )}`}
                        </div>

                        <div
                          className="meta"
                          style={{
                            fontFamily:
                              "monospace",
                          }}
                        >
                          {job.commit_sha.slice(
                            0,
                            8,
                          )}
                          {" "}
                          →{" "}
                          {job.target_branch}

                          {pr?.number
                            ? ` · PR #${pr.number}`
                            : ""}
                        </div>

                        <div
                          className="meta"
                          style={{
                            marginTop:
                              5,
                          }}
                        >
                          Trigger:{" "}
                          {job.trigger ||
                            "unknown"}
                          {" · "}
                          Runner:{" "}
                          {job.runner_type ||
                            "unknown"}
                        </div>

                        {job.failure_reason && (
                          <div
                            className="meta"
                            style={{
                              color:
                                "var(--red)",
                              marginTop:
                                6,
                            }}
                          >
                            {job.failure_reason}
                          </div>
                        )}

                        {job.exit_code !==
                          null &&
                          job.exit_code !==
                            undefined && (
                            <div
                              className="meta"
                              style={{
                                marginTop:
                                  4,
                              }}
                            >
                              Exit code:{" "}
                              {
                                job.exit_code
                              }
                            </div>
                          )}
                      </div>

                      <div
                        style={{
                          display:
                            "flex",
                          flexDirection:
                            "column",
                          alignItems:
                            "flex-end",
                          gap: 7,
                          flexShrink: 0,
                        }}
                      >
                        <Badge
                          tone={
                            statusTone(
                              job.status,
                            ) as any
                          }
                        >
                          {statusLabel(
                            job.status,
                          )}
                        </Badge>

                        <span className="meta">
                          {duration(
                            job.started_at,
                            job.completed_at,
                          )}
                        </span>

                        <span className="meta">
                          {timeAgo(
                            job.created_at,
                          )}
                        </span>

                        {isRunning && (
                          <Btn
                            onClick={(
                              event,
                            ) => {
                              event.stopPropagation();

                              void handleCancel(
                                job,
                              );
                            }}
                            disabled={
                              cancelling ===
                              job.id
                            }
                            style={{
                              fontSize: 11,
                            }}
                          >
                            {cancelling ===
                            job.id
                              ? "Cancelling..."
                              : "Cancel"}
                          </Btn>
                        )}

                        <Btn
                          onClick={(
                            event,
                          ) => {
                            event.stopPropagation();

                            router.push(
                              `/repositories/${encodeURIComponent(
                                repoName,
                              )}/ci/${encodeURIComponent(
                                job.id,
                              )}?pr=${encodeURIComponent(
                                job.pull_request_id,
                              )}`,
                            );
                          }}
                          style={{
                            fontSize: 11,
                          }}
                        >
                          View Logs
                          <I.ArrowRight
                            size={11}
                            style={{
                              marginLeft: 4,
                            }}
                          />
                        </Btn>
                      </div>
                    </div>
                  );
                },
              )}
            </div>
          </Card>
        )}

        {/* Trigger CI */}
        {openPRs.length > 0 && (
          <Card
            style={{
              marginTop: 20,
            }}
          >
            <div className="card-head">
              <div>
                <div className="h2">
                  Trigger a run
                </div>

                <div className="sub">
                  Run CI manually for an
                  open Pull Request.
                </div>
              </div>

              <Badge>
                {openPRs.length} open{" "}
                {openPRs.length === 1
                  ? "PR"
                  : "PRs"}
              </Badge>
            </div>

            <div className="list">
              {openPRs
                .slice(0, 10)
                .map((pr) => (
                  <div
                    key={pr.id}
                    className="list-row"
                  >
                    <I.GitPullRequest
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
                        {pr.title}
                      </div>

                      <div className="meta">
                        PR #
                        {pr.number ||
                          "—"}
                      </div>
                    </div>

                    <Btn
                      onClick={() =>
                        void handleTrigger(
                          pr.id,
                        )
                      }
                      disabled={
                        triggering ===
                        pr.id
                      }
                    >
                      {triggering ===
                      pr.id ? (
                        <>
                          <I.Loader
                            size={12}
                            className="spin"
                          />
                          Triggering…
                        </>
                      ) : (
                        <>
                          <I.Play
                            size={12}
                          />
                          Run CI
                        </>
                      )}
                    </Btn>
                  </div>
                ))}
            </div>
          </Card>
        )}
      </div>

      <style>{`
        .ci-stats-grid {
          display: grid;
          grid-template-columns: repeat(4, minmax(0, 1fr));
          gap: 12px;
          margin-bottom: 24px;
        }

        @media (max-width: 768px) {
          .ci-stats-grid {
            grid-template-columns: repeat(2, minmax(0, 1fr));
            gap: 10px;
          }
        }

        @media (max-width: 480px) {
          .ci-stats-grid {
            grid-template-columns: repeat(2, minmax(0, 1fr));
            gap: 8px;
          }
        }

        .spin {
          animation: spin 1.2s linear infinite;
        }

        @keyframes spin {
          to {
            transform: rotate(360deg);
          }
        }
      `}</style>
    </AppShell>
  );
}

function MetricCard({
  label,
  value,
  icon,
  tone,
}: {
  label: string;
  value: string | number;
  icon: React.ReactNode;
  tone:
    | "green"
    | "red"
    | "aqua"
    | "violet";
}) {
  const color =
    tone === "green"
      ? "var(--green)"
      : tone === "red"
        ? "var(--red)"
        : tone === "aqua"
          ? "var(--cyan)"
          : "var(--violet)";

  return (
    <Card
      style={{
        padding:
          "12px 14px",
        display: "flex",
        alignItems:
          "center",
        gap: 10,
        minWidth: 0,
      }}
    >
      <div
        style={{
          width: 34,
          height: 34,
          borderRadius: 8,
          background:
            "var(--bg-subtle)",
          border:
            "1px solid var(--line)",
          display: "grid",
          placeItems: "center",
          color,
          flexShrink: 0,
        }}
      >
        {icon}
      </div>

      <div style={{ minWidth: 0, overflow: "hidden" }}>
        <div
          style={{
            fontSize: 20,
            fontWeight: 700,
            color: "var(--fg)",
            lineHeight: 1.2,
          }}
        >
          {value}
        </div>

        <div
          style={{
            fontSize: 12,
            color:
              "var(--muted)",
            whiteSpace: "nowrap",
            overflow: "hidden",
            textOverflow: "ellipsis",
          }}
        >
          {label}
        </div>
      </div>
    </Card>
  );
}