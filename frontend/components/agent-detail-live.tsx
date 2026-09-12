"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { useParams } from "next/navigation";
import { agentService, type Agent, type AgentSession, type AgentRepositoryAccess } from "../lib/agents";
import { Badge, Btn, Card, PageHead, Stat } from "./shell";
import { I } from "../lib/icons";
import { repositoryService, type Repository } from "../lib/repositories";

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

  const load = async () => {
    if (!agentId) return;
    try {
      setLoading(true);
      setError(null);
      const agents = await agentService.listAgents();
      const current = agents.find((item) => item.id === agentId);
      if (!current) {
        setError("Agent not found.");
        return;
      }
      setAgent(current);
      
      const [sess, access, repos] = await Promise.all([
        agentService.listSessions(current.id),
        agentService.listRepositoryAccess(current.id),
        repositoryService.listRepositories().catch(() => [] as Repository[]),
      ]);
      
      setSessions(sess);
      setAccessList(access);
      setAllRepos(repos);
    } catch (err: any) {
      console.error(err);
      setError(err?.detail || err?.message || "Failed to load agent.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void load();
  }, [agentId]);

  const activeSessions = useMemo(
    () => sessions.filter((session) => session.status === "active"),
    [sessions],
  );

  const handleRevoke = async (sessionId: string) => {
    try {
      setRevoking(sessionId);
      await agentService.revokeSession(sessionId);
      await load();
    } catch (err: any) {
      setError(err?.detail || err?.message || "Failed to revoke session.");
    } finally {
      setRevoking(null);
    }
  };

  const handleRevokeAgent = async () => {
    if (!agent) return;
    if (!confirm("Are you sure you want to revoke this agent? This will deactivate the agent and invalidate all active sessions.")) return;
    try {
      setRevokingAgent(true);
      await agentService.revokeAgent(agent.id);
      await load();
    } catch (err: any) {
      setError(err?.detail || err?.message || "Failed to revoke agent.");
    } finally {
      setRevokingAgent(false);
    }
  };

  const togglePermission = async (access: AgentRepositoryAccess, permission: string) => {
    if (!agent) return;
    const permissions = access.permissions.includes(permission)
      ? access.permissions.filter(p => p !== permission)
      : [...access.permissions, permission];
    try {
      await agentService.updateRepositoryAccess(agent.id, access.repository_id, permissions, access.enabled);
      await load();
    } catch (err: any) {
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
      await load();
    } catch (err: any) {
      setError(err?.detail || err?.message || "Failed to grant repository access.");
    } finally {
      setGranting(false);
    }
  };

  const handleRevokeAccess = async (repositoryId: string) => {
    if (!agent) return;
    if (!confirm("Revoke this repository access grant?")) return;
    try {
      await agentService.revokeRepositoryAccess(agent.id, repositoryId);
      await load();
    } catch (err: any) {
      setError(err?.detail || err?.message || "Failed to revoke repository access.");
    }
  };

  if (loading) {
    return <div className="muted" style={{ padding: 40 }}>Loading agent…</div>;
  }

  if (error || !agent) {
    return <div className="muted" style={{ padding: 40, color: "#ff8fa0" }}>{error || "Agent not found."}</div>;
  }

  return (
    <>
      <PageHead
        eyebrow={`Agent · ${agent.name}`}
        title={agent.name}
        sub={agent.description || agent.model || "Registered SUTRA agent"}
        action={
          <div style={{ display: "flex", gap: 8 }}>
            <Btn onClick={() => void load()}>
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
        <Stat label="Provider" value={agent.provider || "—"} />
        <Stat label="Model" value={agent.model || "—"} />
        <Stat label="Active sessions" value={String(activeSessions.length)} />
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
          <div className="list">
            {sessions.map((session) => (
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
                "knowledge_graph.read",
                "knowledge_graph.write"
              ];
              return (
                <div key={access.repository_id} style={{ display: "flex", flexDirection: "column", padding: "16px", borderBottom: "1px solid var(--line)" }}>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
                    <div>
                      <div className="title-sm" style={{ fontSize: 15, fontWeight: 600 }}>
                        {access.repository_owner} / {access.repository_name}
                      </div>
                      <div className="meta">Repository ID: {access.repository_id}</div>
                    </div>
                    <Btn
                      style={{ backgroundColor: "var(--red, #ff4d4f)", color: "#fff", padding: "4px 8px", fontSize: 12 }}
                      onClick={() => void handleRevokeAccess(access.repository_id)}
                    >
                      Revoke Repo
                    </Btn>
                  </div>
                  <div className="field">
                    <label className="label" style={{ fontSize: 11, textTransform: "uppercase", letterSpacing: "0.05em", color: "var(--muted)", marginBottom: 8 }}>
                      Allowed capabilities (toggles)
                    </label>
                    <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
                      {capabilitiesList.map((perm) => {
                        const active = access.permissions.includes(perm);
                        return (
                          <button
                            key={perm}
                            onClick={() => void togglePermission(access, perm)}
                            style={{
                              padding: "6px 12px",
                              borderRadius: "16px",
                              fontSize: "12px",
                              fontWeight: 500,
                              cursor: "pointer",
                              border: "1px solid",
                              transition: "all 0.2s ease",
                              backgroundColor: active ? "rgba(99, 102, 241, 0.15)" : "transparent",
                              borderColor: active ? "#6366f1" : "var(--line)",
                              color: active ? "#818cf8" : "var(--muted)"
                            }}
                          >
                            {perm} {active ? "✓" : ""}
                          </button>
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
        <div className="card-pad">
          <div className="eyebrow">Execution history</div>
          <div className="h2">Not exposed by the current backend</div>
          <div className="sub" style={{ marginTop: 8 }}>
            Agent sessions are now real. Task execution traces still require a task-event/run-history aggregation before this view can honestly show past runs.
          </div>
          <div style={{ marginTop: 16 }}>
            <Link href={`/agents/${agent.id}`} className="badge aqua">Refresh agent</Link>
          </div>
        </div>
      </Card>
    </>
  );
}
