"use client";

import React, { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { Bot, CheckCircle2, GitBranch, Play, ShieldCheck, Plus, Check, GitPullRequest, ArrowRight, Sparkles } from "lucide-react";
import { Page, Card, Badge, Skeleton } from "@/components/ui";
import { AppShell } from "@/components/shell";
import { formatErrorMessage } from "@/lib/api";
import { Task, taskService } from "@/lib/tasks";
import { Agent, agentService } from "@/lib/agents";
import { ciService, type PRChecksResponse } from "@/lib/ci";
import { governanceService, type GovernanceEvaluation } from "@/lib/governance";
import { EngineeringTimeline } from "@/components/EngineeringTimeline";

export default function TaskPage() {
  const params = useParams() as any;
  const id = params?.id as string;
  
  const [task, setTask] = useState<Task | null>(null);
  const [agents, setAgents] = useState<Agent[]>([]);
  const [checks, setChecks] = useState<PRChecksResponse | null>(null);
  const [gov, setGov] = useState<GovernanceEvaluation | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);

  const loadData = () => {
    if (!id) return;
    setLoading(true);
    setLoadError(null);
    Promise.all([
      taskService.getTask(id),
      agentService.listAgents().catch(() => []) // gracefully handle if agents fail
    ])
    .then(([t, a]) => {
      setTask(t);
      setAgents(a);
      if (t?.resulting_pull_request_id) {
        ciService.getPRChecks(t.resulting_pull_request_id).then(setChecks).catch(() => {});
        governanceService.getPRGovernance(t.resulting_pull_request_id).then(setGov).catch(() => {});
      }
    })
    .catch((error) => {
      console.error(error);
      setLoadError(formatErrorMessage(error));
    })
    .finally(() => setLoading(false));
  };

  useEffect(() => {
    loadData();

    if (task && (task.status === "completed" || task.status === "done" || task.status === "cancelled")) {
      return;
    }

    // Active tasks need live updates, but terminal tasks should be quiet.
    const interval = setInterval(() => {
      if (!id) return;
      void loadData();
    }, 15000);
    
    return () => clearInterval(interval);
  }, [id, task?.status]);

  if (loading) {
    return (
      <AppShell>
        <Page eyebrow={"Task #" + id.slice(0, 8)} title="Task Execution Details" description="Loading sovereign session & governance status...">
          <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
            <Card style={{ padding: "24px 28px" }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 16 }}>
                <div style={{ display: "flex", flexDirection: "column", gap: 8, flex: 1 }}>
                  <Skeleton width={260} height={22} borderRadius={4} />
                  <Skeleton width={380} height={14} borderRadius={4} />
                </div>
                <Skeleton width={80} height={24} borderRadius={12} />
              </div>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(140px, 1fr))", gap: 12, marginTop: 20 }}>
                {[1, 2, 3, 4].map((i) => (
                  <div key={i} style={{ padding: 12, borderRadius: 8, background: "var(--bg-subtle)" }}>
                    <Skeleton width={60} height={11} borderRadius={3} style={{ marginBottom: 6 }} />
                    <Skeleton width={90} height={16} borderRadius={4} />
                  </div>
                ))}
              </div>
            </Card>
          </div>
        </Page>
      </AppShell>
    );
  }

  if (!task) {
    return (
      <AppShell>
        <Page eyebrow={"Task #" + id.slice(0, 8)} title={loadError ? "Unable to load task" : "Not Found"} description="">
          <p className="muted" style={{ padding: 20 }}>{loadError || "Task could not be found."}</p>
        </Page>
      </AppShell>
    );
  }

  const isCompleted = task.status === "completed" || task.status === "done";
  const isInProgress = task.status === "in_progress" || task.status === "assigned";
  const isOpen = task.status === "todo" || task.status === "open";

  const assignedAgent = agents.find(a => a.id === task.assigned_agent_id);

  return (
    <AppShell>
      <Page 
        eyebrow={
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <span>{"Task #" + id.slice(0, 8)}</span>
          {task.source === "agent" ? (
            <span className="badge indigo" style={{ fontSize: "11px", padding: "2px 8px", display: "inline-flex", alignItems: "center", gap: 4 }}>
              <Sparkles size={11} /> Agent-created Task
            </span>
          ) : (
            <span className="badge gray" style={{ fontSize: "11px", padding: "2px 8px" }}>
              Human-created Task
            </span>
          )}
        </div>
      }
      title={task.title} 
      description={task.description || "No description provided."} 
      actions={
        <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
          {task.resulting_change_id && (
             <Link href={`/changes/${task.resulting_change_id}`} className="btn outline" style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
               <GitBranch size={14} /> Open Change
             </Link>
          )}
          {task.resulting_pull_request_id && (
             <Link href={`/pull-requests/${task.resulting_pull_request_id}`} className="btn primary" style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
               <GitPullRequest size={14} /> View Pull Request
             </Link>
          )}
          <Link
            href={`/assistant`}
            className="btn outline"
            style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}
          >
            <Sparkles size={14} style={{ color: 'var(--cyan)' }} /> Ask Assistant
          </Link>
        </div>
      }
    >
      {/* Authoritative Single Primary Lifecycle State Banner */}
      {(() => {
        let primaryState = "READY";
        let primaryTone: "green" | "aqua" | "amber" | "red" | "violet" | "gray" = "gray";
        let primaryDesc = "Task is open and awaiting connected agent execution.";

        if (isCompleted) {
          primaryState = "COMPLETED";
          primaryTone = "green";
          primaryDesc = "Task implementation completed and verified.";
        } else if (task.status === "cancelled" || task.status === "failed") {
          primaryState = "FAILED";
          primaryTone = "red";
          primaryDesc = "Task execution was cancelled or failed.";
        } else if (checks && checks.overall_status === "failed") {
          primaryState = "BLOCKED";
          primaryTone = "red";
          primaryDesc = "Automated CI verification checks are failing.";
        } else if (gov && (gov.verdict === "BLOCKED" || gov.policy?.passed === false)) {
          primaryState = "BLOCKED";
          primaryTone = "red";
          primaryDesc = "Blocked by sovereign engineering governance policy.";
        } else if (gov?.review?.satisfied) {
          primaryState = "READY";
          primaryTone = "green";
          primaryDesc = "Required human reviews satisfied — ready for governed merge.";
        } else if (gov?.ready_for_approval || gov?.verdict === "READY_FOR_APPROVAL" || gov?.verdict === "NEEDS_REVIEW") {
          primaryState = "WAITING FOR APPROVAL";
          primaryTone = "amber";
          primaryDesc = "Awaiting required sovereign human reviewer approval.";
        } else if (task.resulting_pull_request_id) {
          primaryState = "WAITING FOR REVIEW";
          primaryTone = "violet";
          primaryDesc = "Pull request open — undergoing review and automated validation.";
        } else if (isInProgress || task.claimed_by_session_id) {
          primaryState = "RUNNING";
          primaryTone = "aqua";
          primaryDesc = "Connected agent actively executing task under active session lease.";
        }

        return (
          <div className="task-status-banner">
            <div className="task-status-main">
              <span className={`task-status-dot is-${primaryTone}`} />
              <div>
                <div className="task-status-kicker">Primary Lifecycle State</div>
                <div style={{ display: "flex", alignItems: "center", gap: 8, marginTop: 2 }}>
                  <strong style={{ fontSize: 16, letterSpacing: "0.02em" }}>{primaryState}</strong>
                  <Badge tone={primaryTone}>{primaryState}</Badge>
                </div>
                <div className="sub" style={{ marginTop: 4, fontSize: 12 }}>{primaryDesc}</div>
              </div>
            </div>
            <div className="task-status-meta">
              <span><span className="task-status-label">Next Actor</span>{isCompleted ? "None (Complete)" : primaryState === "WAITING FOR APPROVAL" ? "Human Reviewer" : isInProgress ? "Connected Agent" : "Agent Integration"}</span>
              <span><span className="task-status-label">Task ID</span><code>{id.slice(0, 8)}</code></span>
            </div>
          </div>
        );
      })()}

      {/* SUTRA Pipeline Stepper */}
      <Card className="task-pipeline" style={{ marginBottom: 20 }}>
        <div style={{ padding: "16px 20px", overflowX: "auto" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 10, minWidth: 720, fontSize: 13 }}>
            {[
              { label: "Task", active: true, done: isCompleted || isInProgress },
              { label: "AgentSession", active: Boolean(task.assigned_agent_id || task.active_session_id), done: Boolean(task.assigned_agent_id || task.active_session_id) },
              { label: "Issue", active: Boolean(task.issue_id), done: Boolean(task.issue_id) },
              { label: "Change", active: Boolean(task.resulting_change_id), done: Boolean(task.resulting_change_id) },
              { label: "GitHub PR", active: Boolean(task.resulting_pull_request_id), done: Boolean(task.resulting_pull_request_id) },
              { label: "Checks / CI", active: Boolean(task.resulting_pull_request_id), done: checks?.overall_status === 'passed' },
              { label: "Governance", active: checks?.overall_status === 'passed', done: Boolean(gov?.provenance?.verified && gov?.policy?.passed) },
              { label: "Approval", active: Boolean(gov?.ready_for_approval) || gov?.verdict === 'READY_FOR_APPROVAL' || gov?.verdict === 'NEEDS_REVIEW', done: Boolean(gov?.review?.satisfied) || isCompleted },
              { label: "Merge", active: Boolean(gov?.review?.satisfied), done: isCompleted },
            ].map((step, idx, arr) => (
              <React.Fragment key={step.label}>
                <div style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 6,
                  color: step.done ? "var(--green)" : step.active ? "var(--cyan)" : "var(--muted)",
                  fontWeight: step.active || step.done ? 600 : 400
                }}>
                  {step.done ? <CheckCircle2 size={15} /> : step.active ? <Play size={14} /> : <div style={{ width: 8, height: 8, borderRadius: "50%", background: "var(--line)" }} />}
                  <span>{step.label}</span>
                </div>
                {idx < arr.length - 1 && (
                  <ArrowRight size={13} style={{ color: "var(--line)", flexShrink: 0 }} />
                )}
              </React.Fragment>
            ))}
          </div>
        </div>
      </Card>

      {/* Agent Execution & Validation Record Card */}
      {(task.source === "agent" || task.execution_summary || task.validation_summary) && (
        <Card className="task-record" style={{ marginBottom: 20, border: "1px solid rgba(129, 140, 248, 0.25)", background: "var(--bg-subtle)" }}>
          <div style={{ padding: "18px 20px" }}>
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 14, borderBottom: "1px solid var(--line)", paddingBottom: 12 }}>
              <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                <div style={{ width: 32, height: 32, borderRadius: "50%", background: "rgba(129, 140, 248, 0.15)", display: "flex", alignItems: "center", justifyContent: "center" }}>
                  <Sparkles size={16} style={{ color: "var(--indigo, #818cf8)" }} />
                </div>
                <div>
                  <h3 style={{ fontSize: 14, fontWeight: 600, margin: 0, color: "var(--fg)" }}>Agent Engineering Record</h3>
                  <div style={{ fontSize: 12, color: "var(--muted)" }}>Autonomous task provenance, execution recap & validation telemetry</div>
                </div>
              </div>
              <Badge tone={task.source === "agent" ? "purple" : "gray"}>
                {task.source === "agent" ? "Auto-created from Prompt" : "Human Created"}
              </Badge>
            </div>

            <div style={{ display: "grid", gridTemplateColumns: task.validation_summary ? "1fr 1fr" : "1fr", gap: 14 }}>
              {/* Execution Summary */}
              <div style={{ background: "rgba(0, 0, 0, 0.2)", padding: "12px 14px", borderRadius: 8, border: "1px solid var(--line)" }}>
                <div style={{ fontSize: 11, textTransform: "uppercase", letterSpacing: "0.05em", color: "var(--cyan)", fontWeight: 600, marginBottom: 6 }}>
                  Execution Summary
                </div>
                <div style={{ fontSize: 13, lineHeight: 1.5, color: "var(--text-primary)", whiteSpace: "pre-wrap" }}>
                  {task.execution_summary || "Agent task active. Awaiting execution summary on completion..."}
                </div>
              </div>

              {/* Validation Summary */}
              {task.validation_summary && (
                <div style={{ background: "rgba(0, 0, 0, 0.2)", padding: "12px 14px", borderRadius: 8, border: "1px solid var(--line)" }}>
                  <div style={{ fontSize: 11, textTransform: "uppercase", letterSpacing: "0.05em", color: "var(--green)", fontWeight: 600, marginBottom: 6 }}>
                    Validation & Test Verification
                  </div>
                  <div style={{ fontSize: 13, lineHeight: 1.5, color: "var(--text-primary)", whiteSpace: "pre-wrap" }}>
                    {task.validation_summary}
                  </div>
                </div>
              )}
            </div>

            {task.description && (
              <div style={{ marginTop: 12, paddingTop: 10, borderTop: "1px solid var(--line)", fontSize: 12, color: "var(--muted)", display: "flex", gap: 6 }}>
                <strong style={{ color: "var(--fg)", flexShrink: 0 }}>User Intent / Prompt:</strong>
                <span style={{ color: "var(--text-secondary)" }}>{task.description}</span>
              </div>
            )}
          </div>
        </Card>
      )}

      {/* Authoritative Engineering Lifecycle Timeline */}
      <EngineeringTimeline
        taskId={id}
        pullRequestId={task.resulting_pull_request_id || undefined}
        changeId={task.resulting_change_id || undefined}
        className="task-lifecycle"
        style={{ marginBottom: 20 }}
      />

      {/* Resulting Pull Request Banner if exists */}
      {task.resulting_pull_request_id && (
        <Card className="task-pr-banner" style={{ marginBottom: 20, border: "1px solid rgba(0, 240, 255, 0.25)", background: "var(--bg-subtle)" }}>
          <div style={{ padding: "16px 20px", display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: 14 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
              <div style={{ width: 34, height: 34, borderRadius: "50%", background: "rgba(0, 240, 255, 0.1)", display: "flex", alignItems: "center", justifyContent: "center" }}>
                <GitPullRequest size={17} style={{ color: "var(--cyan)" }} />
              </div>
              <div>
                <div style={{ fontSize: 14, fontWeight: 600, color: "var(--fg)", display: "flex", alignItems: "center", gap: 8 }}>
                  <span>Resulting Substrate Pull Request</span>
                  {isCompleted && <Badge tone="green">✓ MERGED</Badge>}
                </div>
                <div style={{ fontSize: 12, color: "var(--muted)", marginTop: 2 }}>
                  {isCompleted 
                    ? `Pull Request was approved by human reviewer and merged into substrate repository.`
                    : `Autonomous Agent session produced and linked SUTRA Pull Request #${task.resulting_pull_request_id.slice(0, 8)}`}
                </div>
                {checks && (
                  <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginTop: 6, fontSize: 12, flexWrap: 'wrap' }}>
                    <span style={{ 
                      fontWeight: 600,
                      color: checks.overall_status === 'passed' ? 'var(--green)' : checks.overall_status === 'failed' ? '#ff4d4f' : 'var(--cyan)' 
                    }}>
                      CI Checks: {checks.summary.passed}/{checks.summary.total} passing
                    </span>
                    <Badge tone={checks.overall_status === 'passed' ? 'green' : checks.overall_status === 'failed' ? 'red' : 'aqua'}>
                      {checks.governance_verdict}
                    </Badge>
                    {gov && (
                      <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6, marginLeft: 6 }}>
                        <span style={{ fontWeight: 600, color: 'var(--fg)' }}>Governance:</span>
                        <Badge tone={gov.verdict === 'READY_FOR_MERGE' ? 'green' : gov.verdict === 'READY_FOR_APPROVAL' ? 'aqua' : gov.verdict === 'NEEDS_REVIEW' ? 'amber' : gov.verdict === 'CI_PENDING' ? 'aqua' : 'red'}>
                          {gov.verdict.replaceAll('_', ' ')}
                        </Badge>
                      </span>
                    )}
                    {gov?.review && (
                      <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6, marginLeft: 6 }}>
                        <span style={{ fontWeight: 600, color: 'var(--fg)' }}>Approval:</span>
                        <span style={{ color: gov.review.satisfied ? 'var(--green)' : 'var(--amber)', fontWeight: 600 }}>
                          {gov.review.actual_approvals} / {gov.review.required_approvals}
                        </span>
                        <span style={{ fontSize: 11, color: 'var(--muted)' }}>
                          {gov.review.satisfied ? 'Approved by Human Reviewer' : 'Needs human reviewer'}
                        </span>
                      </span>
                    )}
                  </div>
                )}
              </div>
            </div>
            <Link href={`/pull-requests/${task.resulting_pull_request_id}`} className="btn primary" style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
              <GitPullRequest size={14} /> View Pull Request
            </Link>
          </div>
        </Card>
      )}

      <div className="grid grid3 task-stats">
        {/* Agent Card */}
        <Card className="task-stat-card">
          <div className="statlabel">Agent Status</div>
          {isOpen ? (
            <div style={{ marginTop: 12 }}>
              <div className="sub" style={{ marginBottom: 8, fontSize: 13, color: "var(--muted)" }}>
                Agents connect to SUTRA through supported integrations.
              </div>
              <div style={{ padding: "10px 12px", background: "rgba(255,255,255,0.02)", border: "1px solid var(--line)", borderRadius: 8, fontSize: 12, color: "var(--text-secondary)" }}>
                Open for autonomous claiming via MCP or Agent Protocol.
              </div>
            </div>
          ) : (
            <>
              <div className="agentcard" style={{marginTop:12}}>
                <div className="agenticon"><Bot size={18}/></div>
                <div>
                  <strong>{assignedAgent ? assignedAgent.name : (task.assigned_agent_id || "Connected Agent")}</strong>
                  <div className="sub">{assignedAgent ? assignedAgent.model : "Autonomous Agent"}</div>
                </div>
                {isCompleted ? <Badge tone="gray">finished</Badge> : <Badge tone="green">active</Badge>}
              </div>
              <div className="section">
                <div className="sub">Assignment status</div>
                <div style={{marginTop:6}}>
                  <strong className={isCompleted ? "muted" : "cyan"}>{isCompleted ? "Completed" : "Active Lease"}</strong>
                  {task.lease_expires_at && !isCompleted && (
                    <span className="muted" style={{marginLeft: 6, fontSize: 11}}>
                      · Lease active
                    </span>
                  )}
                </div>
              </div>
            </>
          )}
        </Card>

        {/* Execution Card */}
        <Card className="task-stat-card">
          <div className="statlabel">Execution Lifecycle</div>
          <div style={{ marginTop: 10 }}>
            <div style={{ fontSize: 18, fontWeight: 600, color: isCompleted ? "var(--green)" : isInProgress ? "var(--cyan)" : "var(--muted)" }}>
              {isCompleted ? "Complete" : isInProgress ? "Active Execution" : "Pending Intake"}
            </div>
            <div className="sub" style={{ marginTop: 8, fontSize: 12 }}>
              {task.completed_at ? `Completed ${new Date(task.completed_at).toLocaleString()}`
               : task.started_at ? `Started ${new Date(task.started_at).toLocaleString()}`
               : `Created ${new Date(task.created_at).toLocaleString()}`}
            </div>
            {task.execution_summary && (
              <div style={{ marginTop: 10, fontSize: 12, padding: "8px 10px", background: "rgba(0,0,0,0.2)", borderRadius: 6, border: "1px solid var(--line)", whiteSpace: "pre-wrap" }}>
                {task.execution_summary}
              </div>
            )}
          </div>
        </Card>

        {/* Validation Card */}
        <Card className="task-stat-card">
          <div className="statlabel">Validation & CI</div>
          <div style={{marginTop:10}}>
            {checks ? (
              checks.summary.total === 0 ? (
                <>
                  <div className="statusline green" style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                    <CheckCircle2 size={14} /> No CI workflow required
                  </div>
                  <div style={{ marginTop: 6, fontSize: 11, color: 'var(--muted)' }}>
                    No CI workflow configured in repository. Governance evaluation is not blocked.
                  </div>
                </>
              ) : (
                <>
                  <div className={`statusline ${checks.overall_status === 'passed' ? 'green' : checks.overall_status === 'failed' ? 'red' : 'cyan'}`}>
                    {checks.overall_status === 'passed' ? <CheckCircle2 size={14} /> : <Play size={14} />}
                    {checks.summary.passed} / {checks.summary.total} checks passing
                  </div>
                  <div style={{ marginTop: 8, fontSize: 12, display: 'flex', alignItems: 'center', gap: 6 }}>
                    <ShieldCheck size={14} style={{ color: checks.governance_verdict === 'READY FOR GOVERNANCE' ? 'var(--green)' : 'var(--amber)' }} />
                    <span>Verdict: <strong>{checks.governance_verdict}</strong></span>
                  </div>
                  {checks.checks.length > 0 && (
                    <div style={{ marginTop: 8, display: 'flex', flexDirection: 'column', gap: 4 }}>
                      {checks.checks.slice(0, 3).map(chk => (
                        <div key={chk.id} style={{ fontSize: 11, color: 'var(--muted)', display: 'flex', alignItems: 'center', gap: 6 }}>
                          <span style={{ color: chk.status === 'passed' ? 'var(--green)' : chk.status === 'failed' ? '#ff4d4f' : 'var(--cyan)' }}>
                            {chk.status === 'passed' ? '✓' : chk.status === 'failed' ? '✗' : '●'}
                          </span>
                          <span>{chk.name}</span>
                        </div>
                      ))}
                    </div>
                  )}
                </>
              )
            ) : isCompleted ? (
              <div className="statusline green" style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                <CheckCircle2 size={14} /> Execution verified
              </div>
            ) : isInProgress ? (
              <div className="statusline cyan" style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                <Play size={14} /> CI checks evaluating upon PR creation
              </div>
            ) : (
              <div className="muted" style={{ fontSize: 13 }}>Validation triggers on PR creation.</div>
            )}
          </div>
        </Card>
      </div>

      {(isInProgress || isCompleted) && (
        <div className="section task-output">
          <Card className="task-timeline-card">
            <div className="sectionhead">
              <h2>Agent execution timeline</h2>
              {isInProgress ? <Badge tone="cyan">In Progress</Badge> : <Badge>Archived</Badge>}
            </div>
            <div className="timeline">
              <div className="event">
                <strong>{task.source === "agent" ? "Task auto-created by agent" : "Task created"}</strong>
                <p>{task.source === "agent" ? "Spawned from user prompt" : "By user"} · {new Date(task.created_at).toLocaleString()}</p>
              </div>
              {task.started_at && (
                <div className="event">
                  <strong>Agent picked up task</strong>
                  <p>Started execution · {new Date(task.started_at).toLocaleString()}</p>
                </div>
              )}
              {isCompleted && (
                <div className="event">
                  <strong>Completed</strong>
                  <p>Changes committed · {task.completed_at ? new Date(task.completed_at).toLocaleString() : ''}</p>
                </div>
              )}
            </div>
          </Card>
        </div>
      )}
    </Page>
  </AppShell>
);
}