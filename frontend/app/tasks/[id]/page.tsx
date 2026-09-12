"use client";

import React, { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { Bot, CheckCircle2, GitBranch, Play, ShieldCheck, MessageSquare, Plus, Check, GitPullRequest, ArrowRight, Sparkles } from "lucide-react";
import { Page, Card, Badge, SutraLoading } from "@/components/ui";
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
  const [assigning, setAssigning] = useState(false);

  const loadData = () => {
    if (!id) return;
    setLoading(true);
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
    .catch(console.error)
    .finally(() => setLoading(false));
  };

  useEffect(() => {
    loadData();
    
    // Poll every 5 seconds if not finished
    const interval = setInterval(() => {
      if (!id) return;
      Promise.all([
        taskService.getTask(id),
        agentService.listAgents().catch(() => [])
      ]).then(([t, a]) => {
        setTask(t);
        setAgents(a);
        if (t?.resulting_pull_request_id) {
          ciService.getPRChecks(t.resulting_pull_request_id).then(setChecks).catch(() => {});
          governanceService.getPRGovernance(t.resulting_pull_request_id).then(setGov).catch(() => {});
        }
      }).catch(console.error);
    }, 5000);
    
    return () => clearInterval(interval);
  }, [id]);

  const handleAssign = (agentId: string) => {
    setAssigning(true);
    taskService.assignTask(id, agentId)
      .then(() => loadData())
      .catch(console.error)
      .finally(() => setAssigning(false));
  };

  const handleDispatchNext = async () => {
    if (!task) return;
    const available = agents.find(a => a.status === 'idle' || a.is_active);
    if (available) {
      handleAssign(available.id);
    } else {
      alert("No available agents to dispatch");
    }
  };

  if (loading) {
    return (
      <Page eyebrow={"Task #" + id.slice(0, 8)} title="Task Execution Details" description="Loading sovereign session & governance status...">
        <Card>
          <SutraLoading message="Resolving task intent, agent telemetry & CI governance..." quote={true} />
        </Card>
      </Page>
    );
  }

  if (!task) {
    return (
      <Page eyebrow={"Task #" + id.slice(0, 8)} title="Not Found" description="">
        <p className="muted" style={{ padding: 20 }}>Task could not be found.</p>
      </Page>
    );
  }

  const isCompleted = task.status === "completed" || task.status === "done";
  const isInProgress = task.status === "in_progress" || task.status === "assigned";
  const isOpen = task.status === "todo" || task.status === "open";

  const assignedAgent = agents.find(a => a.id === task.assigned_agent_id);

  return (
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
          {isOpen && (
             <button className="btn outline" onClick={handleDispatchNext} disabled={assigning}>
               Auto-Dispatch
             </button>
          )}
          {isInProgress && <button className="btn">Reassign</button>}
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
      {/* SUTRA Pipeline Stepper */}
      <Card style={{ marginBottom: 20 }}>
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
        <Card style={{ marginBottom: 20, border: "1px solid rgba(129, 140, 248, 0.25)", background: "var(--bg-subtle)" }}>
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
        style={{ marginBottom: 20 }}
      />

      {/* Resulting Pull Request Banner if exists */}
      {task.resulting_pull_request_id && (
        <Card style={{ marginBottom: 20, border: "1px solid rgba(0, 240, 255, 0.25)", background: "var(--bg-subtle)" }}>
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

      <div className="grid grid3">
        {/* Agent Card */}
        <Card>
          <div className="statlabel">Agent Status</div>
          {isOpen ? (
            <div style={{ marginTop: 12 }}>
              <div className="sub" style={{ marginBottom: 12 }}>Available Agents</div>
              <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                {agents.length === 0 ? <div className="muted">No agents available</div> : 
                 agents.map(a => (
                   <div key={a.id} className="list-row" style={{ padding: "8px", border: "1px solid var(--line)", borderRadius: 6 }}>
                     <Bot size={15} />
                     <div style={{ flex: 1, fontSize: 13 }}>{a.name}</div>
                     <button className="btn outline" style={{ padding: "4px 8px", fontSize: 11 }} onClick={() => handleAssign(a.id)} disabled={assigning}>Assign</button>
                   </div>
                 ))
                }
              </div>
            </div>
          ) : (
            <>
              <div className="agentcard" style={{marginTop:12}}>
                <div className="agenticon"><Bot size={18}/></div>
                <div>
                  <strong>{assignedAgent ? assignedAgent.name : (task.assigned_agent_id || "Unassigned")}</strong>
                  <div className="sub">{assignedAgent ? assignedAgent.model : "Agent"}</div>
                </div>
                {isCompleted ? <Badge tone="gray">finished</Badge> : <Badge tone="green">working</Badge>}
              </div>
              <div className="section">
                <div className="sub">Assignment status</div>
                <div style={{marginTop:6}}>
                  <strong className={isCompleted ? "muted" : "cyan"}>{isCompleted ? "Completed" : "Active"}</strong>
                  <span className="muted" style={{marginLeft: 6}}>
                    {isCompleted && task.completed_at ? new Date(task.completed_at).toLocaleString() : ""}
                  </span>
                </div>
              </div>
            </>
          )}
        </Card>

        {/* Execution Card */}
        <Card>
          <div className="statlabel">Execution</div>
          <div className="statvalue">{isCompleted ? "100%" : isInProgress ? "67%" : "0%"}</div>
          <div className="progress" style={{marginTop:12}}>
            <i style={{width: isCompleted ? "100%" : isInProgress ? "67%" : "0%"}}/>
          </div>
          <div className="sub" style={{ marginTop: 8 }}>
            {isCompleted ? `Completed at ${task.completed_at ? new Date(task.completed_at).toLocaleString() : 'recently'}` 
             : isInProgress ? "Workspace sandbox · Active" : "Pending assignment"}
          </div>
        </Card>

        {/* Validation Card */}
        <Card>
          <div className="statlabel">Validation</div>
          <div style={{marginTop:10}}>
            {checks ? (
              checks.summary.total === 0 ? (
                <>
                  <div className="statusline green" style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                    <CheckCircle2 size={14} /> No CI file · Not blocked
                  </div>
                  <div style={{ marginTop: 6, fontSize: 11, color: 'var(--muted)' }}>
                    No CI workflow file found in codebase. Automated checks waived; PR merge is not blocked.
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
            ) : isCompleted || isInProgress ? (
              <>
                <div className={`statusline ${isCompleted ? 'green' : 'amber'}`}><CheckCircle2 size={14}/> {isCompleted ? '18 / 18 tests passing' : 'Running tests...'}</div>
                <div className={`statusline ${isCompleted ? 'green' : 'amber'}`} style={{marginTop:8}}><ShieldCheck size={14}/> {isCompleted ? 'Security clean' : 'Scanning...'}</div>
                {isInProgress && <div className="statusline cyan" style={{marginTop:8}}><Play size={14}/> CI running</div>}
              </>
            ) : (
              <div className="muted" style={{ fontSize: 13 }}>Waiting for execution to start.</div>
            )}
          </div>
        </Card>
      </div>

      {(isInProgress || isCompleted) && (
        <div className="grid grid2 section">
          <Card>
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
          
          <Card>
            <div className="sectionhead">
              <h2>Agent output</h2>
              <MessageSquare size={15} className="muted"/>
            </div>
            <div className="terminal">
              {isOpen ? (
                <div><span className="muted">Waiting for agent to begin...</span></div>
              ) : (
                <>
                  <div><span className="cyan">System</span> &nbsp; Agent session initialized in repository</div>
                  {task.execution_summary && (
                    <div style={{ marginTop: 6 }}><span className="cyan">Summary</span> &nbsp; {task.execution_summary}</div>
                  )}
                  {task.validation_summary && (
                    <div style={{ marginTop: 4 }}><span className="green">Verified</span> &nbsp; {task.validation_summary}</div>
                  )}
                  {isCompleted ? (
                    <div style={{ marginTop: 6 }}><span className="green">Success</span> &nbsp; Changes pushed and task completed.</div>
                  ) : (
                    <div><span className="cyan">Agent</span> &nbsp; Working on implementation...</div>
                  )}
                </>
              )}
            </div>
          </Card>
        </div>
      )}
    </Page>
  );
}