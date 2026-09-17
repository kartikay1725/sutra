"use client";

import {
  use,
  useCallback,
  useEffect,
  useMemo,
  useState,
} from "react";

import {
  AppShell,
  Skeleton,
} from "@/components/shell";

import {
  apiAuth,
} from "@/lib/api";

import {
  authService,
} from "@/lib/auth";

import {
  repositoryService,
} from "@/lib/repositories";

import * as I from "lucide-react";

interface KGNode {
  id: string;
  entity_type: string;
  name: string;
  summary?: string | null;
  content_hash?: string | null;
  metadata_json: Record<string, unknown>;
}

interface KGEdge {
  id: string;
  source_node_id: string;
  target_node_id: string;
  relationship_type: string;
}

interface Subgraph {
  node: KGNode;
  outgoing_edges: KGEdge[];
  incoming_edges: KGEdge[];
  neighbors: Record<string, KGNode>;
}

interface GraphResponse {
  nodes: KGNode[];
  edges?: KGEdge[];
}

type GraphTab = "explorer" | "all";

const ENTITY_COLORS: Record<
  string,
  {
    bg: string;
    border: string;
    text: string;
    icon: React.ReactNode;
  }
> = {
  file: {
    bg: "rgba(16,185,129,0.1)",
    border: "rgba(16,185,129,0.3)",
    text: "#10b981",
    icon: <I.FileText size={14} />,
  },
  function: {
    bg: "rgba(34,211,238,0.1)",
    border: "rgba(34,211,238,0.3)",
    text: "#22d3ee",
    icon: <I.Code2 size={14} />,
  },
  class: {
    bg: "rgba(168,85,247,0.1)",
    border: "rgba(168,85,247,0.3)",
    text: "#a855f7",
    icon: <I.Box size={14} />,
  },
  module: {
    bg: "rgba(251,191,36,0.1)",
    border: "rgba(251,191,36,0.3)",
    text: "#fbbf24",
    icon: <I.Package size={14} />,
  },
  task: {
    bg: "rgba(59,130,246,0.1)",
    border: "rgba(59,130,246,0.3)",
    text: "#3b82f6",
    icon: <I.CheckSquare size={14} />,
  },
  change: {
    bg: "rgba(249,115,22,0.1)",
    border: "rgba(249,115,22,0.3)",
    text: "#f97316",
    icon: <I.GitCommit size={14} />,
  },
  commit: {
    bg: "rgba(236,72,153,0.1)",
    border: "rgba(236,72,153,0.3)",
    text: "#ec4899",
    icon: <I.GitBranch size={14} />,
  },
  pull_request: {
    bg: "rgba(139,92,246,0.1)",
    border: "rgba(139,92,246,0.3)",
    text: "#8b5cf6",
    icon: <I.GitPullRequest size={14} />,
  },
  agent: {
    bg: "rgba(16,185,129,0.15)",
    border: "rgba(16,185,129,0.4)",
    text: "#10b981",
    icon: <I.Bot size={14} />,
  },
  discussion: {
    bg: "rgba(6,182,212,0.1)",
    border: "rgba(6,182,212,0.3)",
    text: "#06b6d4",
    icon: <I.MessageSquare size={14} />,
  },
  default: {
    bg: "rgba(99,102,241,0.1)",
    border: "rgba(99,102,241,0.3)",
    text: "#6366f1",
    icon: <I.Database size={14} />,
  },
};

function getEntityStyle(type: string) {
  return (
    ENTITY_COLORS[type] ||
    ENTITY_COLORS.default
  );
}

function EntityBadge({
  type,
}: {
  type: string;
}) {
  const c =
    getEntityStyle(type);

  return (
    <span
      style={{
        fontSize: 11,
        padding: "2px 8px",
        borderRadius: 6,
        fontWeight: 600,
        letterSpacing: "0.02em",
        background: c.bg,
        border: `1px solid ${c.border}`,
        color: c.text,
        display: "inline-flex",
        alignItems: "center",
        gap: 4,
      }}
    >
      {c.icon}
      {type}
    </span>
  );
}

function GraphCanvas({
  subgraph,
  onNodeClick,
}: {
  subgraph: Subgraph;
  onNodeClick: (
    id: string,
  ) => void;
}) {
  const neighbors =
    Object.values(
      subgraph.neighbors,
    );

  return (
    <div
      style={{
        minHeight: 400,
      }}
    >
      <div
        style={{
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          gap: 28,
        }}
      >
        <div
          style={{
            background: "var(--surface-2)",
            border: "1px solid var(--line)",
            borderRadius: "var(--radius-md)",
            padding: "16px 20px",
            textAlign: "center",
            boxShadow: "var(--shadow-sm)",
            width: "min(100%, 420px)",
          }}
        >
          <EntityBadge
            type={
              subgraph.node
                .entity_type
            }
          />

          <div
            style={{
              fontSize: 18,
              fontWeight: 700,
              color: "#fff",
              margin:
                "9px 0 5px",
              wordBreak:
                "break-word",
            }}
          >
            {subgraph.node.name}
          </div>

          {subgraph.node.summary && (
            <div
              style={{
                fontSize: 12,
                color:
                  "var(--muted)",
                lineHeight: 1.5,
              }}
            >
              {
                subgraph.node.summary
              }
            </div>
          )}

          <div
            style={{
              display: "flex",
              justifyContent:
                "center",
              gap: 10,
              marginTop: 12,
              fontSize: 11,
              color:
                "var(--muted)",
            }}
          >
            <span>
              {
                subgraph
                  .outgoing_edges
                  .length
              }{" "}
              outgoing
            </span>

            <span>·</span>

            <span>
              {
                subgraph
                  .incoming_edges
                  .length
              }{" "}
              incoming
            </span>
          </div>
        </div>

        {neighbors.length > 0 ? (
          <div
            style={{
              width: "100%",
            }}
          >
            <div
              style={{
                fontSize: 11,
                fontWeight: 700,
                color:
                  "var(--muted)",
                textTransform:
                  "uppercase",
                letterSpacing: 1,
                textAlign:
                  "center",
                marginBottom: 12,
              }}
            >
              Connected entities (
              {neighbors.length})
            </div>

            <div
              style={{
                display: "flex",
                flexWrap:
                  "wrap",
                gap: 10,
                justifyContent:
                  "center",
              }}
            >
              {neighbors.map(
                (node) => {
                  const style =
                    getEntityStyle(
                      node.entity_type,
                    );

                  const edge = [
                    ...subgraph.outgoing_edges,
                    ...subgraph.incoming_edges,
                  ].find(
                    (item) =>
                      item.source_node_id ===
                        node.id ||
                      item.target_node_id ===
                        node.id,
                  );

                  return (
                    <button
                      key={node.id}
                      type="button"
                      onClick={() =>
                        onNodeClick(
                          node.id,
                        )
                      }
                      style={{
                        background:
                          style.bg,
                        border: `1px solid ${style.border}`,
                        borderRadius: 12,
                        padding:
                          "11px 15px",
                        cursor:
                          "pointer",
                        textAlign:
                          "left",
                        transition:
                          "transform .15s, border-color .15s",
                        minWidth: 150,
                        color:
                          "var(--fg)",
                      }}
                      onMouseEnter={(
                        event,
                      ) => {
                        event.currentTarget.style.transform =
                          "translateY(-2px)";
                      }}
                      onMouseLeave={(
                        event,
                      ) => {
                        event.currentTarget.style.transform =
                          "translateY(0)";
                      }}
                    >
                      <div
                        style={{
                          display:
                            "flex",
                          alignItems:
                            "center",
                          gap: 6,
                          marginBottom: 5,
                        }}
                      >
                        <span
                          style={{
                            color:
                              style.text,
                          }}
                        >
                          {style.icon}
                        </span>

                        <EntityBadge
                          type={
                            node.entity_type
                          }
                        />
                      </div>

                      <div
                        style={{
                          fontSize: 13,
                          fontWeight: 600,
                          color:
                            "#fff",
                          wordBreak:
                            "break-word",
                        }}
                      >
                        {node.name}
                      </div>

                      {edge && (
                        <div
                          style={{
                            fontSize: 11,
                            color:
                              "var(--muted)",
                            marginTop: 5,
                          }}
                        >
                          via{" "}
                          <span
                            style={{
                              color:
                                style.text,
                            }}
                          >
                            {
                              edge.relationship_type
                            }
                          </span>
                        </div>
                      )}
                    </button>
                  );
                },
              )}
            </div>
          </div>
        ) : (
          <div
            style={{
              color:
                "var(--muted)",
              fontSize: 13,
              textAlign:
                "center",
              padding: 20,
            }}
          >
            No connected entities
            were found for this
            node.
          </div>
        )}
      </div>
    </div>
  );
}

export default function KnowledgeGraphPage({
  params,
}: {
  params: Promise<{
    name: string;
  }>;
}) {
  const { name } =
    use(params);

  const [owner, setOwner] =
    useState("");

  const [query, setQuery] =
    useState("");

  const [
    searchResults,
    setSearchResults,
  ] = useState<KGNode[]>([]);

  const [
    isSearching,
    setIsSearching,
  ] = useState(false);

  const [
    selectedNodeId,
    setSelectedNodeId,
  ] = useState<
    string | null
  >(null);

  const [
    subgraph,
    setSubgraph,
  ] = useState<
    Subgraph | null
  >(null);

  const [
    isLoadingNode,
    setIsLoadingNode,
  ] = useState(false);

  const [
    allNodes,
    setAllNodes,
  ] = useState<KGNode[]>([]);

  const [
    allEdges,
    setAllEdges,
  ] = useState<KGEdge[]>([]);

  const [
    activeTab,
    setActiveTab,
  ] = useState<GraphTab>(
    "explorer",
  );

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
  ] = useState<
    string | null
  >(null);

  const loadGraph =
    useCallback(
      async (
        requestedOwner: string,
        showLoader = true,
      ) => {
        if (!requestedOwner) {
          return;
        }

        try {
          if (showLoader) {
            setLoading(true);
          } else {
            setRefreshing(true);
          }

          setError(null);

          const data =
            await apiAuth<GraphResponse>(
              `/v1/repositories/${encodeURIComponent(
                requestedOwner,
              )}/${encodeURIComponent(
                name,
              )}/graph?limit=500`,
            );

          setAllNodes(
            data.nodes || [],
          );
          setAllEdges(
            data.edges || [],
          );

          // Keep the current selection only if
          // the selected entity still exists.
          if (
            selectedNodeId &&
            !data.nodes.some(
              (node) =>
                node.id ===
                selectedNodeId,
            )
          ) {
            setSelectedNodeId(
              null,
            );
            setSubgraph(null);
          }
        } catch (err: any) {
          console.error(
            "Knowledge Graph load failed",
            err,
          );

          setAllNodes([]);
          setAllEdges([]);

          setError(
            err?.detail ||
              err?.message ||
              "Unable to load the Knowledge Graph.",
          );
        } finally {
          if (showLoader) {
            setLoading(false);
          } else {
            setRefreshing(false);
          }
        }
      },
      [
        name,
        selectedNodeId,
      ],
    );

  useEffect(() => {
    let cancelled = false;

    const initialise =
      async () => {
        try {
          const user =
            await authService.getCurrentUser();

          if (cancelled) {
            return;
          }

          let canonicalOwner = user.username;
          try {
            const repo = await repositoryService.getRepository(user.username, name);
            if (repo && (repo.provider_owner || repo.owner)) {
              canonicalOwner = repo.provider_owner || repo.owner || user.username;
            }
          } catch {
            // fallback to user.username
          }

          setOwner(
            canonicalOwner,
          );

          await loadGraph(
            canonicalOwner,
          );
        } catch (err: any) {
          if (cancelled) {
            return;
          }

          setLoading(false);
          setError(
            err?.detail ||
              err?.message ||
              "Unable to determine the repository owner.",
          );
        }
      };

    void initialise();

    return () => {
      cancelled = true;
    };
  }, [
    name,
    loadGraph,
  ]);

  useEffect(() => {
    if (
      !owner ||
      !query.trim()
    ) {
      setSearchResults([]);
      return;
    }

    const timer =
      setTimeout(
        async () => {
          try {
            setIsSearching(
              true,
            );

            const data =
              await apiAuth<
                KGNode[]
              >(
                `/v1/repositories/${encodeURIComponent(
                  owner,
                )}/${encodeURIComponent(
                  name,
                )}/graph/search?q=${encodeURIComponent(
                  query.trim(),
                )}&limit=25`,
              );

            setSearchResults(
              data || [],
            );
          } catch (err) {
            console.error(
              "Knowledge Graph search failed",
              err,
            );

            setSearchResults(
              [],
            );
          } finally {
            setIsSearching(
              false,
            );
          }
        },
        250,
      );

    return () =>
      clearTimeout(
        timer,
      );
  }, [
    owner,
    name,
    query,
  ]);

  const loadSubgraph =
    useCallback(
      async (nodeId: string) => {
        if (!owner) {
          return;
        }

        try {
          setSelectedNodeId(
            nodeId,
          );
          setIsLoadingNode(
            true,
          );
          setError(null);

          const data =
            await apiAuth<Subgraph>(
              `/v1/repositories/${encodeURIComponent(
                owner,
              )}/${encodeURIComponent(
                name,
              )}/graph/nodes/${encodeURIComponent(
                nodeId,
              )}`,
            );

          setSubgraph(
            data,
          );
        } catch (err: any) {
          console.error(
            "Knowledge Graph subgraph load failed",
            err,
          );

          setSubgraph(
            null,
          );

          setError(
            err?.detail ||
              err?.message ||
              "Unable to load that graph node.",
          );
        } finally {
          setIsLoadingNode(
            false,
          );
        }
      },
      [
        owner,
        name,
      ],
    );

  const refresh =
    async () => {
      if (!owner) {
        return;
      }

      await loadGraph(
        owner,
        false,
      );

      if (
        selectedNodeId
      ) {
        await loadSubgraph(
          selectedNodeId,
        );
      }
    };

  const entityGroups =
    useMemo(
      () =>
        allNodes.reduce(
          (
            groups,
            node,
          ) => {
            const type =
              node.entity_type;

            if (!groups[type]) {
              groups[type] =
                [];
            }

            groups[type].push(
              node,
            );

            return groups;
          },
          {} as Record<
            string,
            KGNode[]
          >,
        ),
      [allNodes],
    );

  const entityTypeCount =
    Object.keys(
      entityGroups,
    ).length;

  return (
    <AppShell>
      <div
        style={{
          width: "100%",
        }}
      >
        {/* Header */}
        <div
          style={{
            marginBottom: 24,
          }}
        >
          <div
            style={{
              display: "flex",
              alignItems:
                "center",
              gap: 12,
              marginBottom: 10,
            }}
          >
            <div
              style={{
                width: 40,
                height: 40,
                borderRadius: 12,
                background:
                  "linear-gradient(135deg, #a855f7, #6366f1)",
                display:
                  "flex",
                alignItems:
                  "center",
                justifyContent:
                  "center",
                boxShadow:
                  "0 0 20px rgba(168,85,247,0.3)",
              }}
            >
              <I.Network
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
                Knowledge Graph
              </h1>

              <p
                style={{
                  fontSize: 13,
                  color:
                    "var(--muted)",
                  margin: 0,
                }}
              >
                Semantic map of{" "}
                {name}'s code
                entities and their
                relationships.
              </p>
            </div>

            <div
              style={{
                marginLeft:
                  "auto",
                display: "flex",
                alignItems:
                  "center",
                gap: 8,
                flexWrap:
                  "wrap",
                justifyContent:
                  "flex-end",
              }}
            >
              <span
                style={{
                  fontSize: 11,
                  padding:
                    "4px 10px",
                  borderRadius: 20,
                  background:
                    "rgba(168,85,247,0.1)",
                  border:
                    "1px solid rgba(168,85,247,0.25)",
                  color:
                    "#a855f7",
                  fontWeight: 600,
                }}
              >
                {allNodes.length}{" "}
                entities
              </span>

              <span
                style={{
                  fontSize: 11,
                  padding:
                    "4px 10px",
                  borderRadius: 20,
                  background:
                    "rgba(34,211,238,0.1)",
                  border:
                    "1px solid rgba(34,211,238,0.25)",
                  color:
                    "#22d3ee",
                  fontWeight: 600,
                }}
              >
                {allEdges.length}{" "}
                relationships
              </span>

              <span
                style={{
                  fontSize: 11,
                  padding:
                    "4px 10px",
                  borderRadius: 20,
                  background:
                    "var(--bg-subtle)",
                  border:
                    "1px solid var(--line)",
                  color:
                    "var(--muted)",
                }}
              >
                {entityTypeCount}{" "}
                types
              </span>

              <button
                type="button"
                onClick={() =>
                  void refresh()
                }
                disabled={
                  refreshing ||
                  loading
                }
                title="Refresh graph"
                style={{
                  width: 32,
                  height: 32,
                  borderRadius: 8,
                  display:
                    "grid",
                  placeItems:
                    "center",
                  border:
                    "1px solid var(--line)",
                  background:
                    "var(--bg-subtle)",
                  color:
                    "var(--fg)",
                  cursor:
                    refreshing ||
                    loading
                      ? "default"
                      : "pointer",
                  opacity:
                    refreshing ||
                    loading
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
          </div>

          {error && (
            <div
              style={{
                marginTop: 14,
                padding:
                  "10px 12px",
                borderRadius: 8,
                background:
                  "rgba(239,68,68,.08)",
                border:
                  "1px solid rgba(239,68,68,.22)",
                color:
                  "var(--red)",
                fontSize: 13,
                display:
                  "flex",
                alignItems:
                  "center",
                gap: 8,
              }}
            >
              <I.AlertCircle
                size={15}
              />

              <span>
                {error}
              </span>
            </div>
          )}
        </div>

        {/* Loading */}
        {loading ? (
          <div
            style={{
              border: "1px solid var(--line)",
              borderRadius: "var(--radius-md)",
              background: "var(--surface)",
              overflow: "hidden",
            }}
          >
            <div style={{ padding: "32px 28px", display: "flex", flexDirection: "column", gap: 20 }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <Skeleton width={180} height={20} borderRadius={4} />
                <div style={{ display: "flex", gap: 10 }}>
                  <Skeleton width={80} height={28} borderRadius={6} />
                  <Skeleton width={80} height={28} borderRadius={6} />
                </div>
              </div>
              <div style={{ height: 320, borderRadius: 10, border: "1px dashed var(--line)", background: "var(--bg-subtle)", display: "flex", alignItems: "center", justifyContent: "center", position: "relative" }}>
                <div style={{ display: "flex", alignItems: "center", gap: 32 }}>
                  <Skeleton width={72} height={72} borderRadius="50%" />
                  <Skeleton width={96} height={96} borderRadius="50%" />
                  <Skeleton width={64} height={64} borderRadius="50%" />
                </div>
              </div>
            </div>
          </div>
        ) : (
          <>
            {/* Tabs */}
            <div
              style={{
                display:
                  "flex",
                gap: 0,
                borderBottom:
                  "1px solid rgba(255,255,255,0.07)",
                marginBottom: 24,
              }}
            >
              {(
                [
                  "explorer",
                  "all",
                ] as const
              ).map((tab) => (
                <button
                  key={tab}
                  type="button"
                  onClick={() =>
                    setActiveTab(
                      tab,
                    )
                  }
                  style={{
                    padding:
                      "10px 20px",
                    border:
                      "none",
                    background:
                      "transparent",
                    color:
                      activeTab ===
                      tab
                        ? "#fff"
                        : "var(--muted)",
                    borderBottom:
                      activeTab ===
                      tab
                        ? "2px solid #a855f7"
                        : "2px solid transparent",
                    cursor:
                      "pointer",
                    fontSize: 14,
                    fontWeight:
                      activeTab ===
                      tab
                        ? 600
                        : 400,
                    marginBottom:
                      -1,
                  }}
                >
                  {tab ===
                  "explorer" ? (
                    <>
                      <I.Network
                        size={14}
                        style={{
                          display:
                            "inline",
                          verticalAlign:
                            "middle",
                          marginRight: 6,
                        }}
                      />
                      Explorer
                    </>
                  ) : (
                    <>
                      <I.Layers
                        size={14}
                        style={{
                          display:
                            "inline",
                          verticalAlign:
                            "middle",
                          marginRight: 6,
                        }}
                      />
                      All Entities
                    </>
                  )}
                </button>
              ))}
            </div>

            {/* Empty graph */}
            {allNodes.length ===
            0 ? (
              <div
                style={{
                  background:
                    "rgba(255,255,255,0.03)",
                  border:
                    "1px solid rgba(255,255,255,0.08)",
                  borderRadius: 16,
                  padding:
                    "70px 30px",
                  textAlign:
                    "center",
                }}
              >
                <I.Network
                  size={48}
                  style={{
                    opacity: 0.15,
                    display:
                      "block",
                    margin:
                      "0 auto 16px",
                  }}
                />

                <h3
                  style={{
                    color:
                      "var(--fg)",
                    margin:
                      "0 0 8px",
                    fontSize: 16,
                  }}
                >
                  Knowledge Graph
                  is empty
                </h3>

                <p
                  style={{
                    color:
                      "var(--muted)",
                    margin: 0,
                    fontSize: 13,
                    maxWidth: 520,
                    marginInline:
                      "auto",
                    lineHeight: 1.6,
                  }}
                >
                  There are no
                  indexed entities
                  for this repository
                  yet. Once graph
                  data is written
                  for the repository,
                  it will appear
                  here.
                </p>

                <button
                  type="button"
                  onClick={() =>
                    void refresh()
                  }
                  disabled={
                    refreshing
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
                  <I.RefreshCw
                    size={12}
                    style={{
                      marginRight: 6,
                      verticalAlign:
                        "middle",
                    }}
                  />
                  Refresh
                </button>
              </div>
            ) : (
              <>
                {/* Explorer */}
                {activeTab ===
                  "explorer" && (
                  <div
                    style={{
                      display:
                        "grid",
                      gridTemplateColumns:
                        "280px minmax(0,1fr)",
                      gap: 20,
                    }}
                  >
                    {/* Search */}
                    <div
                      style={{
                        background:
                          "rgba(255,255,255,0.03)",
                        border:
                          "1px solid rgba(255,255,255,0.08)",
                        borderRadius: 16,
                        overflow:
                          "hidden",
                        height:
                          "fit-content",
                        maxHeight:
                          "70vh",
                        display:
                          "flex",
                        flexDirection:
                          "column",
                      }}
                    >
                      <div
                        style={{
                          padding:
                            "14px 16px",
                          borderBottom:
                            "1px solid rgba(255,255,255,0.06)",
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
                            marginBottom: 10,
                          }}
                        >
                          Entity Search
                        </div>

                        <div
                          style={{
                            display:
                              "flex",
                            alignItems:
                              "center",
                            gap: 8,
                            background:
                              "rgba(0,0,0,0.3)",
                            border:
                              "1px solid rgba(255,255,255,0.08)",
                            borderRadius: 10,
                            padding:
                              "8px 12px",
                          }}
                        >
                          <I.Search
                            size={14}
                            color="var(--muted)"
                          />

                          <input
                            value={
                              query
                            }
                            onChange={(
                              event,
                            ) =>
                              setQuery(
                                event
                                  .target
                                  .value,
                              )
                            }
                            placeholder="Search entities..."
                            style={{
                              background:
                                "transparent",
                              border:
                                "none",
                              outline:
                                "none",
                              color:
                                "#fff",
                              fontSize: 13,
                              flex: 1,
                              fontFamily:
                                "inherit",
                            }}
                          />

                          {query && (
                            <button
                              type="button"
                              onClick={() =>
                                setQuery(
                                  "",
                                )
                              }
                              style={{
                                border:
                                  "none",
                                background:
                                  "transparent",
                                color:
                                  "var(--muted)",
                                cursor:
                                  "pointer",
                                padding: 0,
                              }}
                            >
                              <I.X
                                size={13}
                              />
                            </button>
                          )}

                          {isSearching && (
                            <I.Loader
                              size={12}
                              color="var(--muted)"
                              className="spin"
                            />
                          )}
                        </div>
                      </div>

                      <div
                        style={{
                          overflowY:
                            "auto",
                          flex: 1,
                          padding: 8,
                        }}
                      >
                        {searchResults.length >
                        0 ? (
                          searchResults.map(
                            (node) => {
                              const c =
                                getEntityStyle(
                                  node.entity_type,
                                );

                              return (
                                <button
                                  key={
                                    node.id
                                  }
                                  type="button"
                                  onClick={() =>
                                    void loadSubgraph(
                                      node.id,
                                    )
                                  }
                                  style={{
                                    width:
                                      "100%",
                                    padding:
                                      "10px 12px",
                                    borderRadius: 10,
                                    border:
                                      "none",
                                    background:
                                      selectedNodeId ===
                                      node.id
                                        ? "rgba(168,85,247,0.1)"
                                        : "transparent",
                                    cursor:
                                      "pointer",
                                    textAlign:
                                      "left",
                                    display:
                                      "flex",
                                    gap: 10,
                                    alignItems:
                                      "flex-start",
                                  }}
                                >
                                  <span
                                    style={{
                                      color:
                                        c.text,
                                      marginTop: 1,
                                    }}
                                  >
                                    {
                                      c.icon
                                    }
                                  </span>

                                  <div
                                    style={{
                                      minWidth:
                                        0,
                                    }}
                                  >
                                    <div
                                      style={{
                                        fontSize: 13,
                                        fontWeight: 600,
                                        color:
                                          "#fff",
                                        overflow:
                                          "hidden",
                                        textOverflow:
                                          "ellipsis",
                                        whiteSpace:
                                          "nowrap",
                                      }}
                                    >
                                      {
                                        node.name
                                      }
                                    </div>

                                    <div
                                      style={{
                                        fontSize: 11,
                                        color:
                                          c.text,
                                        marginTop: 2,
                                      }}
                                    >
                                      {
                                        node.entity_type
                                      }
                                    </div>
                                  </div>
                                </button>
                              );
                            },
                          )
                        ) : query ? (
                          <div
                            style={{
                              padding: 24,
                              textAlign:
                                "center",
                              color:
                                "var(--muted)",
                              fontSize: 13,
                            }}
                          >
                            No entities
                            found for "
                            {query}"
                          </div>
                        ) : (
                          <div
                            style={{
                              padding:
                                "30px 20px",
                              textAlign:
                                "center",
                            }}
                          >
                            <I.Network
                              size={32}
                              style={{
                                opacity:
                                  0.15,
                                display:
                                  "block",
                                margin:
                                  "0 auto 12px",
                              }}
                            />

                            <p
                              style={{
                                fontSize: 13,
                                color:
                                  "var(--muted)",
                                margin: 0,
                                lineHeight:
                                  1.5,
                              }}
                            >
                              Search the
                              repository's
                              indexed
                              entities.
                            </p>
                          </div>
                        )}
                      </div>
                    </div>

                    {/* Subgraph */}
                    <div
                      style={{
                        background:
                          "rgba(255,255,255,0.03)",
                        border:
                          "1px solid rgba(255,255,255,0.08)",
                        borderRadius: 16,
                        padding: 28,
                        minHeight:
                          400,
                      }}
                    >
                      {isLoadingNode ? (
                        <div
                          style={{
                            display:
                              "flex",
                            alignItems:
                              "center",
                            justifyContent:
                              "center",
                            minHeight:
                              340,
                            gap: 12,
                            color:
                              "var(--muted)",
                            fontSize: 13,
                          }}
                        >
                          <I.Loader
                            size={20}
                            className="spin"
                            style={{
                              color:
                                "#a855f7",
                            }}
                          />
                          Loading
                          relationships…
                        </div>
                      ) : subgraph ? (
                        <GraphCanvas
                          subgraph={
                            subgraph
                          }
                          onNodeClick={
                            loadSubgraph
                          }
                        />
                      ) : (
                        <div
                          style={{
                            display:
                              "flex",
                            flexDirection:
                              "column",
                            alignItems:
                              "center",
                            justifyContent:
                              "center",
                            minHeight:
                              340,
                            gap: 14,
                          }}
                        >
                          <I.Network
                            size={48}
                            style={{
                              opacity:
                                0.1,
                            }}
                          />

                          <div
                            style={{
                              fontSize: 14,
                              fontWeight: 600,
                              color:
                                "var(--fg)",
                            }}
                          >
                            Explore the
                            graph
                          </div>

                          <p
                            style={{
                              color:
                                "var(--muted)",
                              fontSize: 13,
                              textAlign:
                                "center",
                              maxWidth:
                                310,
                              margin: 0,
                              lineHeight:
                                1.5,
                            }}
                          >
                            Search for
                            an entity,
                            then select
                            it to inspect
                            its immediate
                            relationships.
                          </p>
                        </div>
                      )}
                    </div>
                  </div>
                )}

                {/* All entities */}
                {activeTab === "all" && (
                  <div
                    style={{
                      display:
                        "flex",
                      flexDirection:
                        "column",
                      gap: 24,
                    }}
                  >
                    {Object.entries(
                      entityGroups,
                    ).map(
                      ([
                        type,
                        nodes,
                      ]) => {
                        const c =
                          getEntityStyle(
                            type,
                          );

                        return (
                          <div
                            key={type}
                          >
                            <div
                              style={{
                                display:
                                  "flex",
                                alignItems:
                                  "center",
                                gap: 8,
                                marginBottom: 12,
                              }}
                            >
                              <span
                                style={{
                                  color:
                                    c.text,
                                }}
                              >
                                {
                                  c.icon
                                }
                              </span>

                              <h3
                                style={{
                                  margin: 0,
                                  fontSize: 14,
                                  fontWeight: 700,
                                  color:
                                    "var(--fg)",
                                  textTransform:
                                    "capitalize",
                                }}
                              >
                                {type}
                              </h3>

                              <span
                                style={{
                                  fontSize: 11,
                                  padding:
                                    "1px 8px",
                                  borderRadius: 20,
                                  background:
                                    c.bg,
                                  color:
                                    c.text,
                                  border: `1px solid ${c.border}`,
                                }}
                              >
                                {
                                  nodes.length
                                }
                              </span>
                            </div>

                            <div
                              style={{
                                display:
                                  "grid",
                                gridTemplateColumns:
                                  "repeat(auto-fill,minmax(220px,1fr))",
                                gap: 10,
                              }}
                            >
                              {nodes.map(
                                (
                                  node,
                                ) => (
                                  <button
                                    key={
                                      node.id
                                    }
                                    type="button"
                                    onClick={() => {
                                      setActiveTab(
                                        "explorer",
                                      );
                                      void loadSubgraph(
                                        node.id,
                                      );
                                    }}
                                    style={{
                                      background:
                                        c.bg,
                                      border:
                                        `1px solid ${c.border}`,
                                      borderRadius: 12,
                                      padding:
                                        "13px 16px",
                                      cursor:
                                        "pointer",
                                      textAlign:
                                        "left",
                                      transition:
                                        "transform .15s, border-color .15s",
                                      color:
                                        "var(--fg)",
                                    }}
                                    onMouseEnter={(
                                      event,
                                    ) => {
                                      event.currentTarget.style.transform =
                                        "translateY(-2px)";
                                    }}
                                    onMouseLeave={(
                                      event,
                                    ) => {
                                      event.currentTarget.style.transform =
                                        "translateY(0)";
                                    }}
                                  >
                                    <div
                                      style={{
                                        display:
                                          "flex",
                                        alignItems:
                                          "center",
                                        gap: 7,
                                        marginBottom: 7,
                                      }}
                                    >
                                      <EntityBadge
                                        type={
                                          node.entity_type
                                        }
                                      />
                                    </div>

                                    <div
                                      style={{
                                        fontSize: 13,
                                        fontWeight: 700,
                                        color:
                                          "#fff",
                                        marginBottom: 5,
                                        wordBreak:
                                          "break-word",
                                      }}
                                    >
                                      {
                                        node.name
                                      }
                                    </div>

                                    {node.summary && (
                                      <div
                                        style={{
                                          fontSize: 12,
                                          color:
                                            "var(--muted)",
                                          lineHeight:
                                            1.4,
                                        }}
                                      >
                                        {
                                          node.summary
                                        }
                                      </div>
                                    )}

                                    <div
                                      style={{
                                        fontSize: 11,
                                        color:
                                          c.text,
                                        marginTop: 8,
                                      }}
                                    >
                                      Open
                                      relationships
                                      →
                                    </div>
                                  </button>
                                ),
                              )}
                            </div>
                          </div>
                        );
                      },
                    )}
                  </div>
                )}
              </>
            )}
          </>
        )}
      </div>

      <style>{`
        .spin {
          animation: kg-spin 1s linear infinite;
        }

        @keyframes kg-spin {
          to {
            transform: rotate(360deg);
          }
        }

        @media (max-width: 800px) {
          .kg-explorer-grid {
            grid-template-columns: 1fr !important;
          }
        }
      `}</style>
    </AppShell>
  );
}