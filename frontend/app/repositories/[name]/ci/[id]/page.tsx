"use client";

import {
  use,
  useEffect,
  useState,
} from "react";

import {
  useRouter,
  useSearchParams,
} from "next/navigation";

import {
  AppShell,
  PageHead,
  Card,
  Btn,
  Badge,
} from "@/components/shell";

import {
  ciService,
  type CIJob,
  type CILog,
} from "@/lib/ci";

import {
  pullRequestService,
  type PullRequest,
} from "@/lib/pull-requests";

import * as I from "lucide-react";

function timeAgo(
  value: string | null | undefined,
) {
  if (!value) {
    return "—";
  }

  const time =
    new Date(value).getTime();

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

  return `${Math.floor(
    hours / 24,
  )}d ago`;
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
      (finished - started) /
        1000,
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
        <I.CheckCircle2
          size={18}
        />
      );

    case "failed":
      return (
        <I.XCircle
          size={18}
        />
      );

    case "running":
      return (
        <I.Loader
          size={18}
          className="spin"
        />
      );

    case "pending":
      return (
        <I.Circle size={18} />
      );

    case "cancelled":
      return (
        <I.MinusCircle
          size={18}
        />
      );

    default:
      return (
        <I.Circle size={18} />
      );
  }
}

function formatStatus(
  status: string,
) {
  return status
    .replaceAll("_", " ")
    .replace(/\b\w/g, (char) =>
      char.toUpperCase(),
    );
}

export default function CIDetailPage({
  params,
}: {
  params: Promise<{
    name: string;
    id: string;
  }>;
}) {
  const {
    name: repoName,
    id: jobId,
  } = use(params);

  const router = useRouter();

  const searchParams =
    useSearchParams();

  const prId =
    searchParams.get("pr");

  const [job, setJob] =
    useState<CIJob | null>(null);

  const [pr, setPr] =
    useState<PullRequest | null>(
      null,
    );

  const [logs, setLogs] =
    useState<CILog | null>(null);

  const [loading, setLoading] =
    useState(true);

  const [logLoading, setLogLoading] =
    useState(true);

  const [cancelling, setCancelling] =
    useState(false);

  const [refreshing, setRefreshing] =
    useState(false);

  const load = async (
    showPageLoader = true,
  ) => {
    if (!prId) {
      setLoading(false);
      setLogLoading(false);
      return;
    }

    try {
      if (showPageLoader) {
        setLoading(true);
      }

      setLogLoading(true);

      const jobData =
        await ciService.getJob(
          prId,
          jobId,
        );

      setJob(jobData);

      const logData =
        await ciService
          .getLogs(
            prId,
            jobId,
          )
          .catch(
            () => null,
          );

      setLogs(logData);

      try {
        const prData =
          await pullRequestService.getPR(
            prId,
          );

        setPr(prData);
      } catch {
        setPr(null);
      }
    } catch (err: any) {
      console.error(
        "Failed to load CI job",
        err,
      );
      setJob(null);
    } finally {
      setLoading(false);
      setLogLoading(false);
    }
  };

  useEffect(() => {
    void load();
  }, [jobId, prId]);

  const handleRefresh =
    async () => {
      try {
        setRefreshing(true);
        await load(false);
      } finally {
        setRefreshing(false);
      }
    };

  const handleCancel =
    async () => {
      if (
        !job ||
        !prId
      ) {
        return;
      }

      if (
        !window.confirm(
          "Cancel this CI run?",
        )
      ) {
        return;
      }

      try {
        setCancelling(true);

        const updated =
          await ciService.cancelJob(
            prId,
            jobId,
          );

        setJob(updated);

        const logData =
          await ciService
            .getLogs(
              prId,
              jobId,
            )
            .catch(
              () => null,
            );

        setLogs(logData);
      } catch (err: any) {
        alert(
          err?.message ||
            "Failed to cancel CI run.",
        );
      } finally {
        setCancelling(false);
      }
    };

  const handleDownload =
    () => {
      if (
        !logs?.output_log
      ) {
        return;
      }

      const blob =
        new Blob(
          [logs.output_log],
          {
            type: "text/plain",
          },
        );

      const url =
        URL.createObjectURL(
          blob,
        );

      const anchor =
        document.createElement(
          "a",
        );

      anchor.href = url;

      anchor.download =
        `ci-${jobId.slice(
          0,
          8,
        )}.log`;

      document.body.appendChild(
        anchor,
      );

      anchor.click();

      anchor.remove();

      URL.revokeObjectURL(
        url,
      );
    };

  if (!prId) {
    return (
      <AppShell>
        <div
          style={{
            padding: 48,
            textAlign: "center",
            color: "var(--muted)",
          }}
        >
          <Card>
            <div className="card-pad">
              <I.AlertCircle
                size={28}
                style={{
                  marginBottom: 12,
                  opacity: 0.4,
                }}
              />

              <div className="h2">
                Missing Pull Request
                context
              </div>

              <div
                className="sub"
                style={{
                  margin:
                    "8px auto 18px",
                }}
              >
                Open this CI run from
                the repository CI page.
              </div>

              <Btn
                onClick={() =>
                  router.back()
                }
              >
                Go Back
              </Btn>
            </div>
          </Card>
        </div>
      </AppShell>
    );
  }

  if (loading) {
    return (
      <AppShell>
        <div
          style={{
            padding: 48,
            textAlign: "center",
            color: "var(--muted)",
          }}
        >
          Loading CI run…
        </div>
      </AppShell>
    );
  }

  if (!job) {
    return (
      <AppShell>
        <div
          style={{
            padding: 48,
            maxWidth: 500,
            margin: "60px auto",
            textAlign: "center",
          }}
        >
          <Card>
            <div className="card-pad">
              <I.XCircle
                size={32}
                style={{
                  marginBottom: 12,
                  opacity: 0.35,
                }}
              />

              <div className="h2">
                CI run not found
              </div>

              <div
                className="sub"
                style={{
                  margin:
                    "8px auto 18px",
                }}
              >
                The requested CI job could not
                be loaded.
              </div>

              <Btn
                onClick={() =>
                  router.back()
                }
              >
                Go Back
              </Btn>
            </div>
          </Card>
        </div>
      </AppShell>
    );
  }

  const isActive =
    job.status ===
      "running" ||
    job.status ===
      "pending";

  const statusColor =
    job.status ===
    "passed"
      ? "var(--green)"
      : job.status ===
          "failed"
        ? "var(--red)"
        : job.status ===
            "running"
          ? "var(--cyan)"
          : job.status ===
              "pending"
            ? "var(--amber)"
            : "var(--muted)";

  return (
    <AppShell>
      <PageHead
        eyebrow={`CI / ${repoName}`}
        title={
          pr?.title ||
          `CI Run ${job.id.slice(
            0,
            8,
          )}`
        }
        sub={`${job.commit_sha.slice(
          0,
          8,
        )} → ${
          job.target_branch
        } · created ${timeAgo(
          job.created_at,
        )}`}
        action={
          <div
            style={{
              display: "flex",
              gap: 8,
              flexWrap: "wrap",
            }}
          >
            <Btn
              onClick={
                handleRefresh
              }
              disabled={
                refreshing
              }
            >
              <I.RefreshCw
                size={13}
                className={
                  refreshing
                    ? "spin"
                    : undefined
                }
              />
              Refresh
            </Btn>

            {isActive && (
              <Btn
                onClick={
                  handleCancel
                }
                disabled={
                  cancelling
                }
                style={{
                  color:
                    "var(--red)",
                  borderColor:
                    "rgba(239,68,68,.3)",
                }}
              >
                <I.Square
                  size={13}
                />

                {cancelling
                  ? "Cancelling…"
                  : "Cancel Run"}
              </Btn>
            )}

            {(() => {
              const extUrl = (logs?.output_log && logs.output_log.startsWith('http')) ? logs.output_log : (job?.output_log && job.output_log.startsWith('http') ? job.output_log : null);
              if (!extUrl) return null;
              return (
                <a
                  href={extUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                  style={{
                    display: "inline-flex",
                    alignItems: "center",
                    gap: 6,
                    textDecoration: "none",
                    padding: "6px 12px",
                    borderRadius: 6,
                    fontSize: 13,
                    fontWeight: 600,
                    background: "rgba(56, 189, 248, 0.12)",
                    border: "1px solid rgba(56, 189, 248, 0.3)",
                    color: "#38bdf8",
                  }}
                >
                  <I.ExternalLink size={13} />
                  Open on GitHub
                </a>
              );
            })()}

            {pr && (
              <Btn
                onClick={() =>
                  router.push(
                    `/repositories/${encodeURIComponent(
                      repoName,
                    )}/pull-requests/${encodeURIComponent(
                      prId,
                    )}`,
                  )
                }
              >
                <I.GitPullRequest
                  size={13}
                />
                View PR
              </Btn>
            )}
          </div>
        }
      />

      <div
        style={{
          maxWidth: 1100,
          margin: "0 auto",
          padding:
            "0 20px 40px",
        }}
      >
        {/* Status */}
        <Card
          style={{
            marginBottom: 16,
            borderColor:
              `${statusColor}40`,
          }}
        >
          <div
            className="card-pad"
            style={{
              display: "flex",
              alignItems: "center",
              gap: 14,
              flexWrap: "wrap",
            }}
          >
            <div
              style={{
                color:
                  statusColor,
                display:
                  "flex",
                alignItems:
                  "center",
              }}
            >
              {statusIcon(
                job.status,
              )}
            </div>

            <div>
              <div
                style={{
                  fontSize: 15,
                  fontWeight: 700,
                  color:
                    statusColor,
                }}
              >
                {formatStatus(
                  job.status,
                )}
              </div>

              <div
                className="meta"
                style={{
                  marginTop: 3,
                }}
              >
                Run {job.id}
              </div>
            </div>

            <div
              style={{
                marginLeft:
                  "auto",
                display:
                  "flex",
                gap: 18,
                flexWrap:
                  "wrap",
              }}
            >
              <MetaItem
                label="Duration"
                value={duration(
                  job.started_at,
                  job.completed_at,
                )}
              />

              <MetaItem
                label="Runner"
                value={
                  job.runner_type ||
                  "—"
                }
              />

              <MetaItem
                label="Trigger"
                value={
                  job.trigger ||
                  "—"
                }
              />

              {job.exit_code !==
                null &&
                job.exit_code !==
                  undefined && (
                  <MetaItem
                    label="Exit code"
                    value={String(
                      job.exit_code,
                    )}
                  />
                )}
            </div>
          </div>
        </Card>

        {/* Actual job information */}
        <div
          style={{
            display: "grid",
            gridTemplateColumns:
              "minmax(0,1fr) 280px",
            gap: 16,
          }}
        >
          <Card
            style={{
              padding: 0,
              overflow:
                "hidden",
            }}
          >
            <div
              className="card-head"
              style={{
                padding:
                  "13px 18px",
              }}
            >
              <div>
                <div className="h2">
                  CI output
                </div>

                <div className="sub">
                  Raw output reported by
                  the CI runner.
                </div>
              </div>

              <div
                className="actions"
              >
                {logs?.output_log && (
                  <Btn
                    style={{
                      fontSize: 11,
                    }}
                    onClick={
                      handleDownload
                    }
                  >
                    <I.Download
                      size={12}
                    />
                    Download
                  </Btn>
                )}
              </div>
            </div>

            {(() => {
              const extUrl = (logs?.output_log && logs.output_log.startsWith('http')) ? logs.output_log : (job?.output_log && job.output_log.startsWith('http') ? job.output_log : null);
              if (extUrl) {
                return (
                  <div
                    style={{
                      padding: "48px 24px",
                      textAlign: "center",
                      background: "rgba(56, 189, 248, 0.03)",
                      display: "flex",
                      flexDirection: "column",
                      alignItems: "center",
                      gap: 16,
                    }}
                  >
                    <div
                      style={{
                        width: 52,
                        height: 52,
                        borderRadius: 14,
                        background: "rgba(56, 189, 248, 0.12)",
                        border: "1px solid rgba(56, 189, 248, 0.3)",
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "center",
                        color: "#38bdf8",
                      }}
                    >
                      <I.Workflow size={26} />
                    </div>

                    <div>
                      <div
                        style={{
                          fontSize: 18,
                          fontWeight: 700,
                          color: "#f8fafc",
                          letterSpacing: "-0.01em",
                        }}
                      >
                        GitHub Actions Cloud Runner
                      </div>
                      <div
                        className="sub"
                        style={{
                          maxWidth: 520,
                          margin: "8px auto 0",
                          lineHeight: 1.6,
                        }}
                      >
                        This verification check executed natively in GitHub Actions. Complete step logs, annotations, and artifacts are streamed and hosted securely on GitHub.
                      </div>
                    </div>

                    <a
                      href={extUrl}
                      target="_blank"
                      rel="noopener noreferrer"
                      style={{
                        display: "inline-flex",
                        alignItems: "center",
                        gap: 8,
                        marginTop: 8,
                        padding: "10px 20px",
                        borderRadius: 8,
                        fontSize: 13,
                        fontWeight: 600,
                        background: "#38bdf8",
                        color: "#0f172a",
                        textDecoration: "none",
                        boxShadow: "0 2px 10px rgba(56, 189, 248, 0.3)",
                      }}
                    >
                      <I.ExternalLink size={15} />
                      View Execution on GitHub Actions
                    </a>
                  </div>
                );
              }

              return (
                <div
                  style={{
                    minHeight: 460,
                    maxHeight: 680,
                    overflowY: "auto",
                    padding: 18,
                    background: "#090d13",
                    color: "#d7dee8",
                    fontFamily: "monospace",
                    fontSize: 12,
                    lineHeight: 1.75,
                    whiteSpace: "pre-wrap",
                    wordBreak: "break-word",
                  }}
                >
                  {logLoading ? (
                    <span style={{ color: "#8893a3" }}>
                      Loading runner output…
                    </span>
                  ) : logs?.output_log ? (
                    logs.output_log
                  ) : (
                    <span style={{ color: "#8893a3" }}>
                      No log output has been recorded for this run yet.
                    </span>
                  )}
                </div>
              );
            })()}
          </Card>

          {/* Metadata */}
          <div
            style={{
              display:
                "flex",
              flexDirection:
                "column",
              gap: 16,
            }}
          >
            <Card>
              <div className="card-head">
                <div className="h2">
                  Run details
                </div>
              </div>

              <div
                className="card-pad"
              >
                <InfoRow
                  label="Commit"
                  value={
                    job.commit_sha
                  }
                  mono
                />

                <InfoRow
                  label="Target branch"
                  value={
                    job.target_branch
                  }
                  mono
                />

                <InfoRow
                  label="Trigger"
                  value={
                    job.trigger ||
                    "—"
                  }
                />

                <InfoRow
                  label="Runner"
                  value={
                    job.runner_type ||
                    "—"
                  }
                />

                <InfoRow
                  label="Worker"
                  value={
                    job.worker_id ||
                    "—"
                  }
                  mono
                />

                <InfoRow
                  label="Created"
                  value={
                    job.created_at
                      ? new Date(
                          job.created_at,
                        ).toLocaleString()
                      : "—"
                  }
                />

                <InfoRow
                  label="Started"
                  value={
                    job.started_at
                      ? new Date(
                          job.started_at,
                        ).toLocaleString()
                      : "—"
                  }
                />

                <InfoRow
                  label="Completed"
                  value={
                    job.completed_at
                      ? new Date(
                          job.completed_at,
                        ).toLocaleString()
                      : "—"
                  }
                />

                {job.cancelled_at && (
                  <InfoRow
                    label="Cancelled"
                    value={new Date(
                      job.cancelled_at,
                    ).toLocaleString()}
                  />
                )}

                {job.exit_code !==
                  null &&
                  job.exit_code !==
                    undefined && (
                    <InfoRow
                      label="Exit code"
                      value={
                        String(
                          job.exit_code,
                        )
                      }
                    />
                  )}
              </div>
            </Card>

            {job.failure_reason && (
              <Card
                style={{
                  borderColor:
                    "rgba(239,68,68,.3)",
                }}
              >
                <div
                  className="card-pad"
                >
                  <div
                    style={{
                      display:
                        "flex",
                      alignItems:
                        "flex-start",
                      gap: 10,
                    }}
                  >
                    <I.AlertTriangle
                      size={16}
                      style={{
                        color:
                          "var(--red)",
                        flexShrink: 0,
                      }}
                    />

                    <div>
                      <div
                        style={{
                          fontSize: 12,
                          fontWeight: 700,
                          color:
                            "var(--red)",
                          marginBottom:
                            5,
                        }}
                      >
                        Failure reason
                      </div>

                      <div
                        className="sub"
                        style={{
                          color:
                            "var(--fg)",
                        }}
                      >
                        {
                          job.failure_reason
                        }
                      </div>
                    </div>
                  </div>
                </div>
              </Card>
            )}
          </div>
        </div>
      </div>

      <style>{`
        .spin {
          animation:
            spin 1.2s linear infinite;
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

function MetaItem({
  label,
  value,
}: {
  label: string;
  value: string;
}) {
  return (
    <div>
      <div className="meta">
        {label}
      </div>

      <div
        style={{
          marginTop: 3,
          fontSize: 12,
          fontWeight: 600,
          color: "var(--fg)",
        }}
      >
        {value}
      </div>
    </div>
  );
}

function InfoRow({
  label,
  value,
  mono = false,
}: {
  label: string;
  value: React.ReactNode;
  mono?: boolean;
}) {
  return (
    <div
      style={{
        padding:
          "10px 0",
        borderBottom:
          "1px solid var(--line)",
      }}
    >
      <div className="meta">
        {label}
      </div>

      <div
        style={{
          marginTop: 4,
          fontSize: 12,
          color: "var(--fg)",
          fontFamily:
            mono
              ? "monospace"
              : "inherit",
          wordBreak:
            "break-word",
        }}
      >
        {value}
      </div>
    </div>
  );
}