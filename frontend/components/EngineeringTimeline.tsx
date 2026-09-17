"use client";

import React, { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import {
  CheckCircle2,
  Clock,
  AlertTriangle,
  XCircle,
  Circle,
  User,
  Bot,
  Cpu,
  ArrowRight,
  ShieldCheck,
  GitPullRequest,
  GitBranch,
  RefreshCw,
  ExternalLink,
  ChevronDown,
  ChevronRight,
  Lock,
} from "lucide-react";
import {
  lifecycleService,
  type LifecycleStatusResponse,
  type TimelineNode,
} from "@/lib/lifecycle";

interface EngineeringTimelineProps {
  taskId?: string;
  pullRequestId?: string;
  changeId?: string;
  initialData?: LifecycleStatusResponse | null;
  pollingIntervalMs?: number;
  className?: string;
  style?: React.CSSProperties;
}

export function EngineeringTimeline({
  taskId,
  pullRequestId,
  changeId,
  initialData = null,
  pollingIntervalMs = 30000,
  className = "",
  style,
}: EngineeringTimelineProps) {
  const [data, setData] = useState<LifecycleStatusResponse | null>(initialData);
  const [loading, setLoading] = useState<boolean>(!initialData && Boolean(taskId || pullRequestId || changeId));
  const [error, setError] = useState<string | null>(null);
  const [expandedNodes, setExpandedNodes] = useState<Record<string, boolean>>({});
  const [lastRefreshed, setLastRefreshed] = useState<Date | null>(initialData ? new Date() : null);

  const fetchStatus = useCallback(async (isSilent = false) => {
    if (!taskId && !pullRequestId && !changeId) return;
    if (!isSilent) setLoading(true);
    setError(null);
    try {
      const res = await lifecycleService.getStatus({
        taskId,
        pullRequestId,
        changeId,
      });
      setData(res);
      setLastRefreshed(new Date());
    } catch (err: any) {
      if (!data) {
        setError(err?.message || "Failed to load engineering lifecycle status");
      }
    } finally {
      if (!isSilent) setLoading(false);
    }
  }, [taskId, pullRequestId, changeId, data]);

  useEffect(() => {
    fetchStatus(false);
    if (!pollingIntervalMs || pollingIntervalMs <= 0) return;

    const interval = setInterval(() => {
      // Don't poll if completed or failed
      if (data?.overall_state === "COMPLETED" || data?.overall_state === "MERGED") {
        return;
      }
      fetchStatus(true);
    }, pollingIntervalMs);

    return () => clearInterval(interval);
  }, [fetchStatus, pollingIntervalMs, data?.overall_state]);

  const toggleExpand = (stageKey: string) => {
    setExpandedNodes((prev) => ({
      ...prev,
      [stageKey]: !prev[stageKey],
    }));
  };

  const getStatusIcon = (status: TimelineNode["status"]) => {
    switch (status) {
      case "completed":
        return <CheckCircle2 size={18} style={{ color: "var(--green, #10b981)" }} />;
      case "active":
        return <Clock size={18} style={{ color: "var(--cyan, #00f0ff)" }} className="animate-spin-slow" />;
      case "blocked":
        return <AlertTriangle size={18} style={{ color: "var(--amber, #f59e0b)" }} />;
      case "failed":
        return <XCircle size={18} style={{ color: "var(--red, #ef4444)" }} />;
      case "pending":
      default:
        return <Circle size={16} style={{ color: "var(--muted, #64748b)", opacity: 0.6 }} />;
    }
  };

  const getActorBadge = (actorType: TimelineNode["actor_type"], actorId: string | null) => {
    switch (actorType) {
      case "human":
        return (
          <span
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: 4,
              fontSize: 11,
              fontWeight: 500,
              padding: "2px 8px",
              borderRadius: 12,
              background: "rgba(168, 85, 247, 0.12)",
              color: "#c084fc",
              border: "1px solid rgba(168, 85, 247, 0.25)",
            }}
          >
            <User size={11} />
            Human Authority
          </span>
        );
      case "agent":
        return (
          <span
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: 4,
              fontSize: 11,
              fontWeight: 500,
              padding: "2px 8px",
              borderRadius: 12,
              background: "rgba(0, 240, 255, 0.12)",
              color: "#38bdf8",
              border: "1px solid rgba(0, 240, 255, 0.25)",
            }}
          >
            <Bot size={11} />
            Autonomous Agent
          </span>
        );
      case "system":
      default:
        return (
          <span
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: 4,
              fontSize: 11,
              fontWeight: 500,
              padding: "2px 8px",
              borderRadius: 12,
              background: "rgba(148, 163, 184, 0.12)",
              color: "#94a3b8",
              border: "1px solid rgba(148, 163, 184, 0.25)",
            }}
          >
            <Cpu size={11} />
            SUTRA Governance
          </span>
        );
    }
  };

  if (loading && !data) {
    return (
      <div
        className={`timeline-container ${className}`}
        style={{
          background: "linear-gradient(180deg, #11141b 0%, #0d1017 100%)",
          border: "1px solid rgba(255, 255, 255, 0.08)",
          borderRadius: 20,
          padding: 24,
          ...style,
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 12, color: "var(--muted, #94a3b8)" }}>
          <RefreshCw size={18} className="animate-spin" style={{ color: "var(--cyan, #00f0ff)" }} />
          <span style={{ fontSize: 13, fontWeight: 500 }}>
            Querying authoritative SUTRA lifecycle status...
          </span>
        </div>
      </div>
    );
  }

  if (error && !data) {
    return (
      <div
        className={`timeline-container ${className}`}
        style={{
          background: "rgba(239, 68, 68, 0.05)",
          border: "1px solid rgba(239, 68, 68, 0.25)",
          borderRadius: 20,
          padding: 20,
          ...style,
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 10, color: "#ef4444", fontSize: 13 }}>
          <XCircle size={18} />
          <span>{error}</span>
          <button
            onClick={() => fetchStatus(false)}
            style={{
              marginLeft: "auto",
              background: "transparent",
              border: "1px solid rgba(239, 68, 68, 0.4)",
              color: "#ef4444",
              borderRadius: 6,
              padding: "4px 10px",
              cursor: "pointer",
              fontSize: 12,
            }}
          >
            Retry
          </button>
        </div>
      </div>
    );
  }

  if (!data) return null;

  const timeline = data.timeline || [];
  const blockedReasons = data.blocked_reasons || [];
  const overallState = data.overall_state;

  return (
    <div
      className={`engineering-timeline ${className}`}
      style={{
        background: "linear-gradient(180deg, #11141b 0%, #0b0d13 100%)",
        border: "1px solid rgba(255, 255, 255, 0.08)",
        borderRadius: 20,
        padding: "24px 28px",
        boxShadow: "0 10px 30px -10px rgba(0, 0, 0, 0.5)",
        ...style,
      }}
    >
      {/* Header & Meta Bar */}
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          flexWrap: "wrap",
          gap: 12,
          paddingBottom: 20,
          borderBottom: "1px solid rgba(255, 255, 255, 0.06)",
          marginBottom: 20,
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <div
            style={{
              width: 32,
              height: 32,
              borderRadius: 10,
              background: "rgba(0, 240, 255, 0.1)",
              border: "1px solid rgba(0, 240, 255, 0.2)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              color: "var(--cyan, #00f0ff)",
            }}
          >
            <ShieldCheck size={18} />
          </div>
          <div>
            <div style={{ fontSize: 15, fontWeight: 700, color: "var(--fg, #f8fafc)", letterSpacing: "-0.01em" }}>
              Authoritative Engineering Lifecycle
            </div>
            <div style={{ fontSize: 12, color: "var(--muted, #94a3b8)", marginTop: 2 }}>
              Canonical provenance & governance timeline across Task, Change, PR & Substrate
            </div>
          </div>
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          {lastRefreshed && (
            <span style={{ fontSize: 11, color: "var(--muted, #64748b)" }}>
              Refreshed {lastRefreshed.toLocaleTimeString()}
            </span>
          )}
          <button
            onClick={() => fetchStatus(false)}
            aria-label="Refresh Lifecycle Status"
            style={{
              background: "rgba(255, 255, 255, 0.04)",
              border: "1px solid rgba(255, 255, 255, 0.1)",
              color: "var(--fg, #e2e8f0)",
              borderRadius: 8,
              padding: "5px 10px",
              display: "inline-flex",
              alignItems: "center",
              gap: 6,
              fontSize: 12,
              cursor: "pointer",
              transition: "all 0.2s ease",
            }}
          >
            <RefreshCw size={13} className={loading ? "animate-spin" : ""} />
            Sync
          </button>
        </div>
      </div>

      {/* Next Action & Actor Callout Card */}
      <div
        style={{
          background:
            overallState === "COMPLETED" || overallState === "MERGED"
              ? "rgba(16, 185, 129, 0.06)"
              : overallState === "READY_FOR_MERGE"
              ? "rgba(16, 185, 129, 0.1)"
              : blockedReasons.length > 0
              ? "rgba(245, 158, 11, 0.08)"
              : "rgba(0, 240, 255, 0.06)",
          border:
            overallState === "COMPLETED" || overallState === "MERGED"
              ? "1px solid rgba(16, 185, 129, 0.25)"
              : overallState === "READY_FOR_MERGE"
              ? "1px solid rgba(16, 185, 129, 0.4)"
              : blockedReasons.length > 0
              ? "1px solid rgba(245, 158, 11, 0.3)"
              : "1px solid rgba(0, 240, 255, 0.25)",
          borderRadius: 14,
          padding: "16px 20px",
          marginBottom: 24,
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          flexWrap: "wrap",
          gap: 16,
        }}
      >
        <div style={{ flex: 1, minWidth: 260 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 4 }}>
            <span
              style={{
                fontSize: 11,
                fontWeight: 700,
                textTransform: "uppercase",
                letterSpacing: "0.05em",
                color:
                  overallState === "COMPLETED" || overallState === "MERGED"
                    ? "#10b981"
                    : overallState === "READY_FOR_MERGE"
                    ? "#34d399"
                    : blockedReasons.length > 0
                    ? "#f59e0b"
                    : "#38bdf8",
              }}
            >
              {`Current State: ${data.overall_state.replaceAll("_", " ")}`}
            </span>
            <span style={{ fontSize: 11, color: "var(--muted, #64748b)" }}>•</span>
            <span style={{ fontSize: 12, fontWeight: 600, color: "var(--fg, #f8fafc)" }}>
              {`Next Actor: ${data.next_actor}`}
            </span>
          </div>

          <div style={{ fontSize: 13, color: "var(--fg, #e2e8f0)", lineHeight: 1.4 }}>
            {data.overall_state === "COMPLETED" && (
              <span>✓ All gates satisfied: Change merged into substrate repository and engineering task completed.</span>
            )}
            {data.overall_state === "READY_FOR_MERGE" && (
              <span>All governance gates and CI checks passed. Human repository owner can execute governed merge.</span>
            )}
            {data.overall_state === "AWAITING_HUMAN_APPROVAL" && (
              <span>Autonomous work registered. Awaiting independent human code review & approval in SUTRA dashboard.</span>
            )}
            {data.overall_state === "IN_PROGRESS" && (
              <span>Task claimed by agent session. Agent commits locally via terminal git and calls <code style={{ color: "#38bdf8" }}>sutra_submit_change</code>.</span>
            )}
            {data.overall_state === "PENDING" && (
              <span>Task created. Awaiting autonomous agent to claim task lease and initiate implementation.</span>
            )}
            {(data.overall_state === "BLOCKED_ON_CI" || data.overall_state === "BLOCKED_ON_GOVERNANCE") && (
              <span>Progress blocked on automated verification gates. See blocker list below.</span>
            )}
          </div>
        </div>

        {/* Action Link / Context */}
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          {data.pull_request?.id && (
            <Link
              href={`/pull-requests/${data.pull_request.id}`}
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: 6,
                fontSize: 12,
                fontWeight: 600,
                padding: "8px 14px",
                borderRadius: 10,
                background:
                  data.overall_state === "READY_FOR_MERGE"
                    ? "var(--green, #10b981)"
                    : "rgba(255, 255, 255, 0.08)",
                color: data.overall_state === "READY_FOR_MERGE" ? "#000" : "var(--fg, #f8fafc)",
                textDecoration: "none",
                transition: "all 0.2s ease",
              }}
            >
              <GitPullRequest size={14} />
              <span>
                {data.overall_state === "READY_FOR_MERGE" ? "Review & Merge PR" : "View Pull Request"}
              </span>
            </Link>
          )}

          {data.task?.id && !data.pull_request?.id && (
            <Link
              href={`/tasks/${data.task.id}`}
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: 6,
                fontSize: 12,
                fontWeight: 600,
                padding: "8px 14px",
                borderRadius: 10,
                background: "rgba(0, 240, 255, 0.12)",
                color: "#38bdf8",
                textDecoration: "none",
              }}
            >
              <span>View Task</span>
              <ArrowRight size={13} />
            </Link>
          )}
        </div>
      </div>

      {/* Blockers Card if any */}
      {blockedReasons.length > 0 && (
        <div
          style={{
            background: "rgba(245, 158, 11, 0.08)",
            border: "1px solid rgba(245, 158, 11, 0.3)",
            borderRadius: 12,
            padding: "14px 18px",
            marginBottom: 24,
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: 8, color: "#f59e0b", fontWeight: 600, fontSize: 13, marginBottom: 8 }}>
            <AlertTriangle size={16} />
            <span>Active Lifecycle Blockers ({blockedReasons.length})</span>
          </div>
          <ul style={{ margin: 0, paddingLeft: 22, color: "#cbd5e1", fontSize: 12, lineHeight: 1.6 }}>
            {blockedReasons.map((reason, idx) => (
              <li key={idx} style={{ marginTop: idx > 0 ? 4 : 0 }}>
                {reason}
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Vertical Timeline Nodes */}
      <div style={{ position: "relative", paddingLeft: 8 }}>
        {/* Continuous Connecting Line */}
        <div
          style={{
            position: "absolute",
            top: 14,
            bottom: 14,
            left: 20,
            width: 2,
            background: "linear-gradient(180deg, rgba(0, 240, 255, 0.3) 0%, rgba(255, 255, 255, 0.08) 100%)",
            zIndex: 0,
          }}
        />

        <div style={{ display: "flex", flexDirection: "column", gap: 18 }}>
          {timeline.map((node, index) => {
            const isExpanded = Boolean(expandedNodes[node.stage]);
            const hasDetails = node.details && Object.keys(node.details).length > 0;
            const isCompleted = node.status === "completed";
            const isActive = node.status === "active";
            const isBlocked = node.status === "blocked";
            const isFailed = node.status === "failed";

            return (
              <div
                key={node.stage}
                style={{
                  position: "relative",
                  zIndex: 1,
                  display: "flex",
                  alignItems: "flex-start",
                  gap: 16,
                }}
              >
                {/* Node Icon Avatar */}
                <div
                  style={{
                    width: 26,
                    height: 26,
                    borderRadius: "50%",
                    background: isCompleted
                      ? "rgba(16, 185, 129, 0.15)"
                      : isActive
                      ? "rgba(0, 240, 255, 0.2)"
                      : isBlocked
                      ? "rgba(245, 158, 11, 0.15)"
                      : isFailed
                      ? "rgba(239, 68, 68, 0.15)"
                      : "rgba(15, 23, 42, 0.8)",
                    border: isCompleted
                      ? "2px solid #10b981"
                      : isActive
                      ? "2px solid #00f0ff"
                      : isBlocked
                      ? "2px solid #f59e0b"
                      : isFailed
                      ? "2px solid #ef4444"
                      : "2px solid rgba(255, 255, 255, 0.15)",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    flexShrink: 0,
                    boxShadow: isActive ? "0 0 12px rgba(0, 240, 255, 0.4)" : "none",
                    transition: "all 0.3s ease",
                  }}
                >
                  {getStatusIcon(node.status)}
                </div>

                {/* Node Content Card */}
                <div
                  style={{
                    flex: 1,
                    background: isActive
                      ? "rgba(0, 240, 255, 0.03)"
                      : "rgba(255, 255, 255, 0.02)",
                    border: isActive
                      ? "1px solid rgba(0, 240, 255, 0.25)"
                      : "1px solid rgba(255, 255, 255, 0.05)",
                    borderRadius: 12,
                    padding: "12px 16px",
                    transition: "all 0.2s ease",
                  }}
                >
                  <div
                    style={{
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "space-between",
                      flexWrap: "wrap",
                      gap: 8,
                    }}
                  >
                    <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                      <span
                        style={{
                          fontSize: 14,
                          fontWeight: 600,
                          color: isActive
                            ? "#38bdf8"
                            : isCompleted
                            ? "var(--fg, #f1f5f9)"
                            : "var(--muted, #94a3b8)",
                        }}
                      >
                        {node.label}
                      </span>
                      {getActorBadge(node.actor_type, node.actor_id)}
                    </div>

                    <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                      {node.timestamp && (
                        <span style={{ fontSize: 11, color: "var(--muted, #64748b)" }}>
                          {new Date(node.timestamp).toLocaleTimeString([], {
                            hour: "2-digit",
                            minute: "2-digit",
                            second: "2-digit",
                          })}
                        </span>
                      )}

                      {hasDetails && (
                        <button
                          onClick={() => toggleExpand(node.stage)}
                          aria-label={`Toggle details for ${node.label}`}
                          style={{
                            background: "transparent",
                            border: "none",
                            color: "var(--muted, #94a3b8)",
                            cursor: "pointer",
                            padding: 2,
                            display: "inline-flex",
                            alignItems: "center",
                          }}
                        >
                          {isExpanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
                        </button>
                      )}
                    </div>
                  </div>

                  {/* Node Context Snippets */}
                  {node.stage === "task_claimed" && data.session && (
                    <div style={{ fontSize: 12, color: "var(--muted, #94a3b8)", marginTop: 4 }}>
                      Session <code style={{ color: "#38bdf8" }}>{data.session.id.slice(0, 8)}</code>
                      {data.session.lease_expires_at && (
                        <span> • Lease active</span>
                      )}
                    </div>
                  )}

                  {node.stage === "work_submitted" && data.change && (
                    <div style={{ fontSize: 12, color: "var(--muted, #94a3b8)", marginTop: 4 }}>
                      Change <code style={{ color: "#38bdf8" }}>{data.change.id.slice(0, 8)}</code>
                      {data.change.commit_sha && (
                        <span> • Commit <code style={{ color: "#a78bfa" }}>{data.change.commit_sha.slice(0, 7)}</code></span>
                      )}
                    </div>
                  )}

                  {node.stage === "pull_request_opened" && data.pull_request && (
                    <div style={{ fontSize: 12, color: "var(--muted, #94a3b8)", marginTop: 4 }}>
                      PR <code style={{ color: "#38bdf8" }}>#{data.pull_request.id.slice(0, 8)}</code> • {data.pull_request.title}
                    </div>
                  )}

                  {node.stage === "ci_evaluating" && data.ci?.summary && (
                    <div style={{ fontSize: 12, color: "var(--muted, #94a3b8)", marginTop: 4 }}>
                      Checks: {data.ci.summary.passed}/{data.ci.summary.total} passing
                    </div>
                  )}

                  {node.stage === "awaiting_human_approval" && data.approval && (
                    <div style={{ fontSize: 12, color: "var(--muted, #94a3b8)", marginTop: 4 }}>
                      Approvals: {data.approval.current_approvals} / {data.approval.required_approvals} required
                      {data.approval.head_changed_after_approval && (
                        <span style={{ color: "#f59e0b", marginLeft: 6 }}>⚠️ PR HEAD changed since review</span>
                      )}
                    </div>
                  )}

                  {node.stage === "merged" && data.merge?.merge_commit_sha && (
                    <div style={{ fontSize: 12, color: "var(--muted, #94a3b8)", marginTop: 4 }}>
                      Merge Commit: <code style={{ color: "#34d399" }}>{data.merge.merge_commit_sha.slice(0, 7)}</code>
                    </div>
                  )}

                  {/* Expandable Details JSON Viewer */}
                  {isExpanded && hasDetails && (
                    <div
                      style={{
                        marginTop: 10,
                        padding: 10,
                        borderRadius: 8,
                        background: "rgba(0, 0, 0, 0.3)",
                        border: "1px solid rgba(255, 255, 255, 0.05)",
                        fontSize: 11,
                        fontFamily: "monospace",
                        color: "#94a3b8",
                        overflowX: "auto",
                      }}
                    >
                      <pre style={{ margin: 0 }}>{JSON.stringify(node.details, null, 2)}</pre>
                    </div>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
export default EngineeringTimeline;
