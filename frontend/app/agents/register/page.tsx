"use client";

import { useState, useEffect } from "react";
import { Bot, Check, X, ShieldAlert } from "lucide-react";
import { Page, Card, Badge } from "@/components/ui";
import { apiAuth } from "@/lib/api";

type Registration = {
  id: string;
  agent_name: string;
  agent_description: string | null;
  provider: string | null;
  model: string | null;
  status: string;
  created_at: string;
  expires_at: string;
};

export default function AgentRegistrationPage() {
  const [pending, setPending] = useState<Registration[]>([]);
  const [loading, setLoading] = useState(true);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const fetchPending = async () => {
    setError(null);

    try {
      const data = await apiAuth<Registration[]>(
        "/v1/agents/registrations/pending",
      );

      setPending(data);
    } catch (e) {
      console.error("Failed to load pending registrations", e);

      setError(
        e instanceof Error
          ? e.message
          : "Failed to load pending registrations.",
      );
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void fetchPending();
  }, []);

  const handleAction = async (
    id: string,
    action: "approve" | "reject",
  ) => {
    setBusyId(id);
    setError(null);

    try {
      await apiAuth(
        `/v1/agents/registrations/${id}/${action}`,
        {
          method: "POST",
        },
      );

      await fetchPending();
    } catch (e) {
      console.error(
        `Failed to ${action} registration`,
        e,
      );

      setError(
        e instanceof Error
          ? e.message
          : `Failed to ${action} registration.`,
      );
    } finally {
      setBusyId(null);
    }
  };

  return (
    <Page
      eyebrow="Global Workspace"
      title="Agent Authorization"
      description="Review and authorize 3rd-party agents requesting access to your workspace."
    >
      <div className="section">
        <div className="sectionhead">
          <h2>Pending Authorizations</h2>
          <Badge tone="amber">
            Requires Action
          </Badge>
        </div>

        {error && (
          <Card
            style={{
              marginBottom: 16,
              borderColor: "rgba(248,113,113,.35)",
            }}
          >
            <div className="sub">
              {error}
            </div>
          </Card>
        )}

        {loading ? (
          <Card className="text-center py-8">
            <p className="sub">
              Checking for pending requests...
            </p>
          </Card>
        ) : pending.length > 0 ? (
          <div
            className="grid grid2"
            style={{ gap: "20px" }}
          >
            {pending.map((req) => {
              const busy = busyId === req.id;

              return (
                <Card
                  key={req.id}
                  style={{
                    display: "flex",
                    flexDirection: "column",
                    gap: "15px",
                  }}
                >
                  <div
                    style={{
                      display: "flex",
                      justifyContent: "space-between",
                      alignItems: "flex-start",
                    }}
                  >
                    <div
                      style={{
                        display: "flex",
                        alignItems: "center",
                        gap: "10px",
                      }}
                    >
                      <Bot
                        size={24}
                        className="cyan"
                      />

                      <div>
                        <h3
                          style={{
                            margin:
                              "0 0 5px 0",
                          }}
                        >
                          {req.agent_name}
                        </h3>

                        <Badge tone="purple">
                          {req.provider ||
                            "Custom Bot"}
                        </Badge>
                      </div>
                    </div>
                  </div>

                  <div
                    className="sub"
                    style={{ flexGrow: 1 }}
                  >
                    {req.agent_description ||
                      "An external agent is requesting workspace capabilities."}
                  </div>

                  <div
                    style={{
                      background:
                        "var(--bg-subtle)",
                      padding: "10px",
                      borderRadius: "8px",
                      display: "flex",
                      alignItems: "center",
                      gap: "10px",
                    }}
                  >
                    <ShieldAlert
                      size={16}
                      className="amber"
                    />

                    <span
                      className="sub"
                      style={{
                        fontSize: "0.85rem",
                      }}
                    >
                      Approving this request grants
                      the agent permission to perform
                      actions in this workspace.
                    </span>
                  </div>

                  <div
                    style={{
                      display: "flex",
                      gap: "10px",
                      marginTop: "10px",
                    }}
                  >
                    <button
                      className="btn primary"
                      disabled={busy}
                      style={{
                        flex: 1,
                        display: "flex",
                        justifyContent:
                          "center",
                        gap: "8px",
                        alignItems: "center",
                        opacity: busy ? 0.6 : 1,
                      }}
                      onClick={() =>
                        void handleAction(
                          req.id,
                          "approve",
                        )
                      }
                    >
                      <Check size={16} />
                      {busy
                        ? "Processing..."
                        : "Approve"}
                    </button>

                    <button
                      className="btn"
                      disabled={busy}
                      style={{
                        flex: 1,
                        display: "flex",
                        justifyContent:
                          "center",
                        gap: "8px",
                        alignItems: "center",
                        opacity: busy ? 0.6 : 1,
                      }}
                      onClick={() =>
                        void handleAction(
                          req.id,
                          "reject",
                        )
                      }
                    >
                      <X size={16} />
                      Reject
                    </button>
                  </div>
                </Card>
              );
            })}
          </div>
        ) : (
          <Card className="text-center py-10">
            <ShieldAlert
              size={32}
              className="dim"
              style={{
                margin: "0 auto 10px auto",
              }}
            />

            <h3>
              No pending authorizations
            </h3>

            <p className="sub">
              When a 3rd-party agent connects using
              the Device Flow, it will appear here
              for your approval.
            </p>
          </Card>
        )}
      </div>
    </Page>
  );
}