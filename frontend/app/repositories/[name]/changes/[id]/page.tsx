"use client";

import { use, useEffect, useMemo, useState } from "react";
import { AppShell, PageHead, Card, Btn, Badge } from "@/components/shell";
import {
  changeService,
  Change,
  ChangeFile,
  AuthoritativeReview,
} from "@/lib/changes";
import { ciService, CIJob } from "@/lib/ci";
import { authService } from "@/lib/auth";
import * as I from "lucide-react";

type Tab =
  | "Overview"
  | "Commits"
  | "Changes"
  | "Checks"
  | "Review"
  | "Activity";

export default function ChangeDetailPage({
  params,
}: {
  params: Promise<{
    name: string;
    id: string;
  }>;
}) {
  const { name: repoId, id: changeId } = use(params);

  const [change, setChange] = useState<Change | null>(null);
  const [files, setFiles] = useState<ChangeFile[]>([]);
  const [reviews, setReviews] = useState<AuthoritativeReview[]>([]);
  const [ciJobs, setCiJobs] = useState<CIJob[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<Tab>("Overview");

  const loadChange = async () => {
    try {
      setLoading(true);
      setError(null);

      const user = await authService.getCurrentUser();

      const [changeData, fileData, reviewData] = await Promise.all([
        changeService.getChange(user.username, repoId, changeId),
        changeService.getChangeFiles(user.username, repoId, changeId),
        changeService.getChangeReviews(changeId).catch(() => []),
      ]);

      setChange(changeData);
      setFiles(fileData || []);
      setReviews(reviewData || []);

      if (changeData?.pull_request_id) {
        try {
          const jobs = await ciService.listJobsForPR(changeData.pull_request_id);
          setCiJobs(jobs || []);
        } catch {
          setCiJobs([]);
        }
      } else {
        setCiJobs([]);
      }
    } catch (err: any) {
      console.error("Failed to load change", err);
      setChange(null);
      setFiles([]);
      setReviews([]);
      setCiJobs([]);
      setError(err?.detail || err?.message || "Failed to load change.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void loadChange();
  }, [repoId, changeId]);

  const totals = useMemo(() => {
    const additions =
      change?.additions ??
      files.reduce((sum, file) => sum + (file.additions || 0), 0);

    const deletions =
      change?.deletions ??
      files.reduce((sum, file) => sum + (file.deletions || 0), 0);

    return { additions, deletions };
  }, [change, files]);

  const statusTone = (status: string): string => {
    switch (status) {
      case "proposed":
      case "generating":
        return "aqua";
      case "testing":
      case "needs_review":
      case "pending":
        return "amber";
      case "approved":
      case "ready_to_ship":
        return "green";
      case "merged":
      case "recorded":
        return "violet";
      case "failed":
      case "blocked":
      case "rejected":
        return "red";
      default:
        return "amber";
    }
  };

  const statusLabel = (status: string) =>
    status
      .replaceAll("_", " ")
      .replace(/\b\w/g, (char) => char.toUpperCase());

  if (loading) {
    return (
      <AppShell>
        <div style={{ padding: 50, textAlign: "center" }}>
          <div className="sub">Loading change…</div>
        </div>
      </AppShell>
    );
  }

  if (!change) {
    return (
      <AppShell>
        <div
          style={{
            padding: 40,
            maxWidth: 600,
            margin: "40px auto",
            textAlign: "center",
          }}
        >
          <Card>
            <div className="card-pad">
              <I.AlertCircle
                size={32}
                style={{ color: "var(--red)", marginBottom: 16 }}
              />
              <div className="h2" style={{ marginBottom: 8 }}>
                Change Not Found
              </div>
              <div className="sub">
                {error ||
                  "The change does not exist or you do not have permission to view it."}
              </div>
              <div
                className="actions"
                style={{ justifyContent: "center", marginTop: 20 }}
              >
                <Btn onClick={() => window.history.back()}>Go Back</Btn>
              </div>
            </div>
          </Card>
        </div>
      </AppShell>
    );
  }

  const approvedReviews = reviews.filter(
    (review) => review.status === "approved",
  ).length;
  const pendingReviews = reviews.filter(
    (review) => review.status === "pending",
  ).length;
  const rejectedReviews = reviews.filter(
    (review) => review.status === "rejected" || review.status === "changes_requested",
  ).length;

  const passedCIJobs = ciJobs.filter((job) => job.status === "passed").length;
  const runningCIJobs = ciJobs.filter(
    (job) => job.status === "running" || job.status === "queued",
  ).length;
  const failedCIJobs = ciJobs.filter(
    (job) => job.status === "failed" || job.status === "timed_out",
  ).length;

  const allChecksPassed =
    ciJobs.length > 0 && ciJobs.every((job) => job.status === "passed");

  const changeStatus = statusLabel(change.status);

  return (
    <AppShell>
      <PageHead
        eyebrow={`Changes / ${repoId}`}
        title={change.title || change.intent || "Untitled Change"}
        sub={`${change.actor_name || "Unknown"} · created ${new Date(
          change.created_at,
        ).toLocaleDateString()}`}
      />

      <div
        style={{
          width: "100%",
        }}
      >
        {/* Pipeline */}
        <Card style={{ marginBottom: 20 }}>
          <div className="card-pad" style={{ overflowX: "auto" }}>
            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: 14,
                minWidth: 620,
              }}
            >
              <PipelineStep
                label="Task"
                active={Boolean(change.task_id)}
                done={Boolean(change.task_id)}
              />
              <I.ChevronRight size={14} className="muted" />

              <PipelineStep
                label={change.actor_type === "agent" ? "Agent" : "Human"}
                active
                done
              />
              <I.ChevronRight size={14} className="muted" />

              <PipelineStep
                label="Change"
                active
                done={Boolean(change.resulting_commit)}
              />
              <I.ChevronRight size={14} className="muted" />

              <PipelineStep
                label="Checks"
                active={ciJobs.length > 0}
                done={allChecksPassed}
              />
              <I.ChevronRight size={14} className="muted" />

              <PipelineStep
                label="Review"
                active={reviews.length > 0}
                done={approvedReviews > 0}
              />
              <I.ChevronRight size={14} className="muted" />

              <PipelineStep
                label="Ship"
                active={[
                  "ready_to_ship",
                  "merged",
                  "recorded",
                ].includes(change.status)}
                done={["merged", "recorded"].includes(change.status)}
              />
            </div>
          </div>
        </Card>

        <div
          style={{
            display: "grid",
            gridTemplateColumns: "minmax(0,1fr) 320px",
            gap: 24,
          }}
        >
          {/* Main */}
          <div style={{ minWidth: 0 }}>
            <Card>
              <div
                style={{
                  display: "flex",
                  borderBottom: "1px solid var(--line)",
                  overflowX: "auto",
                }}
              >
                {(
                  [
                    "Overview",
                    "Commits",
                    "Changes",
                    "Checks",
                    "Review",
                    "Activity",
                  ] as Tab[]
                ).map((tab) => (
                  <button
                    key={tab}
                    type="button"
                    onClick={() => setActiveTab(tab)}
                    style={{
                      padding: "12px 18px",
                      background: "transparent",
                      border: "none",
                      borderBottom:
                        activeTab === tab
                          ? "2px solid var(--cyan)"
                          : "2px solid transparent",
                      color:
                        activeTab === tab ? "var(--fg)" : "var(--muted)",
                      fontWeight: activeTab === tab ? 600 : 400,
                      cursor: "pointer",
                      whiteSpace: "nowrap",
                    }}
                  >
                    {tab}
                    {tab === "Commits" && (change.commits?.length ?? 0) > 0 && (
                      <span
                        style={{
                          marginLeft: 6,
                          fontSize: 11,
                          padding: "2px 6px",
                          borderRadius: 10,
                          background: "rgba(6,182,212,0.15)",
                          color: "var(--cyan)",
                        }}
                      >
                        {change.commits?.length}
                      </span>
                    )}
                    {tab === "Checks" && ciJobs.length > 0 && (
                      <span
                        style={{
                          marginLeft: 6,
                          fontSize: 11,
                          padding: "2px 6px",
                          borderRadius: 10,
                          background: allChecksPassed
                            ? "rgba(34,197,94,0.15)"
                            : failedCIJobs > 0
                              ? "rgba(239,68,68,0.15)"
                              : "rgba(6,182,212,0.15)",
                          color: allChecksPassed
                            ? "var(--green)"
                            : failedCIJobs > 0
                              ? "var(--red)"
                              : "var(--cyan)",
                        }}
                      >
                        {ciJobs.length}
                      </span>
                    )}
                    {tab === "Review" && reviews.length > 0 && (
                      <span
                        style={{
                          marginLeft: 6,
                          fontSize: 11,
                          padding: "2px 6px",
                          borderRadius: 10,
                          background:
                            approvedReviews > 0
                              ? "rgba(34,197,94,0.15)"
                              : "rgba(245,158,11,0.15)",
                          color:
                            approvedReviews > 0
                              ? "var(--green)"
                              : "var(--amber)",
                        }}
                      >
                        {reviews.length}
                      </span>
                    )}
                  </button>
                ))}
              </div>

              <div className="card-pad">
                {/* Overview */}
                {activeTab === "Overview" && (
                  <div>
                    <div className="eyebrow">Intent</div>
                    <div
                      className="sub"
                      style={{
                        whiteSpace: "pre-wrap",
                        lineHeight: 1.7,
                        color: "var(--fg)",
                      }}
                    >
                      {change.intent ||
                        change.description ||
                        "No description provided."}
                    </div>

                    <div
                      className="grid g2"
                      style={{
                        marginTop: 24,
                      }}
                    >
                      <InfoBlock
                        label="Status"
                        value={
                          <Badge tone={statusTone(change.status) as any}>
                            {changeStatus}
                          </Badge>
                        }
                      />

                      <InfoBlock
                        label="Actor"
                        value={change.actor_name || "Unknown"}
                      />

                      <InfoBlock
                        label="Files changed"
                        value={String(change.files_changed ?? files.length)}
                      />

                      <InfoBlock
                        label="Risk"
                        value={change.risk_level || "Not specified"}
                      />

                      {change.resulting_commit && (
                        <InfoBlock
                          label="Resulting Commit"
                          value={
                            <code
                              style={{
                                fontFamily: "monospace",
                                fontSize: 12,
                                background: "var(--bg)",
                                padding: "2px 6px",
                                borderRadius: 4,
                              }}
                            >
                              {change.resulting_commit.slice(0, 10)}
                            </code>
                          }
                        />
                      )}

                      {change.base_commit && (
                        <InfoBlock
                          label="Base Commit"
                          value={
                            <code
                              style={{
                                fontFamily: "monospace",
                                fontSize: 12,
                                background: "var(--bg)",
                                padding: "2px 6px",
                                borderRadius: 4,
                              }}
                            >
                              {change.base_commit.slice(0, 10)}
                            </code>
                          }
                        />
                      )}
                    </div>
                  </div>
                )}

                {/* Commits */}
                {activeTab === "Commits" && (
                  <div>
                    <div
                      style={{
                        display: "flex",
                        justifyContent: "space-between",
                        alignItems: "center",
                        marginBottom: 16,
                      }}
                    >
                      <div className="h2">Commits with Provenance</div>
                      <div className="meta">
                        {change.commits?.length || 0} commit{change.commits?.length === 1 ? "" : "s"}
                      </div>
                    </div>

                    {(!change.commits || change.commits.length === 0) ? (
                      <div className="card-pad" style={{ textAlign: "center", padding: "36px 16px" }}>
                        <I.GitCommit size={28} className="muted" style={{ marginBottom: 10 }} />
                        <div className="title-sm">No Commits Recorded Yet</div>
                        <div className="sub" style={{ maxWidth: 460, margin: "6px auto 0", lineHeight: 1.6 }}>
                          {change.status === "proposed"
                            ? "This change is currently proposed. When commits are pushed under a governed lease session, they will appear here with cryptographic provenance."
                            : "No substrate commits are linked to this change."}
                        </div>
                      </div>
                    ) : (
                      <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
                        {change.commits.map((commit, idx) => {
                          const prov = commit.provenance;
                          const isAgent = prov?.identity_type === "agent";
                          const isHuman = prov?.identity_type === "human";
                          const isExternal = prov?.identity_type === "external";

                          return (
                            <Card
                              key={commit.sha || idx}
                              style={{
                                border: isAgent ? "1px solid rgba(16, 185, 129, 0.3)" : "1px solid var(--line)",
                                background: isAgent ? "rgba(16, 185, 129, 0.03)" : "rgba(255, 255, 255, 0.01)",
                                borderRadius: 10,
                                padding: "16px 18px",
                              }}
                            >
                              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 12, flexWrap: "wrap" }}>
                                <div>
                                  <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                                    <I.GitCommit size={15} color={isAgent ? "var(--green)" : "var(--cyan)"} />
                                    <code style={{ fontSize: 13, fontWeight: 600 }}>{commit.sha.slice(0, 10)}</code>
                                    {commit.sha === change.resulting_commit && (
                                      <Badge tone="green">Head</Badge>
                                    )}
                                  </div>
                                  <div className="title-sm" style={{ marginTop: 6, fontWeight: 600, fontSize: 14 }}>
                                    {commit.message || "No commit message recorded."}
                                  </div>
                                  <div className="meta" style={{ marginTop: 4 }}>
                                    Committed by {commit.author_name || commit.author_email || "Unknown"} · {commit.committed_at ? new Date(commit.committed_at).toLocaleString() : "—"}
                                  </div>
                                </div>

                                <div>
                                  {isAgent ? (
                                    <Badge tone="green" style={{ display: "flex", alignItems: "center", gap: 5 }}>
                                      <I.Bot size={13} /> SUTRA Agent Provenance
                                    </Badge>
                                  ) : isHuman ? (
                                    <Badge tone="violet" style={{ display: "flex", alignItems: "center", gap: 5 }}>
                                      <I.User size={13} /> Verified Human Commit
                                    </Badge>
                                  ) : isExternal ? (
                                    <Badge tone="amber" style={{ display: "flex", alignItems: "center", gap: 5 }}>
                                      <I.GitCommit size={13} /> External Substrate Commit
                                    </Badge>
                                  ) : (
                                    <Badge tone="aqua">Substrate Commit</Badge>
                                  )}
                                </div>
                              </div>

                              {prov && (
                                <div
                                  style={{
                                    marginTop: 14,
                                    padding: "10px 14px",
                                    borderRadius: 8,
                                    background: isAgent ? "rgba(16, 185, 129, 0.08)" : "rgba(255, 255, 255, 0.03)",
                                    fontSize: 12,
                                    display: "flex",
                                    flexDirection: "column",
                                    gap: 6,
                                  }}
                                >
                                  {isAgent && (
                                    <div style={{ display: "flex", gap: 16, flexWrap: "wrap", alignItems: "center" }}>
                                      <span>
                                        <strong>Agent:</strong> {prov.agent?.name || change.agent_name || "Autonomous Agent"}
                                      </span>
                                      {prov.session?.id && (
                                        <span>
                                          <strong>Session:</strong> #{prov.session.id.slice(0, 8)}
                                        </span>
                                      )}
                                      {prov.task?.id && (
                                        <span>
                                          <strong>Task:</strong>{" "}
                                          <a href={`/tasks/${prov.task.id}`} style={{ color: "var(--cyan)", textDecoration: "underline" }}>
                                            #{prov.task.id.slice(0, 8)} {prov.task.title ? `(${prov.task.title})` : ""}
                                          </a>
                                        </span>
                                      )}
                                    </div>
                                  )}
                                  {isHuman && (
                                    <div>
                                      <strong>Actor:</strong> {prov.actor_name || commit.author_name || "SUTRA Operator"}
                                    </div>
                                  )}
                                  {isExternal && (
                                    <div style={{ color: "var(--amber)" }}>
                                      Commit was pushed directly to the substrate branch outside SUTRA session governance.
                                    </div>
                                  )}
                                </div>
                              )}
                            </Card>
                          );
                        })}
                      </div>
                    )}
                  </div>
                )}

                {/* Changes */}
                {activeTab === "Changes" && (
                  <div>
                    <div
                      style={{
                        display: "flex",
                        justifyContent: "space-between",
                        gap: 16,
                        marginBottom: 18,
                      }}
                    >
                      <div className="h2">Diff</div>
                      <div className="actions">
                        <span style={{ color: "var(--green)" }}>
                          +{totals.additions}
                        </span>
                        <span style={{ color: "var(--red)" }}>
                          −{totals.deletions}
                        </span>
                        <span className="meta">{files.length} files</span>
                      </div>
                    </div>

                    {files.length === 0 ? (
                      <div className="card-pad" style={{ textAlign: "center" }}>
                        <div className="sub">
                          No file modifications recorded for this change.
                        </div>
                      </div>
                    ) : (
                      <div
                        style={{
                          display: "flex",
                          flexDirection: "column",
                          gap: 16,
                        }}
                      >
                        {files.map((file, idx) => {
                          const filePath =
                            file.path || file.filename || `file-${idx}`;
                          const rawPatch = file.patch || "";
                          const patchLines = rawPatch
                            ? rawPatch.split("\n")
                            : [];

                          return (
                            <Card
                              key={filePath}
                              style={{
                                overflow: "hidden",
                                border: "1px solid var(--line)",
                              }}
                            >
                              <div
                                style={{
                                  padding: "10px 16px",
                                  background: "rgba(255, 255, 255, 0.03)",
                                  borderBottom: "1px solid var(--line)",
                                  display: "flex",
                                  alignItems: "center",
                                  justifyContent: "space-between",
                                }}
                              >
                                <div
                                  style={{
                                    display: "flex",
                                    alignItems: "center",
                                    gap: 8,
                                  }}
                                >
                                  <I.FileText size={15} className="muted" />
                                  <span
                                    style={{
                                      fontFamily: "monospace",
                                      fontSize: 13,
                                      fontWeight: 600,
                                    }}
                                  >
                                    {filePath}
                                  </span>
                                  {file.operation && (
                                    <Badge
                                      tone={
                                        file.operation === "add" ||
                                        file.status === "added"
                                          ? "green"
                                          : file.operation === "delete" ||
                                              file.status === "deleted"
                                            ? "red"
                                            : "aqua"
                                      }
                                    >
                                      {file.operation || file.status}
                                    </Badge>
                                  )}
                                </div>
                                <div
                                  style={{
                                    display: "flex",
                                    gap: 8,
                                    fontSize: 12,
                                    fontFamily: "monospace",
                                  }}
                                >
                                  <span style={{ color: "var(--green)" }}>
                                    +{file.additions}
                                  </span>
                                  <span style={{ color: "var(--red)" }}>
                                    −{file.deletions}
                                  </span>
                                </div>
                              </div>

                              {patchLines.length > 0 ? (
                                <div
                                  style={{
                                    fontFamily:
                                      "ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace",
                                    fontSize: 12,
                                    lineHeight: 1.5,
                                    overflowX: "auto",
                                    padding: "8px 0",
                                    background: "#0d1117",
                                  }}
                                >
                                  {patchLines.map((line, lIdx) => {
                                    let bg = "transparent";
                                    let color = "var(--fg)";
                                    if (line.startsWith("+") && !line.startsWith("+++")) {
                                      bg = "rgba(46, 160, 67, 0.18)";
                                      color = "#7ee787";
                                    } else if (
                                      line.startsWith("-") &&
                                      !line.startsWith("---")
                                    ) {
                                      bg = "rgba(248, 81, 73, 0.18)";
                                      color = "#ff7b72";
                                    } else if (line.startsWith("@@")) {
                                      bg = "rgba(56, 139, 253, 0.15)";
                                      color = "#79c0ff";
                                    }

                                    return (
                                      <div
                                        key={lIdx}
                                        style={{
                                          background: bg,
                                          color,
                                          padding: "1px 16px",
                                          whiteSpace: "pre-wrap",
                                          wordBreak: "break-all",
                                        }}
                                      >
                                        {line || " "}
                                      </div>
                                    );
                                  })}
                                </div>
                              ) : (
                                <div
                                  style={{
                                    padding: 16,
                                    background: "var(--bg)",
                                    color: "var(--muted)",
                                    fontSize: 12,
                                    fontFamily: "monospace",
                                  }}
                                >
                                  Diff stats: +{file.additions || 0} / −
                                  {file.deletions || 0} (unified diff generated on commit).
                                </div>
                              )}
                            </Card>
                          );
                        })}
                      </div>
                    )}
                  </div>
                )}

                {/* Checks */}
                {activeTab === "Checks" && (
                  <div>
                    <div
                      style={{
                        display: "flex",
                        justifyContent: "space-between",
                        alignItems: "center",
                        marginBottom: 16,
                      }}
                    >
                      <div className="h2">Pipeline checks</div>
                      {change.pull_request_id && (
                        <Btn
                          onClick={() =>
                            (window.location.href = `/repositories/${repoId}/ci?pr=${change.pull_request_id}`)
                          }
                        >
                          View CI Runs
                        </Btn>
                      )}
                    </div>

                    {ciJobs.length === 0 ? (
                      <div className="sub">
                        {change.pull_request_id
                          ? "No pipeline checks are recorded for this change."
                          : "No pipeline checks recorded (Pull Request not yet opened)."}
                      </div>
                    ) : (
                      <div className="list">
                        {ciJobs.map((job) => (
                          <div
                            key={job.id}
                            className="list-row"
                            style={{ alignItems: "flex-start", gap: 14 }}
                          >
                            <div style={{ marginTop: 2 }}>
                              {job.status === "passed" ? (
                                <I.CheckCircle2
                                  size={18}
                                  style={{ color: "var(--green)" }}
                                />
                              ) : job.status === "running" ||
                                job.status === "queued" ? (
                                <I.Loader
                                  size={18}
                                  style={{ color: "var(--cyan)" }}
                                />
                              ) : (
                                <I.XCircle
                                  size={18}
                                  style={{ color: "var(--red)" }}
                                />
                              )}
                            </div>

                            <div style={{ flex: 1, minWidth: 0 }}>
                              <div
                                style={{
                                  display: "flex",
                                  alignItems: "center",
                                  gap: 8,
                                  flexWrap: "wrap",
                                }}
                              >
                                <div className="title-sm">
                                  CI Automated Sandbox Run
                                </div>
                                <span
                                  className="meta"
                                  style={{ fontFamily: "monospace" }}
                                >
                                  #{job.id.slice(0, 8)}
                                </span>
                              </div>

                              <div
                                className="meta"
                                style={{ marginTop: 4, lineHeight: 1.6 }}
                              >
                                Target Commit:{" "}
                                <code
                                  style={{
                                    fontFamily: "monospace",
                                    fontSize: 12,
                                  }}
                                >
                                  {job.commit_sha
                                    ? job.commit_sha.slice(0, 8)
                                    : "head"}
                                </code>{" "}
                                · Runner: {job.runner_type || "isolated_process"} ·
                                Trigger: {job.trigger}
                              </div>

                              {job.failure_reason && (
                                <div
                                  style={{
                                    marginTop: 4,
                                    fontSize: 12,
                                    color: "var(--red)",
                                    fontWeight: 500,
                                  }}
                                >
                                  Failure: {job.failure_reason}
                                </div>
                              )}

                              <div
                                className="meta"
                                style={{ marginTop: 4, fontSize: 11 }}
                              >
                                Created:{" "}
                                {new Date(job.created_at).toLocaleString()}
                                {job.completed_at &&
                                  ` · Completed: ${new Date(
                                    job.completed_at,
                                  ).toLocaleString()}`}
                              </div>
                            </div>

                            <div
                              style={{
                                display: "flex",
                                alignItems: "center",
                                gap: 10,
                              }}
                            >
                              <Badge
                                tone={
                                  job.status === "passed"
                                    ? "green"
                                    : job.status === "running"
                                      ? "aqua"
                                      : job.status === "queued"
                                        ? "amber"
                                        : "red"
                                }
                              >
                                {statusLabel(job.status)}
                              </Badge>

                              {change.pull_request_id && (
                                <Btn
                                  style={{ padding: "4px 10px", fontSize: 12 }}
                                  onClick={() =>
                                    (window.location.href = `/repositories/${repoId}/ci/${job.id}?pr=${change.pull_request_id}`)
                                  }
                                >
                                  Logs
                                </Btn>
                              )}
                            </div>
                          </div>
                        ))}
                      </div>
                    )}

                    {ciJobs.length > 0 && (
                      <div style={{ marginTop: 18 }}>
                        {allChecksPassed ? (
                          <div
                            className="sub"
                            style={{
                              color: "var(--green)",
                              fontWeight: 500,
                            }}
                          >
                            ✓ All {ciJobs.length} recorded checks have passed.
                          </div>
                        ) : (
                          <div className="sub">
                            Some checks are still pending, running, or have
                            failed.
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                )}

                {/* Review */}
                {activeTab === "Review" && (
                  <div>
                    <div className="h2" style={{ marginBottom: 16 }}>
                      Review status
                    </div>

                    {reviews.length === 0 ? (
                      <div className="sub">
                        No reviews are recorded for this change.
                      </div>
                    ) : (
                      <>
                        <div
                          className="grid g3"
                          style={{
                            marginBottom: 18,
                          }}
                        >
                          <InfoBlock
                            label="Approved"
                            value={`${approvedReviews}/${reviews.length}`}
                          />
                          <InfoBlock
                            label="Pending"
                            value={String(pendingReviews)}
                          />
                          <InfoBlock
                            label="Changes Requested"
                            value={String(rejectedReviews)}
                          />
                        </div>

                        <div className="list">
                          {reviews.map((review) => {
                            const isApproved = review.status === "approved";
                            const isPending = review.status === "pending";
                            const isRejected =
                              review.status === "rejected" ||
                              review.status === "changes_requested";

                            return (
                              <div
                                key={review.id}
                                className="list-row"
                                style={{ alignItems: "flex-start", gap: 14 }}
                              >
                                <div style={{ marginTop: 2 }}>
                                  {isApproved ? (
                                    <I.CheckCircle2
                                      size={18}
                                      style={{ color: "var(--green)" }}
                                    />
                                  ) : isPending ? (
                                    <I.Clock
                                      size={18}
                                      style={{ color: "var(--amber)" }}
                                    />
                                  ) : (
                                    <I.AlertCircle
                                      size={18}
                                      style={{ color: "var(--red)" }}
                                    />
                                  )}
                                </div>

                                <div style={{ flex: 1, minWidth: 0 }}>
                                  <div
                                    style={{
                                      display: "flex",
                                      alignItems: "center",
                                      gap: 8,
                                      flexWrap: "wrap",
                                    }}
                                  >
                                    <div className="title-sm">
                                      {isApproved
                                        ? "Approved"
                                        : isPending
                                          ? "Pending Review"
                                          : "Changes Requested"}
                                    </div>
                                    <span
                                      className="meta"
                                      style={{ fontFamily: "monospace" }}
                                    >
                                      #{review.id.slice(0, 8)}
                                    </span>
                                  </div>

                                  {review.reason && (
                                    <div
                                      className="sub"
                                      style={{
                                        marginTop: 4,
                                        color: "var(--fg)",
                                      }}
                                    >
                                      {review.reason}
                                    </div>
                                  )}

                                  <div
                                    className="meta"
                                    style={{ marginTop: 6, lineHeight: 1.6 }}
                                  >
                                    {review.reviewer_id && (
                                      <span>
                                        Reviewer:{" "}
                                        <code
                                          style={{
                                            fontFamily: "monospace",
                                            fontSize: 12,
                                          }}
                                        >
                                          {review.reviewer_id.slice(0, 8)}...
                                        </code>{" "}
                                        ·{" "}
                                      </span>
                                    )}
                                    Requested by:{" "}
                                    <code
                                      style={{
                                        fontFamily: "monospace",
                                        fontSize: 12,
                                      }}
                                    >
                                      {review.requested_by.slice(0, 8)}...
                                    </code>
                                  </div>

                                  <div
                                    className="meta"
                                    style={{ marginTop: 4, fontSize: 11 }}
                                  >
                                    Requested:{" "}
                                    {new Date(
                                      review.created_at,
                                    ).toLocaleString()}
                                    {review.reviewed_at &&
                                      ` · Reviewed: ${new Date(
                                        review.reviewed_at,
                                      ).toLocaleString()}`}
                                  </div>
                                </div>

                                <Badge
                                  tone={
                                    isApproved
                                      ? "green"
                                      : isPending
                                        ? "amber"
                                        : "red"
                                  }
                                >
                                  {isApproved
                                    ? "Approved"
                                    : isPending
                                      ? "Pending"
                                      : "Changes Requested"}
                                </Badge>
                              </div>
                            );
                          })}
                        </div>
                      </>
                    )}
                  </div>
                )}

                {/* Activity */}
                {activeTab === "Activity" && (
                  <div>
                    <div className="h2" style={{ marginBottom: 16 }}>
                      Change activity
                    </div>

                    <div className="list">
                      <div className="list-row">
                        <I.PlusCircle size={15} className="muted" />
                        <div style={{ flex: 1 }}>
                          <div className="title-sm">Change created</div>
                          <div className="meta">
                            {new Date(change.created_at).toLocaleString()}
                          </div>
                        </div>
                      </div>

                      {change.updated_at !== change.created_at && (
                        <div className="list-row">
                          <I.RefreshCw size={15} className="muted" />
                          <div style={{ flex: 1 }}>
                            <div className="title-sm">Change updated</div>
                            <div className="meta">
                              {new Date(change.updated_at).toLocaleString()}
                            </div>
                          </div>
                        </div>
                      )}

                      <div className="list-row">
                        <I.GitCommit size={15} className="muted" />
                        <div style={{ flex: 1 }}>
                          <div className="title-sm">Current status</div>
                          <div className="meta">{changeStatus}</div>
                        </div>
                      </div>
                    </div>
                  </div>
                )}
              </div>
            </Card>
          </div>

          {/* Sidebar */}
          <div
            style={{
              display: "flex",
              flexDirection: "column",
              gap: 16,
            }}
          >
            <Card>
              <div className="card-pad">
                <div className="eyebrow">Change</div>
                <div style={{ marginTop: 8 }}>
                  <Badge tone={statusTone(change.status) as any}>
                    {changeStatus}
                  </Badge>
                </div>

                <div style={{ marginTop: 16 }}>
                  <InfoBlock label="Repository" value={repoId} />
                  <InfoBlock
                    label="Author"
                    value={change.actor_name || "Unknown"}
                  />
                  <InfoBlock
                    label="Actor type"
                    value={
                      change.actor_type === "agent" ? "Agent" : "Human"
                    }
                  />
                  <InfoBlock
                    label="Risk"
                    value={change.risk_level || "Not specified"}
                  />
                </div>
              </div>
            </Card>

            {/* Related Pull Request */}
            {change.pull_request_id && (
              <Card>
                <div className="card-pad">
                  <div className="eyebrow">Related Pull Request</div>
                  <div style={{ marginTop: 10 }}>
                    <div className="title-sm">
                      {change.pull_request_title ||
                        `PR #${change.pull_request_id.slice(0, 8)}`}
                    </div>
                    <div
                      style={{
                        marginTop: 6,
                        display: "flex",
                        alignItems: "center",
                        gap: 8,
                      }}
                    >
                      <Badge
                        tone={
                          change.pull_request_status === "merged"
                            ? "violet"
                            : change.pull_request_status === "open"
                              ? "green"
                              : "muted"
                        }
                      >
                        {change.pull_request_status || "open"}
                      </Badge>
                      <span
                        className="meta"
                        style={{ fontFamily: "monospace", fontSize: 11 }}
                      >
                        #{change.pull_request_id.slice(0, 8)}
                      </span>
                    </div>

                    <Btn
                      style={{
                        marginTop: 12,
                        width: "100%",
                        justifyContent: "center",
                      }}
                      onClick={() =>
                        (window.location.href = `/repositories/${repoId}/pull-requests/${change.pull_request_id}`)
                      }
                    >
                      View Pull Request
                    </Btn>
                  </div>
                </div>
              </Card>
            )}

            <Card>
              <div className="card-pad">
                <div className="eyebrow">Originating task</div>
                {change.task_id ? (
                  <div style={{ marginTop: 10 }}>
                    <div className="title-sm">
                      #{change.task_id.split("-").pop()?.slice(0, 8) ||
                        change.task_id.slice(0, 8)}
                    </div>
                    <div className="sub">
                      {change.task_title ||
                        "Task details are not available on this change."}
                    </div>
                    <Btn
                      style={{
                        marginTop: 12,
                        width: "100%",
                        justifyContent: "center",
                      }}
                      onClick={() =>
                        (window.location.href = `/tasks/${change.task_id}`)
                      }
                    >
                      View Task
                    </Btn>
                  </div>
                ) : (
                  <div className="sub" style={{ marginTop: 8 }}>
                    No originating task is associated with this change.
                  </div>
                )}
              </div>
            </Card>

            <Card>
              <div className="card-pad">
                <div className="eyebrow">Pipeline Checks</div>
                <div style={{ marginTop: 12 }}>
                  {ciJobs.length === 0 ? (
                    <div className="sub">No checks recorded.</div>
                  ) : (
                    <div
                      style={{
                        display: "flex",
                        flexDirection: "column",
                        gap: 10,
                      }}
                    >
                      {ciJobs.map((job) => (
                        <div
                          key={job.id}
                          style={{
                            display: "flex",
                            alignItems: "center",
                            justifyContent: "space-between",
                            gap: 8,
                          }}
                        >
                          <div
                            style={{
                              display: "flex",
                              alignItems: "center",
                              gap: 6,
                              minWidth: 0,
                            }}
                          >
                            {job.status === "passed" ? (
                              <I.Check
                                size={14}
                                style={{ color: "var(--green)" }}
                              />
                            ) : job.status === "running" ||
                              job.status === "queued" ? (
                              <I.Loader
                                size={14}
                                style={{ color: "var(--cyan)" }}
                              />
                            ) : (
                              <I.X size={14} style={{ color: "var(--red)" }} />
                            )}
                            <span
                              className="meta"
                              style={{
                                fontFamily: "monospace",
                                fontSize: 12,
                                whiteSpace: "nowrap",
                                overflow: "hidden",
                                textOverflow: "ellipsis",
                              }}
                            >
                              CI #{job.id.slice(0, 8)}
                            </span>
                          </div>

                          <Badge
                            tone={
                              job.status === "passed"
                                ? "green"
                                : job.status === "running"
                                  ? "aqua"
                                  : job.status === "queued"
                                    ? "amber"
                                    : "red"
                            }
                          >
                            {job.status}
                          </Badge>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            </Card>

            <Card>
              <div className="card-pad">
                <div className="eyebrow">Review</div>
                <div style={{ marginTop: 12 }}>
                  {reviews.length === 0 ? (
                    <div className="sub">No reviews recorded.</div>
                  ) : (
                    <div
                      style={{
                        display: "flex",
                        flexDirection: "column",
                        gap: 10,
                      }}
                    >
                      {reviews.map((review) => {
                        const isApproved = review.status === "approved";
                        const isPending = review.status === "pending";

                        return (
                          <div
                            key={review.id}
                            style={{
                              display: "flex",
                              alignItems: "center",
                              justifyContent: "space-between",
                              gap: 10,
                            }}
                          >
                            <span
                              className="meta"
                              style={{
                                fontFamily: "monospace",
                                fontSize: 12,
                              }}
                            >
                              {review.reviewer_id
                                ? `Reviewer: #${review.reviewer_id.slice(0, 8)}`
                                : `Requested: #${review.requested_by.slice(0, 8)}`}
                            </span>

                            <Badge
                              tone={
                                isApproved
                                  ? "green"
                                  : isPending
                                    ? "amber"
                                    : "red"
                              }
                            >
                              {isApproved
                                ? "Approved"
                                : isPending
                                  ? "Pending"
                                  : "Rejected"}
                            </Badge>
                          </div>
                        );
                      })}
                    </div>
                  )}
                </div>
              </div>
            </Card>
          </div>
        </div>
      </div>
    </AppShell>
  );
}

function PipelineStep({
  label,
  active,
  done,
}: {
  label: string;
  active: boolean;
  done: boolean;
}) {
  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        gap: 7,
        color: done
          ? "var(--green)"
          : active
            ? "var(--cyan)"
            : "var(--muted)",
        whiteSpace: "nowrap",
      }}
    >
      {done ? (
        <I.CheckCircle2 size={16} />
      ) : active ? (
        <I.CircleDot size={16} />
      ) : (
        <I.Circle size={16} />
      )}

      <span
        style={{
          fontWeight: 600,
          fontSize: 13,
        }}
      >
        {label}
      </span>
    </div>
  );
}

function InfoBlock({
  label,
  value,
}: {
  label: string;
  value: React.ReactNode;
}) {
  return (
    <div style={{ marginBottom: 14 }}>
      <div className="meta">{label}</div>
      <div
        style={{
          marginTop: 3,
          fontSize: 14,
          color: "var(--fg)",
        }}
      >
        {value}
      </div>
    </div>
  );
}