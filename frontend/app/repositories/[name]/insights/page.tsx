"use client";

import {
  use,
  useCallback,
  useEffect,
  useState,
} from "react";

import {
  AppShell,
} from "@/components/shell";

import {
  apiAuth,
} from "@/lib/api";

import {
  authService,
} from "@/lib/auth";

import * as I from "lucide-react";

interface InsightsData {
  deployments_per_week: number;
  lead_time_minutes: number;
  ci_pass_rate: number;
  agent_changes_percent: number;
  human_changes_percent: number;
  agent_lead_time_minutes: number;
  human_lead_time_minutes: number;
  actionable_signal: string;
  actionable_signal_details: string;
}

function formatMinutes(
  minutes: number,
) {
  if (!Number.isFinite(minutes)) {
    return "—";
  }

  const total = Math.max(
    0,
    Math.round(minutes),
  );

  const hours = Math.floor(
    total / 60,
  );

  const mins = total % 60;

  if (hours === 0) {
    return `${mins}m`;
  }

  return `${hours}h ${mins}m`;
}

function clampPercent(
  value: number,
) {
  if (!Number.isFinite(value)) {
    return 0;
  }

  return Math.max(
    0,
    Math.min(100, value),
  );
}

function MetricCard({
  icon,
  label,
  value,
  unit,
  description,
}: {
  icon: React.ReactNode;
  label: string;
  value: string | number;
  unit?: string;
  description?: string;
}) {
  return (
    <div
      style={{
        background:
          "rgba(255,255,255,0.03)",
        border:
          "1px solid rgba(255,255,255,0.08)",
        borderRadius: 16,
        padding: 20,
        transition:
          "transform .15s, border-color .15s",
      }}
      onMouseEnter={(event) => {
        event.currentTarget.style.borderColor =
          "rgba(255,255,255,0.15)";
        event.currentTarget.style.transform =
          "translateY(-2px)";
      }}
      onMouseLeave={(event) => {
        event.currentTarget.style.borderColor =
          "rgba(255,255,255,0.08)";
        event.currentTarget.style.transform =
          "translateY(0)";
      }}
    >
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent:
            "space-between",
          marginBottom: 14,
        }}
      >
        <span
          style={{
            fontSize: 12,
            color:
              "var(--muted)",
            fontWeight: 600,
            textTransform:
              "uppercase",
            letterSpacing:
              "0.05em",
          }}
        >
          {label}
        </span>

        <div
          style={{
            opacity: 0.7,
          }}
        >
          {icon}
        </div>
      </div>

      <div
        style={{
          fontSize: 28,
          fontWeight: 800,
          color: "var(--fg)",
          lineHeight: 1,
        }}
      >
        {value}

        {unit && (
          <span
            style={{
              fontSize: 14,
              fontWeight: 400,
              color:
                "var(--muted)",
              marginLeft: 4,
            }}
          >
            {unit}
          </span>
        )}
      </div>

      {description && (
        <div
          style={{
            fontSize: 12,
            color:
              "var(--muted)",
            marginTop: 8,
          }}
        >
          {description}
        </div>
      )}
    </div>
  );
}

function ProgressBar({
  label,
  value,
  color,
}: {
  label: string;
  value: number;
  color: string;
}) {
  const percentage =
    clampPercent(value);

  return (
    <div
      style={{
        marginBottom: 20,
      }}
    >
      <div
        style={{
          display: "flex",
          justifyContent:
            "space-between",
          alignItems: "center",
          marginBottom: 7,
        }}
      >
        <span
          style={{
            fontSize: 13,
            color:
              "var(--muted)",
          }}
        >
          {label}
        </span>

        <span
          style={{
            fontSize: 13,
            fontWeight: 700,
            color:
              "var(--fg)",
          }}
        >
          {percentage.toFixed(1)}%
        </span>
      </div>

      <div
        style={{
          height: 6,
          background:
            "rgba(255,255,255,0.08)",
          borderRadius: 4,
          overflow: "hidden",
        }}
      >
        <div
          style={{
            height: "100%",
            width: `${percentage}%`,
            background: color,
            borderRadius: 4,
            transition:
              "width .4s ease",
          }}
        />
      </div>
    </div>
  );
}

function AgentHumanBreakdown({
  agentPct,
  humanPct,
}: {
  agentPct: number;
  humanPct: number;
}) {
  const safeAgent =
    clampPercent(agentPct);

  const safeHuman =
    clampPercent(humanPct);

  const total =
    safeAgent + safeHuman;

  const normalizedAgent =
    total > 0
      ? (safeAgent / total) * 100
      : 0;

  const normalizedHuman =
    total > 0
      ? (safeHuman / total) * 100
      : 0;

  const radius = 44;

  const circumference =
    2 * Math.PI * radius;

  const agentDash =
    (normalizedAgent / 100) *
    circumference;

  return (
    <div
      style={{
        display: "flex",
        alignItems:
          "center",
        gap: 24,
        flexWrap: "wrap",
      }}
    >
      <svg
        width={110}
        height={110}
        viewBox="0 0 110 110"
      >
        <circle
          cx="55"
          cy="55"
          r={radius}
          fill="none"
          stroke="rgba(255,255,255,0.08)"
          strokeWidth="12"
        />

        {total > 0 && (
          <>
            <circle
              cx="55"
              cy="55"
              r={radius}
              fill="none"
              stroke="#22d3ee"
              strokeWidth="12"
              strokeDasharray={`${agentDash} ${
                circumference -
                agentDash
              }`}
              strokeDashoffset={
                circumference / 4
              }
              strokeLinecap="round"
            />

            <circle
              cx="55"
              cy="55"
              r={radius}
              fill="none"
              stroke="#a855f7"
              strokeWidth="12"
              strokeDasharray={`${
                circumference -
                agentDash
              } ${agentDash}`}
              strokeDashoffset={
                circumference / 4 -
                agentDash
              }
              strokeLinecap="round"
            />
          </>
        )}

        <text
          x="55"
          y="52"
          textAnchor="middle"
          fill="var(--fg)"
          fontSize="14"
          fontWeight="800"
        >
          {Math.round(
            normalizedAgent,
          )}
          %
        </text>

        <text
          x="55"
          y="65"
          textAnchor="middle"
          fill="var(--muted)"
          fontSize="9"
        >
          Agent
        </text>
      </svg>

      <div
        style={{
          display: "flex",
          flexDirection:
            "column",
          gap: 10,
          flex: 1,
          minWidth: 180,
        }}
      >
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 8,
          }}
        >
          <div
            style={{
              width: 10,
              height: 10,
              borderRadius: 3,
              background:
                "#22d3ee",
            }}
          />

          <span
            style={{
              fontSize: 13,
              color:
                "var(--muted)",
            }}
          >
            Agent changes
          </span>

          <span
            style={{
              fontSize: 13,
              fontWeight: 700,
              color:
                "#22d3ee",
              marginLeft:
                "auto",
            }}
          >
            {safeAgent.toFixed(1)}%
          </span>
        </div>

        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 8,
          }}
        >
          <div
            style={{
              width: 10,
              height: 10,
              borderRadius: 3,
              background:
                "#a855f7",
            }}
          />

          <span
            style={{
              fontSize: 13,
              color:
                "var(--muted)",
            }}
          >
            Human changes
          </span>

          <span
            style={{
              fontSize: 13,
              fontWeight: 700,
              color:
                "#a855f7",
              marginLeft:
                "auto",
            }}
          >
            {safeHuman.toFixed(1)}%
          </span>
        </div>
      </div>
    </div>
  );
}

function Section({
  icon,
  title,
  children,
}: {
  icon: React.ReactNode;
  title: string;
  children: React.ReactNode;
}) {
  return (
    <div
      style={{
        background:
          "rgba(255,255,255,0.03)",
        border:
          "1px solid rgba(255,255,255,0.08)",
        borderRadius: 16,
        padding: 24,
      }}
    >
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 8,
          marginBottom: 20,
        }}
      >
        {icon}

        <h3
          style={{
            margin: 0,
            fontSize: 14,
            fontWeight: 700,
            color:
              "var(--fg)",
          }}
        >
          {title}
        </h3>
      </div>

      {children}
    </div>
  );
}

export default function InsightsPage({
  params,
}: {
  params: Promise<{
    name: string;
  }>;
}) {
  const { name } =
    use(params);

  const [
    data,
    setData,
  ] = useState<
    InsightsData | null
  >(null);

  const [
    loading,
    setLoading,
  ] = useState(true);

  const [
    refreshing,
    setRefreshing,
  ] = useState(false);

  const [
    error,
    setError,
  ] = useState<string | null>(
    null,
  );

  const load =
    useCallback(
      async (
        showLoading = true,
      ) => {
        try {
          if (showLoading) {
            setLoading(
              true,
            );
          } else {
            setRefreshing(
              true,
            );
          }

          setError(null);

          const user =
            await authService.getCurrentUser();

          const result =
            await apiAuth<InsightsData>(
              `/v1/repositories/${encodeURIComponent(
                user.username,
              )}/${encodeURIComponent(
                name,
              )}/insights`,
            );

          setData(result);
        } catch (err: any) {
          console.error(
            "Failed to load insights",
            err,
          );

          setError(
            err?.detail ||
              err?.message ||
              "Failed to load insights.",
          );
        } finally {
          if (showLoading) {
            setLoading(
              false,
            );
          } else {
            setRefreshing(
              false,
            );
          }
        }
      },
      [name],
    );

  useEffect(() => {
    void load();
  }, [load]);

  if (loading) {
    return (
      <AppShell>
        <div
          style={{
            minHeight:
              "50vh",
            display:
              "flex",
            flexDirection:
              "column",
            alignItems:
              "center",
            justifyContent:
              "center",
            gap: 12,
            color:
              "var(--muted)",
          }}
        >
          <I.Loader
            size={22}
            color="#22d3ee"
            className="spin"
          />

          <span>
            Aggregating repository
            telemetry…
          </span>
        </div>

        <style>{`
          .spin {
            animation:
              insights-spin 1s linear infinite;
          }

          @keyframes insights-spin {
            to {
              transform: rotate(360deg);
            }
          }
        `}</style>
      </AppShell>
    );
  }

  if (error || !data) {
    return (
      <AppShell>
        <div
          style={{
            maxWidth: 700,
            margin:
              "70px auto",
            padding:
              "0 20px",
          }}
        >
          <div
            style={{
              background:
                "rgba(239,68,68,.06)",
              border:
                "1px solid rgba(239,68,68,.22)",
              borderRadius: 14,
              padding: 30,
              textAlign:
                "center",
            }}
          >
            <I.AlertCircle
              size={30}
              color="var(--red)"
              style={{
                marginBottom: 12,
              }}
            />

            <div
              style={{
                color:
                  "var(--fg)",
                fontWeight: 700,
                marginBottom: 7,
              }}
            >
              Unable to load
              insights
            </div>

            <div
              style={{
                color:
                  "var(--muted)",
                fontSize: 13,
              }}
            >
              {error ||
                "No insights data is available."}
            </div>

            <button
              type="button"
              onClick={() =>
                void load()
              }
              style={{
                marginTop: 18,
                padding:
                  "8px 14px",
                borderRadius: 8,
                border:
                  "1px solid var(--line)",
                background:
                  "var(--bg-subtle)",
                color:
                  "var(--fg)",
                cursor:
                  "pointer",
                fontSize: 12,
              }}
            >
              Try again
            </button>
          </div>
        </div>
      </AppShell>
    );
  }

  return (
    <AppShell>
      <div
        style={{
          maxWidth: 1200,
          margin: "0 auto",
          padding:
            "24px 20px 40px",
        }}
      >
        {/* Header */}
        <div
          style={{
            marginBottom: 30,
          }}
        >
          <div
            style={{
              display: "flex",
              alignItems:
                "center",
              gap: 12,
            }}
          >
            <div
              style={{
                width: 40,
                height: 40,
                borderRadius: 12,
                background:
                  "linear-gradient(135deg, #10b981, #059669)",
                display:
                  "grid",
                placeItems:
                  "center",
                boxShadow:
                  "0 0 20px rgba(16,185,129,0.3)",
              }}
            >
              <I.BarChart3
                size={20}
                color="#fff"
              />
            </div>

            <div>
              <h1
                style={{
                  fontSize: 20,
                  fontWeight: 700,
                  margin: 0,
                  color:
                    "var(--fg)",
                }}
              >
                Insights
              </h1>

              <p
                style={{
                  fontSize: 13,
                  color:
                    "var(--muted)",
                  margin: "2px 0 0",
                }}
              >
                Repository telemetry for{" "}
                {name}.
              </p>
            </div>

            <button
              type="button"
              onClick={() =>
                void load(false)
              }
              disabled={
                refreshing
              }
              title="Refresh insights"
              style={{
                marginLeft:
                  "auto",
                width: 34,
                height: 34,
                borderRadius: 8,
                border:
                  "1px solid var(--line)",
                background:
                  "var(--bg-subtle)",
                color:
                  "var(--fg)",
                display:
                  "grid",
                placeItems:
                  "center",
                cursor:
                  refreshing
                    ? "default"
                    : "pointer",
                opacity:
                  refreshing
                    ? 0.6
                    : 1,
              }}
            >
              <I.RefreshCw
                size={14}
                className={
                  refreshing
                    ? "spin"
                    : undefined
                }
              />
            </button>
          </div>

          {/* Actionable signal */}
          {(data.actionable_signal ||
            data.actionable_signal_details) && (
            <div
              style={{
                background:
                  "rgba(251,191,36,0.08)",
                border:
                  "1px solid rgba(251,191,36,0.2)",
                borderRadius: 12,
                padding:
                  "14px 18px",
                display:
                  "flex",
                gap: 12,
                alignItems:
                  "flex-start",
                marginTop: 20,
              }}
            >
              <I.Zap
                size={18}
                color="#fbbf24"
                style={{
                  flexShrink: 0,
                  marginTop: 1,
                }}
              />

              <div>
                {data.actionable_signal && (
                  <div
                    style={{
                      fontSize: 13,
                      fontWeight: 700,
                      color:
                        "#fbbf24",
                      marginBottom: 3,
                    }}
                  >
                    {
                      data.actionable_signal
                    }
                  </div>
                )}

                {data.actionable_signal_details && (
                  <div
                    style={{
                      fontSize: 12,
                      color:
                        "var(--muted)",
                      lineHeight:
                        1.5,
                    }}
                  >
                    {
                      data.actionable_signal_details
                    }
                  </div>
                )}
              </div>
            </div>
          )}
        </div>

        {/* DORA metrics */}
        <div
          style={{
            marginBottom: 24,
          }}
        >
          <div
            style={{
              fontSize: 12,
              fontWeight: 700,
              color:
                "var(--muted)",
              textTransform:
                "uppercase",
              letterSpacing: 1,
              marginBottom: 14,
            }}
          >
            Delivery Metrics
          </div>

          <div
            style={{
              display:
                "grid",
              gridTemplateColumns:
                "repeat(4,minmax(0,1fr))",
              gap: 14,
            }}
          >
            <MetricCard
              icon={
                <I.Rocket
                  size={18}
                  color="#10b981"
                />
              }
              label="Deploy Frequency"
              value={
                Number.isFinite(
                  data.deployments_per_week,
                )
                  ? data.deployments_per_week
                  : "—"
              }
              unit="/wk"
              description="Deployments per week"
            />

            <MetricCard
              icon={
                <I.Clock
                  size={18}
                  color="#22d3ee"
                />
              }
              label="Lead Time"
              value={formatMinutes(
                data.lead_time_minutes,
              )}
              description="Average change-to-deploy time"
            />

            <MetricCard
              icon={
                <I.CheckCircle2
                  size={18}
                  color="#6366f1"
                />
              }
              label="CI Pass Rate"
              value={
                Number.isFinite(
                  data.ci_pass_rate,
                )
                  ? data.ci_pass_rate.toFixed(
                      1,
                    )
                  : "—"
              }
              unit="%"
              description="Recorded CI success rate"
            />

            <MetricCard
              icon={
                <I.Bot
                  size={18}
                  color="#a855f7"
                />
              }
              label="Agent Changes"
              value={
                Number.isFinite(
                  data.agent_changes_percent,
                )
                  ? data.agent_changes_percent.toFixed(
                      1,
                    )
                  : "—"
              }
              unit="%"
              description="Share of changes attributed to agents"
            />
          </div>
        </div>

        {/* Secondary metrics */}
        <div
          style={{
            display:
              "grid",
            gridTemplateColumns:
              "1fr 1fr",
            gap: 18,
          }}
        >
          <Section
            icon={
              <I.ShieldCheck
                size={16}
                color="#10b981"
              />
            }
            title="CI Reliability"
          >
            <ProgressBar
              label="CI Build Success"
              value={
                data.ci_pass_rate
              }
              color="#10b981"
            />

            <div
              style={{
                padding:
                  "12px 14px",
                borderRadius: 9,
                background:
                  "rgba(255,255,255,0.03)",
                border:
                  "1px solid rgba(255,255,255,0.06)",
                color:
                  "var(--muted)",
                fontSize: 12,
                lineHeight: 1.5,
              }}
            >
              Insights currently
              expose CI pass rate
              as the reliability
              signal. No deployment
              success or Git uptime
              metric is presented
              unless the backend
              provides it.
            </div>
          </Section>

          <Section
            icon={
              <I.Users
                size={16}
                color="#a855f7"
              />
            }
            title="Agent vs Human"
          >
            <AgentHumanBreakdown
              agentPct={
                data.agent_changes_percent
              }
              humanPct={
                data.human_changes_percent
              }
            />

            <div
              style={{
                display:
                  "grid",
                gridTemplateColumns:
                  "1fr 1fr",
                gap: 12,
                marginTop: 20,
              }}
            >
              <div
                style={{
                  background:
                    "rgba(34,211,238,0.06)",
                  border:
                    "1px solid rgba(34,211,238,0.15)",
                  borderRadius: 10,
                  padding:
                    "10px 14px",
                }}
              >
                <div
                  style={{
                    fontSize: 11,
                    color:
                      "#22d3ee",
                    marginBottom: 4,
                  }}
                >
                  Agent Lead Time
                </div>

                <div
                  style={{
                    fontSize: 16,
                    fontWeight: 700,
                    color:
                      "var(--fg)",
                  }}
                >
                  {formatMinutes(
                    data.agent_lead_time_minutes,
                  )}
                </div>
              </div>

              <div
                style={{
                  background:
                    "rgba(168,85,247,0.06)",
                  border:
                    "1px solid rgba(168,85,247,0.15)",
                  borderRadius: 10,
                  padding:
                    "10px 14px",
                }}
              >
                <div
                  style={{
                    fontSize: 11,
                    color:
                      "#a855f7",
                    marginBottom: 4,
                  }}
                >
                  Human Lead Time
                </div>

                <div
                  style={{
                    fontSize: 16,
                    fontWeight: 700,
                    color:
                      "var(--fg)",
                  }}
                >
                  {formatMinutes(
                    data.human_lead_time_minutes,
                  )}
                </div>
              </div>
            </div>
          </Section>
        </div>
      </div>

      <style>{`
        .spin {
          animation: insights-spin 1s linear infinite;
        }

        @keyframes insights-spin {
          to {
            transform: rotate(360deg);
          }
        }

        @media (max-width: 900px) {
          .insights-grid {
            grid-template-columns: 1fr !important;
          }
        }
      `}</style>
    </AppShell>
  );
}