"use client";

import { use, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { AppShell, PageHead, Card, Btn, Badge } from "@/components/shell";
import { pullRequestService, PullRequest, PRReview, PREvent, PRChange } from "@/lib/pull-requests";
import { ciService, CIJob } from "@/lib/ci";
import { authService } from "@/lib/auth";
import * as I from "lucide-react";

function timeAgo(dateStr: string) {
  const diff = Date.now() - new Date(dateStr).getTime();
  const m = Math.floor(diff / 60000);
  if (m < 1) return "just now";
  if (m < 60) return `${m}m ago`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}h ago`;
  return `${Math.floor(h / 24)}d ago`;
}

const STATUS_COLORS: Record<string, string> = {
  open: "var(--cyan)", draft: "var(--muted)", approved: "var(--green)",
  merged: "var(--purple)", closed: "var(--muted)", rejected: "var(--red)",
};

export default function PullRequestDetailPage({ params }: { params: Promise<{ name: string; id: string }> }) {
  const { name: repoName, id: prId } = use(params);
  const router = useRouter();
  const [pr, setPr] = useState<PullRequest | null>(null);
  const [change, setChange] = useState<PRChange | null>(null);
  const [reviews, setReviews] = useState<PRReview[]>([]);
  const [events, setEvents] = useState<PREvent[]>([]);
  const [ciJobs, setCiJobs] = useState<CIJob[]>([]);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState("Conversation");
  const [actionLoading, setActionLoading] = useState(false);

  useEffect(() => {
    const load = async () => {
      setLoading(true);
      try {
        const [prData, reviewData, eventData, jobsData] = await Promise.all([
          pullRequestService.getPR(prId),
          pullRequestService.getPRReviews(prId).catch(() => []),
          pullRequestService.getPREvents(prId).catch(() => []),
          ciService.listJobsForPR(prId).catch(() => []),
        ]);
        setPr(prData);
        setReviews(reviewData);
        setEvents(eventData);
        setCiJobs(jobsData);

        // Load the associated Change and its diffs
        try {
          const changeData = await pullRequestService.getPRChange(prId);
          setChange(changeData);
        } catch (_) {
          setChange(null);
        }

      } catch (e) {
        console.error("Failed to load PR", e);
        setPr(null);
      } finally {
        setLoading(false);
      }
    };
    load();
  }, [prId]);

  const handleApprove = async () => {
    if (!pr) return;
    setActionLoading(true);
    try {
      const updated = await pullRequestService.approvePR(pr.id);
      setPr(updated);
    } catch (e: any) {
      alert(e?.message || "Failed to approve");
    } finally {
      setActionLoading(false);
    }
  };

  const handleMerge = async () => {
    if (!pr) return;
    setActionLoading(true);
    try {
      await pullRequestService.mergePR(pr.id);
      const updated = await pullRequestService.getPR(pr.id);
      setPr(updated);
    } catch (e: any) {
      alert(e?.message || "Failed to merge");
    } finally {
      setActionLoading(false);
    }
  };

  const handleClose = async () => {
    if (!pr) return;
    setActionLoading(true);
    try {
      const updated = await pullRequestService.closePR(pr.id);
      setPr(updated);
    } catch (e: any) {
      alert(e?.message || "Failed to close");
    } finally {
      setActionLoading(false);
    }
  };

  if (loading) {
    return <AppShell><div style={{ padding: 48, textAlign: "center", color: "var(--muted)" }}>Loading pull request...</div></AppShell>;
  }

  if (!pr) {
    return (
      <AppShell>
        <div style={{ padding: 48, maxWidth: 500, margin: "60px auto", textAlign: "center", background: "var(--bg-subtle)", borderRadius: 12, border: "1px solid var(--line)" }}>
          <I.GitPullRequest size={36} color="var(--muted)" style={{ marginBottom: 16 }} />
          <div style={{ fontSize: 18, fontWeight: 600, color: "var(--fg)", marginBottom: 8 }}>Pull Request Not Found</div>
          <div style={{ color: "var(--muted)", marginBottom: 24 }}>This PR does not exist or you don't have access.</div>
          <Btn onClick={() => router.back()}>Go Back</Btn>
        </div>
      </AppShell>
    );
  }

  const statusColor = STATUS_COLORS[pr.status] || "var(--fg)";
  const canApprove = pr.status === "open" || pr.status === "draft";
  const canMerge = pr.status === "approved";
  const canClose = pr.status === "open" || pr.status === "draft";

  const hasPassedCI = ciJobs.some(j => j.status === "passed");
  const hasFailedCI = ciJobs.some(j => j.status === "failed");
  const isRunningCI = ciJobs.some(j => j.status === "running" || j.status === "queued" || j.status === "pending");

  const tabs = ["Conversation", `Changes`, "Checks", "Activity"];

  return (
    <AppShell>
      <PageHead
        eyebrow="Pull Requests"
        title={pr.title}
        sub={`${repoName} • ${pr.source_commit ? pr.source_commit.slice(0,7) : "—"} → ${pr.target_branch} • opened ${timeAgo(pr.created_at)}`}
      />

      <div style={{ maxWidth: 1200, margin: "0 auto", padding: "0 20px" }}>

        {/* Status Bar */}
        <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 24, padding: "12px 20px", background: "var(--bg-subtle)", borderRadius: 8, border: `1px solid ${statusColor}40` }}>
          <div style={{ width: 10, height: 10, borderRadius: "50%", background: statusColor }} />
          <span style={{ fontWeight: 700, color: statusColor, fontSize: 13, textTransform: "uppercase", letterSpacing: "0.5px" }}>
            {pr.status}
          </span>
          <span style={{ color: "var(--muted)", fontSize: 13 }}>
            {pr.merged_at ? `Merged ${timeAgo(pr.merged_at)}` : pr.closed_at ? `Closed ${timeAgo(pr.closed_at)}` : `Updated ${timeAgo(pr.updated_at)}`}
          </span>
          {pr.source_commit && pr.target_commit && (
            <div style={{ marginLeft: "auto", display: "flex", alignItems: "center", gap: 8, fontSize: 13, fontFamily: "monospace", color: "var(--muted)" }}>
              <I.GitBranch size={13} />
              <span>{pr.source_commit.slice(0,7)}</span>
              <I.ArrowRight size={13} />
              <span>{pr.target_commit.slice(0,7)}</span>
            </div>
          )}
        </div>

        {/* Pipeline Checks Row */}
        <div style={{ display: "flex", alignItems: "center", gap: 0, marginBottom: 28, background: "var(--bg-subtle)", borderRadius: 8, border: "1px solid var(--line)", overflow: "hidden" }}>
          {[
            {
              label: "CI",
              icon: hasPassedCI ? <I.CheckCircle2 size={14} color="var(--green)" /> : hasFailedCI ? <I.XCircle size={14} color="var(--red)" /> : isRunningCI ? <I.PlayCircle size={14} color="var(--yellow)" /> : <I.Circle size={14} />,
              done: hasPassedCI,
              state: hasPassedCI ? "passed" : hasFailedCI ? "failed" : isRunningCI ? "running" : "none",
            },
            {
              label: "Review",
              icon: reviews.some(r => r.status === "approved") ? <I.CheckCircle2 size={14} color="var(--green)" /> : reviews.some(r => r.status === "rejected") ? <I.XCircle size={14} color="var(--red)" /> : <I.Users size={14} />,
              done: reviews.some(r => r.status === "approved"),
              state: reviews.some(r => r.status === "approved") ? "approved" : reviews.length > 0 ? "pending" : "none",
            },
            {
              label: "Merge",
              icon: <I.GitMerge size={14} />,
              done: pr.status === "merged",
              state: pr.status === "merged" ? "merged" : "open",
            },
          ].map((step, idx) => (
            <div key={step.label} style={{
              flex: 1, display: "flex", alignItems: "center", justifyContent: "center", gap: 6, padding: "12px 0",
              borderRight: idx < 2 ? "1px solid var(--line)" : "none",
              color: step.done ? "var(--green)" : step.state === "failed" ? "var(--red)" : step.state === "running" ? "var(--yellow)" : "var(--muted)",
              fontSize: 13, fontWeight: 600,
            }}>
              {step.icon}
              {step.label}
              <span style={{ fontSize: 11, fontWeight: 400, opacity: 0.8 }}>({step.state})</span>
            </div>
          ))}
        </div>

        {/* Main 2-column layout */}
        <div style={{ display: "flex", gap: 32, alignItems: "flex-start" }}>

          {/* LEFT - Tabs + Content */}
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ display: "flex", borderBottom: "1px solid var(--line)", marginBottom: 24 }}>
              {tabs.map(tab => (
                <button key={tab} onClick={() => setActiveTab(tab)} style={{
                  padding: "10px 18px", background: "transparent", border: "none",
                  borderBottom: activeTab === tab ? "2px solid var(--cyan)" : "2px solid transparent",
                  color: activeTab === tab ? "var(--fg)" : "var(--muted)",
                  fontWeight: activeTab === tab ? 600 : 400, cursor: "pointer", fontSize: 14,
                }}>
                  {tab}
                </button>
              ))}
            </div>

            {/* Conversation Tab */}
            {activeTab === "Conversation" && (
              <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
                {pr.description && (
                  <Card style={{ padding: 20 }}>
                    <div style={{ fontSize: 13, fontWeight: 700, color: "var(--muted)", textTransform: "uppercase", letterSpacing: "0.5px", marginBottom: 10 }}>Description</div>
                    <div style={{ fontSize: 14, color: "var(--fg)", lineHeight: 1.7, whiteSpace: "pre-wrap" }}>{pr.description}</div>
                  </Card>
                )}

                {/* Events timeline */}
                {events.length > 0 && (
                  <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                    {events.map(ev => (
                      <div key={ev.id} style={{ display: "flex", alignItems: "flex-start", gap: 10, padding: "10px 0", borderBottom: "1px solid var(--line)40" }}>
                        <div style={{ width: 28, height: 28, borderRadius: "50%", background: "var(--bg-subtle)", border: "1px solid var(--line)", display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0 }}>
                          <I.Activity size={13} color="var(--muted)" />
                        </div>
                        <div>
                          <div style={{ fontSize: 13, color: "var(--fg)" }}>
                            <span style={{ fontWeight: 600 }}>{ev.event_type}</span>
                            {ev.from_status && ev.to_status && (
                              <span style={{ color: "var(--muted)" }}> — {ev.from_status} → {ev.to_status}</span>
                            )}
                          </div>
                          {ev.reason && <div style={{ fontSize: 12, color: "var(--muted)", marginTop: 2 }}>{ev.reason}</div>}
                          <div style={{ fontSize: 12, color: "var(--muted)", marginTop: 2 }}>{timeAgo(ev.created_at)}</div>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}

            {/* Changes Tab - Real diff viewer */}
            {activeTab === "Changes" && (
              <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
                {change ? (
                  <>
                    <Card style={{ padding: 0 }}>
                      <div style={{ padding: "14px 16px", background: "var(--bg-subtle)", borderBottom: "1px solid var(--line)" }}>
                        <div style={{ fontSize: 13, fontWeight: 700, color: "var(--fg)", marginBottom: 8 }}>
                          Linked Change
                        </div>
                        <div style={{ fontSize: 14, color: "var(--fg)", lineHeight: 1.6, whiteSpace: "pre-wrap" }}>
                          {change.intent || "No change intent recorded."}
                        </div>
                      </div>

                      <div style={{ display: "grid", gridTemplateColumns: "repeat(3,minmax(0,1fr))", gap: 1, background: "var(--line)" }}>
                        <div style={{ background: "var(--bg)", padding: 16 }}>
                          <div className="meta">Base commit</div>
                          <div style={{ marginTop: 6, fontFamily: "monospace", fontSize: 12, color: "var(--fg)", wordBreak: "break-all" }}>
                            {change.base_commit ? change.base_commit.slice(0, 10) : "Not recorded"}
                          </div>
                        </div>

                        <div style={{ background: "var(--bg)", padding: 16 }}>
                          <div className="meta">Resulting commit</div>
                          <div style={{ marginTop: 6, fontFamily: "monospace", fontSize: 12, color: "var(--fg)", wordBreak: "break-all" }}>
                            {change.resulting_commit ? change.resulting_commit.slice(0, 10) : "Not recorded"}
                          </div>
                        </div>

                        <div style={{ background: "var(--bg)", padding: 16 }}>
                          <div className="meta">Risk level</div>
                          <div style={{ marginTop: 6, fontSize: 13, fontWeight: 600, color: change.risk_level === "high" ? "var(--red)" : change.risk_level === "medium" ? "var(--yellow)" : "var(--green)" }}>
                            {change.risk_level || "Not specified"}
                          </div>
                        </div>
                      </div>
                    </Card>

                    {/* Files Diff Card */}
                    <Card>
                      <div className="card-head">
                        <div>
                          <div className="h2">Changed Files ({change.files_changed || change.files?.length || 0})</div>
                          <div className="sub" style={{ display: "flex", gap: 12, marginTop: 4 }}>
                            <span style={{ color: "var(--green)", fontWeight: 600 }}>+{change.additions || 0} additions</span>
                            <span style={{ color: "var(--red)", fontWeight: 600 }}>-{change.deletions || 0} deletions</span>
                          </div>
                        </div>
                        <Badge>{change.status}</Badge>
                      </div>

                      {change.files && change.files.length > 0 ? (
                        <div className="list">
                          {change.files.map((file, idx) => (
                            <div key={idx} className="list-row" style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                              <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                                <I.FileCode size={16} color="var(--muted)" />
                                <span style={{ fontFamily: "monospace", fontSize: 13, color: "var(--fg)" }}>{file.path}</span>
                              </div>
                              <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
                                <span style={{ fontSize: 12, fontFamily: "monospace", color: "var(--green)" }}>+{file.additions}</span>
                                <span style={{ fontSize: 12, fontFamily: "monospace", color: "var(--red)" }}>-{file.deletions}</span>
                                <Badge tone={file.operation === "added" ? "green" : file.operation === "deleted" ? "red" : "cyan"}>
                                  {file.operation}
                                </Badge>
                              </div>
                            </div>
                          ))}
                        </div>
                      ) : (
                        <div className="card-pad" style={{ textAlign: "center", padding: "32px 0" }}>
                          <I.FileText size={24} style={{ opacity: 0.35, marginBottom: 8 }} />
                          <div className="sub">No file modifications recorded in this change.</div>
                        </div>
                      )}
                    </Card>
                  </>
                ) : (
                  <Card>
                    <div className="card-pad" style={{ textAlign: "center", padding: "44px 0" }}>
                      <I.GitPullRequest size={28} style={{ opacity: 0.35, marginBottom: 12 }} />
                      <div className="h2">No linked change</div>
                      <div className="sub">This pull request does not have an associated Change record.</div>
                    </div>
                  </Card>
                )}
              </div>
            )}

            {/* Checks Tab - Real CI Jobs */}
            {activeTab === "Checks" && (
              <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
                {ciJobs.length === 0 ? (
                  <Card>
                    <div className="card-pad" style={{ textAlign: "center", padding: "44px 0" }}>
                      <I.PlayCircle size={28} style={{ opacity: 0.35, marginBottom: 12 }} />
                      <div className="h2">No checks have run yet.</div>
                      <div className="sub">No CI jobs have been executed for this pull request.</div>
                    </div>
                  </Card>
                ) : (
                  <Card>
                    <div className="card-head">
                      <div>
                        <div className="h2">CI Runs ({ciJobs.length})</div>
                        <div className="sub">Automated verification pipelines for commit {pr.source_commit ? pr.source_commit.slice(0, 8) : "—"}</div>
                      </div>
                    </div>
                    <div className="list">
                      {ciJobs.map((job) => (
                        <div key={job.id} className="list-row" style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                          <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
                            {job.status === "passed" ? (
                              <I.CheckCircle2 size={18} color="var(--green)" />
                            ) : job.status === "failed" ? (
                              <I.XCircle size={18} color="var(--red)" />
                            ) : job.status === "running" ? (
                              <I.PlayCircle size={18} color="var(--yellow)" />
                            ) : (
                              <I.Circle size={18} color="var(--muted)" />
                            )}
                            <div>
                              <div style={{ fontWeight: 600, fontSize: 13, color: "var(--fg)" }}>
                                Job #{job.id.slice(0, 8)} · {job.trigger}
                              </div>
                              <div className="meta" style={{ fontSize: 12 }}>
                                Commit {job.commit_sha.slice(0, 8)} · Runner: {job.runner_type} · {timeAgo(job.created_at)}
                              </div>
                              {job.failure_reason && (
                                <div style={{ fontSize: 12, color: "var(--red)", marginTop: 4 }}>
                                  Reason: {job.failure_reason}
                                </div>
                              )}
                            </div>
                          </div>
                          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                            <Badge tone={job.status === "passed" ? "green" : job.status === "failed" ? "red" : job.status === "running" ? "yellow" : "cyan"}>
                              {job.status}
                            </Badge>
                          </div>
                        </div>
                      ))}
                    </div>
                  </Card>
                )}
              </div>
            )}

            {/* Activity Tab */}
            {activeTab === "Activity" && (
              <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                {events.length === 0 ? (
                  <div style={{ padding: 40, textAlign: "center", color: "var(--muted)" }}>No activity yet.</div>
                ) : events.map(ev => (
                  <div key={ev.id} style={{ padding: "12px 16px", background: "var(--bg-subtle)", borderRadius: 6, border: "1px solid var(--line)", display: "flex", justifyContent: "space-between" }}>
                    <div>
                      <span style={{ fontWeight: 600, fontSize: 13, color: "var(--fg)" }}>{ev.event_type}</span>
                      {ev.reason && <span style={{ fontSize: 13, color: "var(--muted)" }}> — {ev.reason}</span>}
                    </div>
                    <span style={{ fontSize: 12, color: "var(--muted)" }}>{timeAgo(ev.created_at)}</span>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* RIGHT sidebar */}
          <div style={{ width: 280, flexShrink: 0, display: "flex", flexDirection: "column", gap: 20 }}>

            {/* Reviewers */}
            <Card style={{ padding: 16 }}>
              <div style={{ fontSize: 11, fontWeight: 700, color: "var(--muted)", textTransform: "uppercase", letterSpacing: "1px", marginBottom: 12 }}>Approvals & Reviews</div>
              {reviews.length === 0 ? (
                <div style={{ fontSize: 13, color: "var(--muted)" }}>No reviews requested yet.</div>
              ) : reviews.map(r => (
                <div key={r.id} style={{ display: "flex", alignItems: "center", justifyContent: "space-between", fontSize: 13, marginBottom: 8 }}>
                  <div style={{ display: "flex", alignItems: "center", gap: 6, color: "var(--fg)" }}>
                    <div style={{ width: 22, height: 22, borderRadius: "50%", background: "var(--bg-subtle)", border: "1px solid var(--line)", display: "flex", alignItems: "center", justifyContent: "center" }}>
                      <I.User size={11} color="var(--muted)" />
                    </div>
                    <span>{r.reviewer_id ? r.reviewer_id.slice(0, 8) : "Human Reviewer"}</span>
                  </div>
                  <span style={{
                    color: r.status === "approved" ? "var(--green)" : r.status === "rejected" ? "var(--red)" : "var(--yellow)",
                    fontSize: 12,
                    display: "flex",
                    alignItems: "center",
                    gap: 4
                  }}>
                    {r.status === "approved" ? (
                      <><I.CheckCircle2 size={12} /> Approved</>
                    ) : r.status === "rejected" ? (
                      <><I.XCircle size={12} /> Changes Requested</>
                    ) : (
                      <><I.CircleDashed size={12} /> Pending Review</>
                    )}
                  </span>
                </div>
              ))}
            </Card>

            {/* Branch info */}
            <Card style={{ padding: 16 }}>
              <div style={{ fontSize: 11, fontWeight: 700, color: "var(--muted)", textTransform: "uppercase", letterSpacing: "1px", marginBottom: 12 }}>Branch</div>
              <div style={{ fontSize: 13, color: "var(--muted)", marginBottom: 6 }}>Target</div>
              <div style={{ fontSize: 13, fontFamily: "monospace", color: "var(--fg)", display: "flex", alignItems: "center", gap: 6 }}>
                <I.GitBranch size={13} color="var(--cyan)" /> {pr.target_branch}
              </div>
              {pr.source_commit && (
                <>
                  <div style={{ fontSize: 13, color: "var(--muted)", marginTop: 12, marginBottom: 6 }}>Commit</div>
                  <div style={{ fontSize: 12, fontFamily: "monospace", color: "var(--fg)" }}>{pr.source_commit.slice(0, 14)}</div>
                </>
              )}
            </Card>

            {/* Actions */}
            <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
              {canApprove && (
                <Btn primary onClick={handleApprove} disabled={actionLoading} style={{ width: "100%", justifyContent: "center" }}>
                  <I.CheckCircle2 size={14} style={{ marginRight: 6 }} /> Approve
                </Btn>
              )}
              {canMerge && pr.status !== "merged" && (
                <Btn primary onClick={handleMerge} disabled={actionLoading} style={{ width: "100%", justifyContent: "center", background: "var(--purple)" }}>
                  <I.GitMerge size={14} style={{ marginRight: 6 }} /> Merge Pull Request
                </Btn>
              )}
              {pr.status === "merged" && (
                <div style={{ padding: "12px 16px", borderRadius: 8, background: "rgba(168,85,247,0.08)", border: "1px solid rgba(168,85,247,0.25)", fontSize: 13, color: "var(--purple)", textAlign: "center", fontWeight: 600 }}>
                  <I.GitMerge size={14} style={{ marginRight: 6 }} /> Merged
                </div>
              )}
              {canClose && (
                <Btn onClick={handleClose} disabled={actionLoading} style={{ width: "100%", justifyContent: "center" }}>
                  Close PR
                </Btn>
              )}
            </div>

          </div>
        </div>
      </div>
    </AppShell>
  );
}
