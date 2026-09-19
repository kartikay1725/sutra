"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { useParams } from "next/navigation";
import { agentService, type Agent, type AgentSession, type AgentRepositoryAccess } from "../lib/agents";
import { Badge, Btn, Card, PageHead, Stat } from "./shell";
import { I } from "../lib/icons";
import { repositoryService, type Repository } from "../lib/repositories";
import { taskService, type Task } from "../lib/tasks";
import { ConfirmModal } from "./ConfirmModal";

function fmt(value: string | null): string {
  if (!value) return "—";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString();
}

export function AgentDetailLive() {
  const params = useParams<{ id: string }>();
  const agentId = params?.id || "";

  const [agent, setAgent] = useState<Agent | null>(null);
  const [sessions, setSessions] = useState<AgentSession[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [revoking, setRevoking] = useState<string | null>(null);
  const [revokingAgent, setRevokingAgent] = useState(false);

  const [accessList, setAccessList] = useState<AgentRepositoryAccess[]>([]);
  const [allRepos, setAllRepos] = useState<Repository[]>([]);
  const [selectedRepoId, setSelectedRepoId] = useState("");
  const [granting, setGranting] = useState(false);
  const [tasks, setTasks] = useState<Task[]>([]);
  const [terminatingTaskId, setTerminatingTaskId] = useState<string | null>(null);
  const [confirmConfig, setConfirmConfig] = useState<{
    isOpen: boolean;
    title: string;
    description: React.ReactNode;
    confirmText?: string;
    confirmTone?: "danger" | "warning";
    onConfirm: () => Promise<void>;
  } | null>(null);

  const [notification, setNotification] = useState<{
    message: string;
    type: "success" | "error" | "info";
  } | null>(null);

  // Pagination state: 10 items per page
  const [sessionsPage, setSessionsPage] = useState(1);
  const [tasksPage, setTasksPage] = useState(1);
  const PAGE_SIZE = 10;

  const showToast = (message: string, type: "success" | "error" | "info" = "success") => {
    setNotification({ message, type });
    window.setTimeout(() => {
      setNotification((curr) => (curr?.message === message ? null : curr));
    }, 3500);
  };

  const load = async (silent = false) => {
    if (!agentId) return;
    try {
      if (!silent) {
        setLoading(true);
        setError(null);
      }
      const current = await agentService.getAgent(agentId);
      if (!current) {
        if (!silent) setError("Agent not found.");
        return;
      }
      setAgent(current);
      
      const [sess, access, repos, allTasks] = await Promise.all([
        agentService.listSessions(current.id).catch(() => [] as AgentSession[]),
        agentService.listRepositoryAccess(current.id).catch(() => [] as AgentRepositoryAccess[]),
        repositoryService.listRepositories().catch(() => [] as Repository[]),
        taskService.listAllTasks().catch(() => [] as Task[]),
      ]);
      
      setSessions(sess);
      setAccessList(access);
      setAllRepos(repos);
      setTasks(allTasks.filter((t) => t.assigned_agent_id === current.id));
    } catch (err: any) {
      console.error(err);
      if (!silent) {
        setError(err?.detail || err?.message || "Failed to load agent.");
      }
    } finally {
      if (!silent) {
        setLoading(false);
      }
    }
  };

  useEffect(() => {
    void load();
  }, [agentId]);

  const activeSessions = useMemo(
    () => sessions.filter((session) => session.status === "active"),
    [sessions],
  );

  const paginatedSessions = useMemo(() => {
    const start = (sessionsPage - 1) * PAGE_SIZE;
    return sessions.slice(start, start + PAGE_SIZE);
  }, [sessions, sessionsPage]);

  const totalSessionPages = Math.max(1, Math.ceil(sessions.length / PAGE_SIZE));

  const paginatedTasks = useMemo(() => {
    const start = (tasksPage - 1) * PAGE_SIZE;
    return tasks.slice(start, start + PAGE_SIZE);
  }, [tasks, tasksPage]);

  const totalTaskPages = Math.max(1, Math.ceil(tasks.length / PAGE_SIZE));

  const handleRevoke = async (sessionId: string) => {
    try {
      setRevoking(sessionId);
      await agentService.revokeSession(sessionId);
      await load(true);
      showToast("Session revoked successfully");
    } catch (err: any) {
      setError(err?.detail || err?.message || "Failed to revoke session.");
    } finally {
      setRevoking(null);
    }
  };

  const handleRevokeAgent = () => {
    if (!agent) return;
    setConfirmConfig({
      isOpen: true,
      title: "Revoke Agent",
      description: (
        <>
          Are you sure you want to revoke <strong>{agent.name}</strong>? This will deactivate the agent and invalidate all active sessions immediately.
        </>
      ),
      confirmText: "Revoke Agent",
      confirmTone: "danger",
      onConfirm: async () => {
        setRevokingAgent(true);
        try {
          await agentService.revokeAgent(agent.id);
          await load(true);
          setConfirmConfig(null);
          showToast("Agent revoked successfully");
        } catch (err: any) {
          setError(err?.detail || err?.message || "Failed to revoke agent.");
        } finally {
          setRevokingAgent(false);
        }
      },
    });
  };

  const handleTerminateTask = (task: Task) => {
    setConfirmConfig({
      isOpen: true,
      title: "Terminate Task",
      description: (
        <>
          Are you sure you want to terminate <strong>&ldquo;{task.title}&rdquo;</strong>? Active execution will be aborted immediately and the task status will be set to cancelled.
        </>
      ),
      confirmText: "Terminate Task",
      confirmTone: "danger",
      onConfirm: async () => {
        setTerminatingTaskId(task.id);
        try {
          await taskService.terminateTask(task.id);
          await load(true);
          setConfirmConfig(null);
          showToast(`Task "${task.title}" terminated`);
        } catch (err: any) {
          setError(err?.detail || err?.message || "Failed to terminate task.");
        } finally {
          setTerminatingTaskId(null);
        }
      },
    });
  };

  const togglePermission = async (access: AgentRepositoryAccess, permission: string) => {
    if (!agent) return;
    const isCurrentlyEnabled = access.permissions.includes(permission);
    const newPermissions = isCurrentlyEnabled
      ? access.permissions.filter(p => p !== permission)
      : [...access.permissions, permission];

    // Optimistically update local state immediately without full-page spinner or scroll loss
    setAccessList(prev =>
      prev.map(item =>
        item.repository_id === access.repository_id
          ? { ...item, permissions: newPermissions }
          : item
      )
    );

    const actionText = isCurrentlyEnabled ? "disabled" : "enabled";
    showToast(`[${permission}] ${actionText} for ${access.repository_name}`);

    try {
      await agentService.updateRepositoryAccess(
        agent.id,
        access.repository_id,
        newPermissions,
        access.enabled
      );
      // Refresh silently in background to keep full sync
      await load(true);
    } catch (err: any) {
      // Revert optimistic update on failure
      setAccessList(prev =>
        prev.map(item =>
          item.repository_id === access.repository_id
            ? { ...item, permissions: access.permissions }
            : item
        )
      );
      showToast(`Failed to update [${permission}]`, "error");
      setError(err?.detail || err?.message || "Failed to update permissions.");
    }
  };

  const handleGrant = async () => {
    if (!agent || !selectedRepoId) return;
    try {
      setGranting(true);
      const defaultPerms = [
        "repository.read",
        "repository.write",
        "change.create",
        "change.commit",
        "change.conflict.read"
      ];
      await agentService.grantRepositoryAccess(agent.id, selectedRepoId, defaultPerms);
      setSelectedRepoId("");
      await load(true);
      showToast("Repository access granted");
    } catch (err: any) {
      setError(err?.detail || err?.message || "Failed to grant repository access.");
    } finally {
      setGranting(false);
    }
  };

  const handleRevokeAccess = (repositoryId: string, repoName?: string) => {
    if (!agent) return;
    setConfirmConfig({
      isOpen: true,
      title: "Revoke Repository Access",
      description: (
        <>
          Are you sure you want to revoke access to <strong>{repoName || "this repository"}</strong>? This agent will no longer be able to perform operations on that repository.
        </>
      ),
      confirmText: "Revoke Access",
      confirmTone: "danger",
      onConfirm: async () => {
        try {
          await agentService.revokeRepositoryAccess(agent.id, repositoryId);
          await load(true);
          setConfirmConfig(null);
          showToast(`Revoked access to ${repoName || "repository"}`);
        } catch (err: any) {
          setError(err?.detail || err?.message || "Failed to revoke repository access.");
        }
      },
    });
  };

  if (loading) {
    return (
      <div style={{ padding: 48, textAlign: "center", color: "var(--muted)" }}>
        <div style={{ marginBottom: 12 }}>Loading agent…</div>
      </div>
    );
  }

  if (error || !agent) {
    return (
      <div style={{ padding: 48, maxWidth: 460, margin: "60px auto", textAlign: "center", background: "var(--bg-subtle, rgba(255,255,255,0.02))", borderRadius: 12, border: "1px solid var(--line)" }}>
        <I.Bot size={32} style={{ marginBottom: 12, opacity: 0.3 }} />
        <div style={{ fontSize: 17, fontWeight: 600, color: "var(--fg, #fff)", marginBottom: 8 }}>
          Agent Not Found
        </div>
        <div className="sub" style={{ marginBottom: 18, color: "#ff8fa0" }}>
          {error || "The agent does not exist or has been removed."}
        </div>
        <div style={{ display: "flex", gap: 10, justifyContent: "center" }}>
          <Btn onClick={() => void load()}>Try Again</Btn>
          <Link className="btn" href="/agents">Back to Agents</Link>
        </div>
      </div>
    );
  }

  return (
    <>
      {/* Smooth Toast Notification */}
      {notification && (
        <div
          style={{
            position: "fixed",
            bottom: 24,
            right: 24,
            zIndex: 9999,
            display: "flex",
            alignItems: "center",
            gap: 10,
            padding: "12px 18px",
            borderRadius: 12,
            background: notification.type === "error"
              ? "linear-gradient(145deg, #2a1215 0%, #17090b 100%)"
              : "linear-gradient(145deg, #121826 0%, #0d111a 100%)",
            border: notification.type === "error"
              ? "1px solid rgba(239, 68, 68, 0.4)"
              : "1px solid rgba(99, 102, 241, 0.4)",
            boxShadow: "0 10px 30px rgba(0, 0, 0, 0.5), 0 0 20px rgba(99, 102, 241, 0.15)",
            color: notification.type === "error" ? "#fca5a5" : "#c7d2fe",
            fontSize: 13,
            fontWeight: 500,
            animation: "slideInSmooth 0.3s cubic-bezier(0.16, 1, 0.3, 1)",
            backdropFilter: "blur(8px)",
          }}
        >
          {notification.type === "error" ? (
            <I.XCircle size={16} style={{ color: "#ef4444", flexShrink: 0 }} />
          ) : (
            <I.ShieldCheck size={16} style={{ color: "var(--cyan, #22d3ee)", flexShrink: 0 }} />
          )}
          <span>{notification.message}</span>
          <button
            onClick={() => setNotification(null)}
            style={{
              background: "none",
              border: "none",
              color: "inherit",
              cursor: "pointer",
              padding: 2,
              marginLeft: 8,
              opacity: 0.6,
              display: "flex",
            }}
            title="Dismiss"
          >
            <I.XCircle size={14} />
          </button>
        </div>
      )}

      <PageHead
        eyebrow={`Agent · ${agent.name}`}
        title={agent.name}
        sub={
          [
            agent.description || "No description provided.",
            agent.provider ? `Provider: ${agent.provider}` : null,
            agent.model ? `Model: ${agent.model}` : null,
          ].filter(Boolean).join(" · ")
        }
        action={
          <div style={{ display: "flex", gap: 8 }}>
            <Btn onClick={() => void load(false)}>
              Refresh
            </Btn>
            {agent.status === "active" && (
              <Btn
                disabled={revokingAgent}
                onClick={() => void handleRevokeAgent()}
                style={{ backgroundColor: "var(--red, #ff4d4f)", color: "#fff" }}
              >
                {revokingAgent ? "Revoking…" : "Revoke Agent"}
              </Btn>
            )}
          </div>
        }
      />

      <div className="grid g4">
        <Stat label="Status" value={agent.status} />
        <Stat label="Token prefix" value={agent.token_prefix} />
        <Stat label="Repo access" value={`${accessList.length} ${accessList.length === 1 ? "repo" : "repos"}`} />
        <Stat label="Active sessions" value={`${activeSessions.length} active`} />
      </div>

      <Card style={{ marginTop: 14 }}>
        <div className="card-head">
          <div>
            <div className="h2">Agent sessions</div>
            <div className="sub">Real authenticated agent sessions. No fabricated run history.</div>
          </div>
          <Badge tone={activeSessions.length ? "green" : "amber"}>
            {activeSessions.length} active
          </Badge>
        </div>

        {sessions.length === 0 ? (
          <div className="card-pad">
            <div className="sub">No agent sessions have been created yet.</div>
          </div>
        ) : (
          <>
            <div className="list">
              {paginatedSessions.map((session) => (
                <div className="list-row" key={session.session_id}>
                  <I.Bot size={15} style={{ color: "#63e5e8" }} />
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div className="title-sm">
                      {session.token_prefix}…
                    </div>
                    <div className="meta">
                      Created {fmt(session.created_at)} · last seen {fmt(session.last_seen_at)} · expires {fmt(session.expires_at)}
                    </div>
                  </div>
                  <Badge tone={session.status === "active" ? "green" : "amber"}>
                    {session.status}
                  </Badge>
                  {session.status === "active" && (
                    <Btn
                      disabled={revoking === session.session_id}
                      onClick={() => void handleRevoke(session.session_id)}
                    >
                      {revoking === session.session_id ? "Revoking…" : "Revoke"}
                    </Btn>
                  )}
                </div>
              ))}
            </div>

            {/* Sessions Pagination (10 per page) */}
            {sessions.length > PAGE_SIZE && (
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "space-between",
                  padding: "12px 16px",
                  borderTop: "1px solid var(--line)",
                  background: "rgba(255, 255, 255, 0.015)",
                }}
              >
                <div className="meta" style={{ fontSize: 12 }}>
                  Showing {(sessionsPage - 1) * PAGE_SIZE + 1}–{Math.min(sessionsPage * PAGE_SIZE, sessions.length)} of {sessions.length} sessions
                </div>
                <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                  <Btn
                    disabled={sessionsPage <= 1}
                    onClick={() => setSessionsPage((p) => Math.max(1, p - 1))}
                    style={{ padding: "4px 10px", fontSize: 12 }}
                  >
                    Previous
                  </Btn>
                  <span style={{ fontSize: 12, color: "var(--muted)", minWidth: 48, textAlign: "center" }}>
                    {sessionsPage} / {totalSessionPages}
                  </span>
                  <Btn
                    disabled={sessionsPage >= totalSessionPages}
                    onClick={() => setSessionsPage((p) => Math.min(totalSessionPages, p + 1))}
                    style={{ padding: "4px 10px", fontSize: 12 }}
                  >
                    Next
                  </Btn>
                </div>
              </div>
            )}
          </>
        )}
      </Card>

      <Card style={{ marginTop: 14 }}>
        <div className="card-head">
          <div>
            <div className="h2">Repository Access & Capabilities</div>
            <div className="sub">Grant repository access and toggle individual agent capabilities.</div>
          </div>
        </div>

        <div className="card-pad form" style={{ display: "flex", gap: 12, alignItems: "flex-end", borderBottom: "1px solid var(--line)" }}>
          <div className="field" style={{ flex: 1, margin: 0 }}>
            <label className="label">Add repository access</label>
            <select
              className="input select"
              value={selectedRepoId}
              onChange={(e) => setSelectedRepoId(e.target.value)}
              disabled={granting}
            >
              <option value="">Select a repository...</option>
              {allRepos
                .filter((r) => !accessList.some((a) => a.repository_id === r.id))
                .map((r) => (
                  <option key={r.id} value={r.id}>
                    {r.name} ({r.visibility})
                  </option>
                ))}
            </select>
          </div>
          <Btn onClick={() => void handleGrant()} disabled={!selectedRepoId || granting}>
            {granting ? "Granting..." : "Grant Access"}
          </Btn>
        </div>

        {accessList.length === 0 ? (
          <div className="card-pad">
            <div className="sub">No repository access has been granted yet. This agent cannot perform operations on SUTRA.</div>
          </div>
        ) : (
          <div className="list">
            {accessList.map((access) => {
              const capabilitiesList = [
                "repository.read",
                "repository.write",
                "change.create",
                "change.commit",
                "change.conflict.read",
                "workflow.read",
                "workflow.write",
                "discussion.read",
                "discussion.create",
                "discussion.comment",
                "knowledge_graph.read",
                "knowledge_graph.write"
              ];
              return (
                <div key={access.repository_id} style={{ display: "flex", flexDirection: "column", padding: "16px", borderBottom: "1px solid var(--line)" }}>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", flexWrap: "wrap", gap: 8, marginBottom: 12 }}>
                    <div style={{ minWidth: 200, flex: 1 }}>
                      <div className="title-sm" style={{ fontSize: 15, fontWeight: 600, wordBreak: "break-all" }}>
                        {access.repository_owner} / {access.repository_name}
                      </div>
                      <div className="meta" style={{ wordBreak: "break-all" }}>Repository ID: {access.repository_id}</div>
                    </div>
                    <Btn
                      style={{ backgroundColor: "var(--red, #ff4d4f)", color: "#fff", padding: "4px 8px", fontSize: 12, flexShrink: 0 }}
                      onClick={() => handleRevokeAccess(access.repository_id, `${access.repository_owner}/${access.repository_name}`)}
                    >
                      Revoke Repo
                    </Btn>
                  </div>
                  <div className="field">
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 10 }}>
                      <label className="label" style={{ fontSize: 11, textTransform: "uppercase", letterSpacing: "0.05em", color: "var(--muted)", margin: 0 }}>
                        Repository Capabilities & Permissions
                      </label>
                      <span className="meta" style={{ fontSize: 11 }}>
                        {access.permissions.length} granted
                      </span>
                    </div>

                    <div style={{
                      display: "grid",
                      gridTemplateColumns: "repeat(auto-fill, minmax(260px, 1fr))",
                      gap: 8,
                      width: "100%",
                    }}>
                      {capabilitiesList.map((perm) => {
                        const active = access.permissions.includes(perm);
                        return (
                          <div
                            key={perm}
                            onClick={() => void togglePermission(access, perm)}
                            style={{
                              display: "flex",
                              alignItems: "center",
                              justifyContent: "space-between",
                              padding: "9px 12px",
                              borderRadius: "8px",
                              backgroundColor: active ? "rgba(99, 102, 241, 0.08)" : "rgba(255, 255, 255, 0.02)",
                              border: `1px solid ${active ? "rgba(99, 102, 241, 0.3)" : "var(--line)"}`,
                              cursor: "pointer",
                              transition: "all 0.2s cubic-bezier(0.4, 0, 0.2, 1)",
                              userSelect: "none",
                            }}
                          >
                            <div style={{ display: "flex", flexDirection: "column", minWidth: 0, paddingRight: 8 }}>
                              <span style={{
                                fontFamily: "monospace",
                                fontSize: "12px",
                                fontWeight: active ? 600 : 400,
                                color: active ? "#c7d2fe" : "var(--text)",
                                whiteSpace: "nowrap",
                                overflow: "hidden",
                                textOverflow: "ellipsis",
                              }}>
                                {perm}
                              </span>
                            </div>

                            {/* Modern Switch Toggle UI with Fluid Motion */}
                            <div
                              style={{
                                width: 34,
                                height: 18,
                                borderRadius: 10,
                                backgroundColor: active ? "#6366f1" : "rgba(255, 255, 255, 0.15)",
                                position: "relative",
                                flexShrink: 0,
                                transition: "background-color 0.25s cubic-bezier(0.4, 0, 0.2, 1)",
                              }}
                            >
                              <div
                                style={{
                                  width: 14,
                                  height: 14,
                                  borderRadius: "50%",
                                  backgroundColor: "#fff",
                                  position: "absolute",
                                  top: 2,
                                  left: active ? 18 : 2,
                                  boxShadow: "0 1px 3px rgba(0,0,0,0.3)",
                                  transition: "left 0.25s cubic-bezier(0.4, 0, 0.2, 1)",
                                }}
                              />
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </Card>

      <Card style={{ marginTop: 14 }}>
        <div className="card-head">
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <I.ShieldCheck size={16} style={{ color: "var(--cyan)" }} />
            <div className="h2">Authority Boundaries & Governance Invariants</div>
          </div>
          <Badge tone="aqua">Enforced</Badge>
        </div>
        <div className="card-pad" style={{ display: "flex", flexDirection: "column", gap: 12 }}>
          <div className="sub" style={{ fontSize: 13, lineHeight: 1.5 }}>
            SUTRA enforces sovereign governance boundaries on all agent actions regardless of assigned capabilities:
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))", gap: 10, marginTop: 4 }}>
            <div style={{ display: "flex", alignItems: "flex-start", gap: 8, padding: "10px 12px", background: "rgba(255,255,255,0.02)", border: "1px solid var(--line)", borderRadius: 6 }}>
              <I.XCircle size={15} style={{ color: "var(--red)", flexShrink: 0, marginTop: 2 }} />
              <div>
                <div style={{ fontSize: 12, fontWeight: 600 }}>Cannot Approve Own Work</div>
                <div className="meta" style={{ fontSize: 11, marginTop: 2 }}>Agents cannot approve their own pull requests or peer changes.</div>
              </div>
            </div>
            <div style={{ display: "flex", alignItems: "flex-start", gap: 8, padding: "10px 12px", background: "rgba(255,255,255,0.02)", border: "1px solid var(--line)", borderRadius: 6 }}>
              <I.XCircle size={15} style={{ color: "var(--red)", flexShrink: 0, marginTop: 2 }} />
              <div>
                <div style={{ fontSize: 12, fontWeight: 600 }}>Cannot Execute Governed Merges</div>
                <div className="meta" style={{ fontSize: 11, marginTop: 2 }}>Merge execution requires explicit human authorization and passing CI.</div>
              </div>
            </div>
            <div style={{ display: "flex", alignItems: "flex-start", gap: 8, padding: "10px 12px", background: "rgba(255,255,255,0.02)", border: "1px solid var(--line)", borderRadius: 6 }}>
              <I.XCircle size={15} style={{ color: "var(--red)", flexShrink: 0, marginTop: 2 }} />
              <div>
                <div style={{ fontSize: 12, fontWeight: 600 }}>Cannot Bypass Governance</div>
                <div className="meta" style={{ fontSize: 11, marginTop: 2 }}>Changes without verified provenance or failing policy checks are blocked.</div>
              </div>
            </div>
            <div style={{ display: "flex", alignItems: "flex-start", gap: 8, padding: "10px 12px", background: "rgba(255,255,255,0.02)", border: "1px solid var(--line)", borderRadius: 6 }}>
              <I.XCircle size={15} style={{ color: "var(--red)", flexShrink: 0, marginTop: 2 }} />
              <div>
                <div style={{ fontSize: 12, fontWeight: 600 }}>No Human Approval Authority</div>
                <div className="meta" style={{ fontSize: 11, marginTop: 2 }}>Agents connect through supported protocols; human operators retain sovereignty.</div>
              </div>
            </div>
          </div>
        </div>
      </Card>

      <Card style={{ marginTop: 14 }}>
        <div className="card-head">
          <div>
            <div className="h2">Assigned Tasks</div>
            <div className="sub">Engineering tasks assigned to this agent across authorized repositories.</div>
          </div>
          <Badge tone={tasks.filter((t) => t.status === "in_progress").length ? "green" : "neutral"}>
            {tasks.filter((t) => t.status === "in_progress").length} in progress
          </Badge>
        </div>

        {tasks.length === 0 ? (
          <div className="card-pad">
            <div className="sub">No tasks currently assigned to this agent.</div>
          </div>
        ) : (
          <>
            <div className="list">
              {paginatedTasks.map((task) => (
                <div
                  className="list-row"
                  key={task.id}
                  style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}
                >
                  <div style={{ display: "flex", alignItems: "center", gap: 10, flex: 1, minWidth: 0 }}>
                    <I.CheckSquare
                      size={16}
                      style={{
                        color:
                          task.status === "done"
                            ? "var(--green)"
                            : task.status === "in_progress"
                            ? "var(--cyan)"
                            : "var(--muted)",
                      }}
                    />
                    <div style={{ minWidth: 0 }}>
                      <div className="title-sm" style={{ fontWeight: 600 }}>
                        <Link href={`/tasks/${task.id}`} style={{ color: "inherit", textDecoration: "none" }}>
                          {task.title}
                        </Link>
                      </div>
                      <div className="meta">
                        {task.priority && (
                          <span style={{ textTransform: "uppercase", marginRight: 8 }}>
                            {task.priority}
                          </span>
                        )}
                        Created {fmt(task.created_at)}
                      </div>
                    </div>
                  </div>
                  <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                    <Badge
                      tone={
                        task.status === "done"
                          ? "green"
                          : task.status === "in_progress"
                          ? "cyan"
                          : "neutral"
                      }
                    >
                      {task.status.replace("_", " ")}
                    </Badge>
                    {task.status === "in_progress" && (
                      <Btn
                        disabled={terminatingTaskId === task.id}
                        onClick={() => handleTerminateTask(task)}
                        style={{
                          backgroundColor: "rgba(239, 68, 68, 0.15)",
                          color: "#f87171",
                          border: "1px solid rgba(239, 68, 68, 0.3)",
                          padding: "4px 8px",
                          fontSize: 12,
                        }}
                      >
                        {terminatingTaskId === task.id ? "Terminating…" : "Terminate"}
                      </Btn>
                    )}
                  </div>
                </div>
              ))}
            </div>

            {/* Tasks Pagination (10 per page) */}
            {tasks.length > PAGE_SIZE && (
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "space-between",
                  padding: "12px 16px",
                  borderTop: "1px solid var(--line)",
                  background: "rgba(255, 255, 255, 0.015)",
                }}
              >
                <div className="meta" style={{ fontSize: 12 }}>
                  Showing {(tasksPage - 1) * PAGE_SIZE + 1}–{Math.min(tasksPage * PAGE_SIZE, tasks.length)} of {tasks.length} tasks
                </div>
                <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                  <Btn
                    disabled={tasksPage <= 1}
                    onClick={() => setTasksPage((p) => Math.max(1, p - 1))}
                    style={{ padding: "4px 10px", fontSize: 12 }}
                  >
                    Previous
                  </Btn>
                  <span style={{ fontSize: 12, color: "var(--muted)", minWidth: 48, textAlign: "center" }}>
                    {tasksPage} / {totalTaskPages}
                  </span>
                  <Btn
                    disabled={tasksPage >= totalTaskPages}
                    onClick={() => setTasksPage((p) => Math.min(totalTaskPages, p + 1))}
                    style={{ padding: "4px 10px", fontSize: 12 }}
                  >
                    Next
                  </Btn>
                </div>
              </div>
            )}
          </>
        )}
      </Card>
      {confirmConfig && (
        <ConfirmModal
          isOpen={confirmConfig.isOpen}
          onClose={() => setConfirmConfig(null)}
          onConfirm={confirmConfig.onConfirm}
          title={confirmConfig.title}
          description={confirmConfig.description}
          confirmText={confirmConfig.confirmText}
          confirmTone={confirmConfig.confirmTone}
          loading={revokingAgent || Boolean(terminatingTaskId)}
        />
      )}
    </>
  );
}
