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
} from "@/components/shell";

import {
  agentService,
  type Agent,
  type AgentSession,
} from "@/lib/agents";

import { taskService } from "@/lib/tasks";
import { authService } from "@/lib/auth";
import { ConfirmModal } from "@/components/ConfirmModal";

import * as I from "lucide-react";

type TaskRow = {
  id: string;
  title: string;
  description?: string | null;
  status: string;
  priority?: string | null;
  created_at?: string;
  updated_at?: string;
  started_at?: string | null;
  completed_at?: string | null;
  assigned_agent_id?: string | null;
};

function timeAgo(dateStr?: string | null) {
  if (!dateStr) {
    return "—";
  }

  const timestamp =
    new Date(dateStr).getTime();

  if (!Number.isFinite(timestamp)) {
    return "—";
  }

  const diff =
    Date.now() - timestamp;

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

function taskStatusColor(
  status: string,
) {
  switch (status) {
    case "completed":
      return "var(--green)";

    case "in_progress":
      return "var(--cyan)";

    case "failed":
      return "var(--red)";

    case "cancelled":
      return "var(--muted)";

    case "blocked":
      return "var(--amber)";

    default:
      return "var(--muted)";
  }
}

function taskStatusIcon(
  status: string,
) {
  switch (status) {
    case "completed":
      return <I.CheckCircle2 size={15} />;

    case "in_progress":
      return <I.Loader size={15} />;

    case "failed":
      return <I.XCircle size={15} />;

    case "cancelled":
      return <I.MinusCircle size={15} />;

    case "blocked":
      return <I.CircleAlert size={15} />;

    default:
      return <I.Circle size={15} />;
  }
}

function humanStatus(status: string) {
  return status
    .replaceAll("_", " ")
    .replace(/\b\w/g, (char) =>
      char.toUpperCase(),
    );
}

export default function AgentDetailPage({
  params,
}: {
  params: Promise<{
    name: string;
    id: string;
  }>;
}) {
  const {
    name: repoName,
    id: agentId,
  } = use(params);

  const router = useRouter();

  const [agent, setAgent] =
    useState<Agent | null>(null);

  const [agentTasks, setAgentTasks] =
    useState<TaskRow[]>([]);

  const [sessions, setSessions] =
    useState<AgentSession[]>([]);

  const [loading, setLoading] =
    useState(true);

  const [error, setError] =
    useState<string | null>(null);

  const [revoking, setRevoking] =
    useState(false);

  const [activeTab, setActiveTab] =
    useState<
      "Overview" | "Tasks" | "Sessions" | "Configuration"
    >("Overview");

  const [
    isRevokeModalOpen,
    setIsRevokeModalOpen,
  ] = useState(false);

  const [terminatingTaskId, setTerminatingTaskId] = useState<string | null>(null);
  const [taskToTerminate, setTaskToTerminate] = useState<TaskRow | null>(null);

  const load = async () => {
    try {
      setLoading(true);
      setError(null);

      const user =
        await authService.getCurrentUser();

      const [
        fetchedAgent,
        taskList,
        sessionList,
      ] = await Promise.all([
        agentService.getAgent(agentId).catch(() => null),

        taskService
          .listTasks(
            user.username,
            repoName,
          )
          .catch(() => []),

        agentService
          .listSessions(agentId)
          .catch(() => []),
      ]);

      if (!fetchedAgent) {
        setAgent(null);
        setAgentTasks([]);
        setSessions([]);
        return;
      }

      setAgent(fetchedAgent);

      setAgentTasks(
        (taskList || []).filter(
          (task: TaskRow) =>
            task.assigned_agent_id ===
            agentId,
        ),
      );

      setSessions(
        (sessionList || []).sort(
          (a, b) =>
            new Date(
              b.last_seen_at ||
                b.created_at,
            ).getTime() -
            new Date(
              a.last_seen_at ||
                a.created_at,
            ).getTime(),
        ),
      );
    } catch (err: any) {
      console.error(
        "Failed to load agent",
        err,
      );

      setError(
        err?.detail ||
          err?.message ||
          "Failed to load agent.",
      );
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void load();
  }, [agentId, repoName]);

  const handleRevoke = async () => {
    if (!agent) {
      return;
    }

    try {
      setRevoking(true);

      await agentService.revokeAgent(
        agent.id,
      );

      router.push(
        `/repositories/${encodeURIComponent(
          repoName,
        )}/agents`,
      );
    } catch (err: any) {
      setError(
        err?.detail ||
          err?.message ||
          "Failed to revoke agent.",
      );

      setRevoking(false);
      setIsRevokeModalOpen(false);
    }
  };

  const handleTerminateTask = (task: TaskRow) => {
    setTaskToTerminate(task);
  };

  const executeTerminateTask = async () => {
    if (!taskToTerminate) return;
    const taskId = taskToTerminate.id;
    setTerminatingTaskId(taskId);
    try {
      await taskService.terminateTask(taskId);
      setAgentTasks((prev) =>
        prev.map((t) => (t.id === taskId ? { ...t, status: "cancelled" } : t))
      );
      setTaskToTerminate(null);
    } catch (err: any) {
      alert(err?.message || "Failed to terminate task");
    } finally {
      setTerminatingTaskId(null);
    }
  };

  const runningTask =
    agentTasks.find(
      (task) =>
        task.status ===
        "in_progress",
    );

  const completedCount =
    agentTasks.filter(
      (task) =>
        task.status ===
        "completed",
    ).length;

  const failedCount =
    agentTasks.filter(
      (task) =>
        task.status ===
        "failed",
    ).length;

  const terminalTaskCount =
    completedCount +
    failedCount;

  const successRate =
    terminalTaskCount > 0
      ? Math.round(
          (completedCount /
            terminalTaskCount) *
            100,
        )
      : null;

  const activeSessions =
    sessions.filter(
      (session) =>
        session.status ===
        "active" &&
        !session.revoked_at,
    );

  const latestSession =
    sessions[0] || null;

  const latestSeen =
    latestSession?.last_seen_at ||
    null;

  const agentIsActive =
    Boolean(
      agent &&
        agent.is_active &&
        agent.status ===
          "active",
    );

  const connected =
    agentIsActive &&
    activeSessions.length >
      0;

  const connectionLabel =
    connected
      ? runningTask
        ? "Running"
        : "Connected"
      : agentIsActive
        ? "Active / no session"
        : humanStatus(
            agent?.status ||
              "inactive",
          );

  const statusColor =
    connected
      ? runningTask
        ? "var(--green)"
        : "var(--cyan)"
      : agentIsActive
        ? "var(--amber)"
        : "var(--muted)";

  const tabs = [
    "Overview",
    "Tasks",
    "Sessions",
    "Configuration",
  ] as const;

  const taskSummary = useMemo(() => {
    const counts: Record<
      string,
      number
    > = {};

    for (const task of agentTasks) {
      counts[task.status] =
        (counts[task.status] || 0) + 1;
    }

    return counts;
  }, [agentTasks]);

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
          Loading agent…
        </div>
      </AppShell>
    );
  }

  if (!agent) {
    return (
      <AppShell>
        <div
          style={{
            padding: 48,
            maxWidth: 460,
            margin: "60px auto",
            textAlign: "center",
            background:
              "var(--bg-subtle)",
            borderRadius: 12,
            border:
              "1px solid var(--line)",
          }}
        >
          <I.Bot
            size={32}
            style={{
              marginBottom: 12,
              opacity: 0.3,
            }}
          />

          <div
            style={{
              fontSize: 17,
              fontWeight: 600,
              color: "var(--fg)",
              marginBottom: 8,
            }}
          >
            Agent not found
          </div>

          <div
            className="sub"
            style={{
              marginBottom: 18,
            }}
          >
            {error ||
              "The agent does not exist or you do not have access to it."}
          </div>

          <Btn
            onClick={() =>
              router.back()
            }
          >
            Go Back
          </Btn>
        </div>
      </AppShell>
    );
  }

  return (
    <AppShell>
      <PageHead
        eyebrow={`Agents / ${repoName}`}
        title={agent.name}
        sub={
          agent.description ||
          (agent.provider
            ? `${agent.provider}${
                agent.model
                  ? ` / ${agent.model}`
                  : ""
              }`
            : "Autonomous engineering agent")
        }
        action={
          agentIsActive ? (
            <Btn
              onClick={() =>
                setIsRevokeModalOpen(
                  true,
                )
              }
              disabled={revoking}
              style={{
                color: "var(--red)",
                borderColor:
                  "rgba(239,68,68,.3)",
              }}
            >
              {revoking
                ? "Revoking…"
                : "Revoke Agent"}
            </Btn>
          ) : null
        }
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
                  color: "var(--red)",
                }}
              >
                {error}
              </div>
            </div>
          </Card>
        )}

        {/* Real connection status */}
        <Card
          style={{
            marginBottom: 20,
          }}
        >
          <div
            className="card-pad"
            style={{
              display: "flex",
              alignItems: "center",
              gap: 12,
            }}
          >
            <div
              style={{
                width: 10,
                height: 10,
                borderRadius:
                  "50%",
                background:
                  statusColor,
                boxShadow:
                  connected
                    ? `0 0 12px ${statusColor}`
                    : "none",
                flexShrink: 0,
              }}
            />

            <div>
              <div
                style={{
                  fontSize: 13,
                  fontWeight: 700,
                  color:
                    statusColor,
                }}
              >
                {connectionLabel}
              </div>

              <div
                className="meta"
                style={{
                  marginTop: 3,
                }}
              >
                {latestSeen
                  ? `Last seen ${timeAgo(
                      latestSeen,
                    )}`
                  : "No agent session has been recorded"}
              </div>
            </div>

            <div
              style={{
                marginLeft: "auto",
                fontFamily:
                  "monospace",
                fontSize: 12,
                color:
                  "var(--muted)",
              }}
            >
              {agent.id}
            </div>
          </div>
        </Card>

        {/* Real metrics */}
        <div
          style={{
            display: "grid",
            gridTemplateColumns:
              "repeat(3,minmax(0,1fr))",
            gap: 12,
            marginBottom: 24,
          }}
        >
          <MetricCard
            label="Assigned Tasks"
            value={
              agentTasks.length
            }
            icon={
              <I.ListTodo
                size={16}
              />
            }
          />

          <MetricCard
            label="Completed"
            value={
              completedCount
            }
            icon={
              <I.CheckCircle2
                size={16}
              />
            }
          />

          <MetricCard
            label="Success Rate"
            value={
              successRate === null
                ? "—"
                : `${successRate}%`
            }
            icon={
              <I.TrendingUp
                size={16}
              />
            }
          />
        </div>

        {/* Tabs */}
        <div
          style={{
            display: "flex",
            borderBottom:
              "1px solid var(--line)",
            marginBottom: 24,
            overflowX: "auto",
          }}
        >
          {tabs.map((tab) => (
            <button
              key={tab}
              type="button"
              onClick={() =>
                setActiveTab(tab)
              }
              style={{
                padding:
                  "10px 18px",
                background:
                  "transparent",
                border: "none",
                borderBottom:
                  activeTab === tab
                    ? "2px solid var(--cyan)"
                    : "2px solid transparent",
                color:
                  activeTab === tab
                    ? "var(--fg)"
                    : "var(--muted)",
                fontWeight:
                  activeTab === tab
                    ? 600
                    : 400,
                cursor: "pointer",
                fontSize: 14,
                whiteSpace:
                  "nowrap",
              }}
            >
              {tab}
            </button>
          ))}
        </div>

        {/* Overview */}
        {activeTab ===
          "Overview" && (
          <div
            style={{
              display: "flex",
              flexDirection:
                "column",
              gap: 16,
            }}
          >
            {runningTask ? (
              <Card>
                <div className="card-head">
                  <div>
                    <div
                      className="eyebrow"
                      style={{
                        color:
                          "var(--green)",
                      }}
                    >
                      Current task
                    </div>

                    <div
                      className="h2"
                      style={{
                        marginTop: 5,
                      }}
                    >
                      {runningTask.title}
                    </div>

                    {runningTask.description && (
                      <div
                        className="sub"
                        style={{
                          marginTop: 5,
                        }}
                      >
                        {
                          runningTask.description
                        }
                      </div>
                    )}
                  </div>

                  <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                    <Badge tone="green">
                      In Progress
                    </Badge>
                    <button
                      type="button"
                      onClick={() => handleTerminateTask(runningTask)}
                      disabled={terminatingTaskId === runningTask.id}
                      className="badge red"
                      style={{
                        cursor: "pointer",
                        display: "inline-flex",
                        alignItems: "center",
                        gap: 4,
                        padding: "4px 10px",
                        fontSize: "11px",
                        background: "rgba(239,68,68,0.12)",
                        border: "1px solid rgba(239,68,68,0.3)",
                        color: "#ef4444",
                        fontWeight: 600,
                        borderRadius: 4,
                      }}
                      title="Terminate active task"
                    >
                      <I.Square size={10} fill="currentColor" /> {terminatingTaskId === runningTask.id ? "Terminating…" : "Terminate"}
                    </button>
                  </div>
                </div>

                <div
                  className="card-pad"
                  style={{
                    display: "grid",
                    gridTemplateColumns:
                      "repeat(3,minmax(0,1fr))",
                    gap: 16,
                  }}
                >
                  <InfoRow
                    label="Priority"
                    value={
                      runningTask.priority ||
                      "—"
                    }
                  />

                  <InfoRow
                    label="Started"
                    value={
                      runningTask.started_at
                        ? new Date(
                            runningTask.started_at,
                          ).toLocaleString()
                        : "—"
                    }
                  />

                  <InfoRow
                    label="Updated"
                    value={
                      timeAgo(
                        runningTask.updated_at,
                      )
                    }
                  />
                </div>
              </Card>
            ) : (
              <Card>
                <div className="card-pad">
                  <div
                    style={{
                      display: "flex",
                      alignItems:
                        "center",
                      gap: 10,
                    }}
                  >
                    <I.PauseCircle
                      size={18}
                      className="muted"
                    />

                    <div>
                      <div className="title-sm">
                        No task is currently
                        running
                      </div>

                      <div
                        className="sub"
                        style={{
                          marginTop: 3,
                        }}
                      >
                        The agent is{" "}
                        {connected
                          ? "connected and idle"
                          : "not currently connected"}.
                      </div>
                    </div>
                  </div>
                </div>
              </Card>
            )}

            <div
              style={{
                display: "grid",
                gridTemplateColumns:
                  "1.2fr .8fr",
                gap: 16,
              }}
            >
              <Card>
                <div className="card-head">
                  <div>
                    <div className="h2">
                      Task status
                    </div>

                    <div className="sub">
                      Live counts from tasks
                      assigned to this agent.
                    </div>
                  </div>
                </div>

                <div className="card-pad">
                  {Object.keys(
                    taskSummary,
                  ).length === 0 ? (
                    <div className="sub">
                      No tasks assigned yet.
                    </div>
                  ) : (
                    <div
                      style={{
                        display:
                          "flex",
                        flexDirection:
                          "column",
                        gap: 10,
                      }}
                    >
                      {Object.entries(
                        taskSummary,
                      ).map(
                        ([
                          status,
                          count,
                        ]) => (
                          <div
                            key={status}
                            style={{
                              display:
                                "flex",
                              alignItems:
                                "center",
                              justifyContent:
                                "space-between",
                            }}
                          >
                            <div
                              style={{
                                display:
                                  "flex",
                                alignItems:
                                  "center",
                                gap: 8,
                                color:
                                  taskStatusColor(
                                    status,
                                  ),
                              }}
                            >
                              {taskStatusIcon(
                                status,
                              )}

                              <span
                                style={{
                                  color:
                                    "var(--fg)",
                                  fontSize: 13,
                                }}
                              >
                                {humanStatus(
                                  status,
                                )}
                              </span>
                            </div>

                            <span className="meta">
                              {
                                count
                              }
                            </span>
                          </div>
                        ),
                      )}
                    </div>
                  )}
                </div>
              </Card>

              <Card>
                <div className="card-head">
                  <div>
                    <div className="h2">
                      Connection
                    </div>

                    <div className="sub">
                      Real agent sessions.
                    </div>
                  </div>
                </div>

                <div className="card-pad">
                  <InfoRow
                    label="Active sessions"
                    value={
                      activeSessions.length
                    }
                  />

                  <InfoRow
                    label="Latest session"
                    value={
                      latestSession
                        ? timeAgo(
                            latestSession.last_seen_at,
                          )
                        : "—"
                    }
                  />

                  <InfoRow
                    label="Session status"
                    value={
                      latestSession
                        ?.status ||
                      "No session"
                    }
                  />
                </div>
              </Card>
            </div>
          </div>
        )}

        {/* Tasks */}
        {activeTab ===
          "Tasks" && (
          <Card>
            <div className="card-head">
              <div>
                <div className="h2">
                  Assigned tasks
                </div>

                <div className="sub">
                  Tasks actually assigned to this
                  agent.
                </div>
              </div>

              <Badge>
                {agentTasks.length}
              </Badge>
            </div>

            {agentTasks.length === 0 ? (
              <div
                className="card-pad"
                style={{
                  textAlign: "center",
                  paddingTop: 50,
                  paddingBottom: 50,
                }}
              >
                <I.ListTodo
                  size={26}
                  style={{
                    opacity: 0.35,
                    marginBottom: 10,
                  }}
                />

                <div className="h2">
                  No assigned tasks
                </div>

                <div className="sub">
                  Tasks assigned to this agent
                  will appear here.
                </div>
              </div>
            ) : (
              <div className="list">
                {agentTasks.map(
                  (task) => (
                    <div
                      key={task.id}
                      className="list-row"
                      style={{
                        alignItems:
                          "flex-start",
                      }}
                    >
                      <div
                        style={{
                          color:
                            taskStatusColor(
                              task.status,
                            ),
                          paddingTop: 2,
                        }}
                      >
                        {taskStatusIcon(
                          task.status,
                        )}
                      </div>

                      <div
                        style={{
                          flex: 1,
                          minWidth: 0,
                        }}
                      >
                        <div className="title-sm">
                          {task.title}
                        </div>

                        {task.description && (
                          <div
                            className="sub"
                            style={{
                              marginTop: 4,
                            }}
                          >
                            {task.description}
                          </div>
                        )}

                        <div
                          className="meta"
                          style={{
                            marginTop: 6,
                          }}
                        >
                          {task.created_at
                            ? `Created ${timeAgo(
                                task.created_at,
                              )}`
                            : `Updated ${timeAgo(
                                task.updated_at,
                              )}`}
                        </div>
                      </div>

                      {task.priority && (
                        <Badge>
                          {task.priority}
                        </Badge>
                      )}

                      <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                        <Badge
                          tone={
                            task.status === "completed"
                              ? "green"
                              : task.status === "failed" || task.status === "cancelled"
                                ? "red"
                                : task.status === "in_progress"
                                  ? "aqua"
                                  : "amber"
                          }
                        >
                          {humanStatus(task.status)}
                        </Badge>
                        {(task.status === "in_progress" || task.status === "assigned" || task.status === "open") && (
                          <button
                            type="button"
                            onClick={() => handleTerminateTask(task)}
                            disabled={terminatingTaskId === task.id}
                            className="badge red"
                            style={{
                              cursor: "pointer",
                              padding: "2px 8px",
                              fontSize: "10px",
                              background: "rgba(239,68,68,0.12)",
                              border: "1px solid rgba(239,68,68,0.3)",
                              color: "#ef4444",
                              fontWeight: 600,
                              borderRadius: 4,
                            }}
                            title="Terminate task"
                          >
                            Terminate
                          </button>
                        )}
                      </div>
                    </div>
                  ),
                )}
              </div>
            )}
          </Card>
        )}

        {/* Sessions */}
        {activeTab ===
          "Sessions" && (
          <Card>
            <div className="card-head">
              <div>
                <div className="h2">
                  Agent sessions
                </div>

                <div className="sub">
                  Connection records reported by the
                  agent.
                </div>
              </div>

              <Badge>
                {sessions.length}
              </Badge>
            </div>

            {sessions.length === 0 ? (
              <div
                className="card-pad"
                style={{
                  textAlign: "center",
                  paddingTop: 50,
                  paddingBottom: 50,
                }}
              >
                <I.PlugZap
                  size={26}
                  style={{
                    opacity: 0.35,
                    marginBottom: 10,
                  }}
                />

                <div className="h2">
                  No sessions
                </div>

                <div className="sub">
                  This agent has not established
                  a session yet.
                </div>
              </div>
            ) : (
              <div className="list">
                {sessions.map(
                  (session) => {
                    const sessionActive =
                      session.status ===
                        "active" &&
                      !session.revoked_at;

                    return (
                      <div
                        key={
                          session.session_id
                        }
                        className="list-row"
                      >
                        <div
                          style={{
                            width: 9,
                            height: 9,
                            borderRadius:
                              "50%",
                            background:
                              sessionActive
                                ? "var(--green)"
                                : "var(--muted)",
                            flexShrink: 0,
                          }}
                        />

                        <div
                          style={{
                            flex: 1,
                            minWidth: 0,
                          }}
                        >
                          <div
                            className="title-sm"
                            style={{
                              fontFamily:
                                "monospace",
                            }}
                          >
                            {
                              session.session_id
                            }
                          </div>

                          <div
                            className="meta"
                            style={{
                              marginTop: 4,
                            }}
                          >
                            Last seen{" "}
                            {timeAgo(
                              session.last_seen_at,
                            )}{" "}
                            · Created{" "}
                            {timeAgo(
                              session.created_at,
                            )}
                          </div>
                        </div>

                        <Badge
                          tone={
                            sessionActive
                              ? "green"
                              : undefined
                          }
                        >
                          {sessionActive
                            ? "Active"
                            : session.revoked_at
                              ? "Revoked"
                              : session.status}
                        </Badge>
                      </div>
                    );
                  },
                )}
              </div>
            )}
          </Card>
        )}

        {/* Configuration */}
        {activeTab ===
          "Configuration" && (
          <div
            style={{
              display: "flex",
              flexDirection:
                "column",
              gap: 16,
            }}
          >
            <Card>
              <div className="card-head">
                <div>
                  <div className="h2">
                    Agent configuration
                  </div>

                  <div className="sub">
                    Values stored for this agent.
                  </div>
                </div>
              </div>

              <div className="card-pad">
                <InfoRow
                  label="Agent ID"
                  value={agent.id}
                  mono
                />

                <InfoRow
                  label="Provider"
                  value={
                    agent.provider ||
                    "—"
                  }
                  mono
                />

                <InfoRow
                  label="Model"
                  value={
                    agent.model ||
                    "—"
                  }
                  mono
                />

                <InfoRow
                  label="Token prefix"
                  value={
                    agent.token_prefix ||
                    "—"
                  }
                  mono
                />

                <InfoRow
                  label="Status"
                  value={
                    humanStatus(
                      agent.status,
                    )
                  }
                />

                <InfoRow
                  label="Active"
                  value={
                    agent.is_active
                      ? "Yes"
                      : "No"
                  }
                />
              </div>
            </Card>

            <Card>
              <div className="card-pad">
                <div
                  style={{
                    display:
                      "flex",
                    gap: 10,
                    alignItems:
                      "flex-start",
                  }}
                >
                  <I.ShieldCheck
                    size={18}
                    style={{
                      color:
                        "var(--cyan)",
                      marginTop: 1,
                    }}
                  />

                  <div>
                    <div className="title-sm">
                      Capabilities
                    </div>

                    <div
                      className="sub"
                      style={{
                        marginTop: 4,
                      }}
                    >
                      Capability data is not included
                      in the current Agent API response,
                      so SUTRA does not display fabricated
                      capabilities here.
                    </div>
                  </div>
                </div>
              </div>
            </Card>
          </div>
        )}
      </div>

      {isRevokeModalOpen && (
        <div
          style={{
            position: "fixed",
            inset: 0,
            background:
              "rgba(0,0,0,.6)",
            backdropFilter:
              "blur(4px)",
            zIndex: 200,
            display: "flex",
            alignItems: "center",
            justifyContent:
              "center",
            padding: 20,
          }}
        >
          <Card
            style={{
              width: 440,
              maxWidth: "100%",
            }}
          >
            <div className="card-pad">
              <div
                style={{
                  display:
                    "flex",
                  gap: 14,
                  alignItems:
                    "flex-start",
                }}
              >
                <div
                  style={{
                    background:
                      "rgba(239,68,68,.1)",
                    border:
                      "1px solid rgba(239,68,68,.2)",
                    color:
                      "var(--red)",
                    padding: 10,
                    borderRadius: 10,
                  }}
                >
                  <I.AlertTriangle
                    size={22}
                  />
                </div>

                <div
                  style={{
                    flex: 1,
                  }}
                >
                  <div
                    className="h2"
                    style={{
                      marginBottom: 4,
                    }}
                  >
                    Revoke Agent
                  </div>

                  <div className="sub">
                    Are you sure you want to revoke{" "}
                    <strong>
                      {agent.name}
                    </strong>
                    ? This removes the agent's
                    active access.
                  </div>
                </div>
              </div>

              <div
                className="actions"
                style={{
                  justifyContent:
                    "flex-end",
                  marginTop: 20,
                }}
              >
                <Btn
                  onClick={() =>
                    setIsRevokeModalOpen(
                      false,
                    )
                  }
                  disabled={revoking}
                >
                  Cancel
                </Btn>

                <Btn
                  primary
                  onClick={
                    handleRevoke
                  }
                  disabled={revoking}
                  style={{
                    background:
                      "var(--red)",
                    borderColor:
                      "var(--red)",
                  }}
                >
                  {revoking
                    ? "Revoking..."
                    : "Revoke Agent"}
                </Btn>
              </div>
            </div>
          </Card>
        </div>
      )}

      <ConfirmModal
        isOpen={Boolean(taskToTerminate)}
        onClose={() => setTaskToTerminate(null)}
        onConfirm={executeTerminateTask}
        title="Terminate Active Task"
        description={
          <>
            Are you sure you want to terminate <strong>&ldquo;{taskToTerminate?.title}&rdquo;</strong>? Active execution will be aborted immediately and the task status will be marked as cancelled.
          </>
        }
        confirmText="Terminate Task"
        confirmTone="danger"
        loading={Boolean(terminatingTaskId)}
      />
    </AppShell>
  );
}

function MetricCard({
  label,
  value,
  icon,
}: {
  label: string;
  value: string | number;
  icon: React.ReactNode;
}) {
  return (
    <Card
      style={{
        padding:
          "16px 20px",
        display: "flex",
        alignItems:
          "center",
        gap: 12,
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
          color:
            "var(--cyan)",
          flexShrink: 0,
        }}
      >
        {icon}
      </div>

      <div>
        <div
          style={{
            fontSize: 20,
            fontWeight: 700,
            color: "var(--fg)",
          }}
        >
          {value}
        </div>

        <div
          style={{
            fontSize: 12,
            color: "var(--muted)",
          }}
        >
          {label}
        </div>
      </div>
    </Card>
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
        display: "flex",
        justifyContent:
          "space-between",
        alignItems:
          "center",
        gap: 20,
        padding:
          "11px 0",
        borderBottom:
          "1px solid var(--line)",
      }}
    >
      <span
        className="meta"
        style={{
          flexShrink: 0,
        }}
      >
        {label}
      </span>

      <span
        style={{
          fontSize: 13,
          color: "var(--fg)",
          fontFamily: mono
            ? "monospace"
            : "inherit",
          textAlign: "right",
          wordBreak:
            "break-all",
        }}
      >
        {value}
      </span>
    </div>
  );
}