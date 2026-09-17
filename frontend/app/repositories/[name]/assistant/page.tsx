"use client";

import {
  use,
  useCallback,
  useEffect,
  useRef,
  useState,
} from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
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

import * as I from "lucide-react";

interface Thread {
  id: string;
  repository_id: string;
  user_id: string;
  title: string;
}

interface Message {
  id?: string;
  thread_id?: string;
  role: "user" | "assistant";
  content: string;
}

function MarkdownText({
  content,
}: {
  content: string;
}) {
  return (
    <div
      className="assistant-markdown"
      style={{
        fontSize: 14,
        lineHeight: 1.65,
        color: "#e5e7eb",
      }}
    >
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          h1: ({ children }) => (
            <h1
              style={{
                fontSize: 20,
                lineHeight: 1.3,
                margin: "0 0 12px",
                color: "var(--fg)",
              }}
            >
              {children}
            </h1>
          ),

          h2: ({ children }) => (
            <h2
              style={{
                fontSize: 17,
                lineHeight: 1.35,
                margin: "18px 0 10px",
                color: "var(--fg)",
              }}
            >
              {children}
            </h2>
          ),

          h3: ({ children }) => (
            <h3
              style={{
                fontSize: 15,
                lineHeight: 1.4,
                margin: "16px 0 8px",
                color: "var(--fg)",
              }}
            >
              {children}
            </h3>
          ),

          p: ({ children }) => (
            <p
              style={{
                margin: "0 0 12px",
              }}
            >
              {children}
            </p>
          ),

          ul: ({ children }) => (
            <ul
              style={{
                margin: "8px 0 14px",
                paddingLeft: 22,
              }}
            >
              {children}
            </ul>
          ),

          ol: ({ children }) => (
            <ol
              style={{
                margin: "8px 0 14px",
                paddingLeft: 22,
              }}
            >
              {children}
            </ol>
          ),

          li: ({ children }) => (
            <li
              style={{
                marginBottom: 5,
              }}
            >
              {children}
            </li>
          ),

          blockquote: ({ children }) => (
            <blockquote
              style={{
                margin: "12px 0",
                padding:
                  "8px 14px",
                borderLeft:
                  "3px solid #22d3ee",
                background:
                  "rgba(34,211,238,.05)",
                color:
                  "var(--muted)",
              }}
            >
              {children}
            </blockquote>
          ),

          a: ({ href, children }) => (
            <a
              href={href}
              target="_blank"
              rel="noopener noreferrer"
              style={{
                color: "#22d3ee",
                textDecoration:
                  "underline",
                textUnderlineOffset: 2,
              }}
            >
              {children}
            </a>
          ),

          code: ({
            className,
            children,
          }) => {
            const isBlock =
              Boolean(
                className,
              );

            if (!isBlock) {
              return (
                <code
                  style={{
                    background:
                      "rgba(255,255,255,.08)",
                    border:
                      "1px solid rgba(255,255,255,.08)",
                    borderRadius: 5,
                    padding:
                      "2px 5px",
                    fontFamily:
                      "monospace",
                    fontSize: 12,
                    color:
                      "#67e8f9",
                  }}
                >
                  {children}
                </code>
              );
            }

            return (
              <pre
                style={{
                  background:
                    "#0b1017",
                  border:
                    "1px solid rgba(255,255,255,.08)",
                  borderRadius: 9,
                  padding:
                    "12px 14px",
                  overflowX:
                    "auto",
                  margin:
                    "10px 0 14px",
                }}
              >
                <code
                  style={{
                    fontFamily:
                      "monospace",
                    fontSize: 12,
                    lineHeight: 1.6,
                    color:
                      "#d7dee8",
                  }}
                >
                  {children}
                </code>
              </pre>
            );
          },

          table: ({ children }) => (
            <div
              style={{
                overflowX:
                  "auto",
                margin:
                  "12px 0",
              }}
            >
              <table
                style={{
                  width:
                    "100%",
                  borderCollapse:
                    "collapse",
                  fontSize: 13,
                }}
              >
                {children}
              </table>
            </div>
          ),

          th: ({ children }) => (
            <th
              style={{
                textAlign:
                  "left",
                padding:
                  "8px 10px",
                border:
                  "1px solid var(--line)",
                background:
                  "rgba(255,255,255,.04)",
                color:
                  "var(--fg)",
              }}
            >
              {children}
            </th>
          ),

          td: ({ children }) => (
            <td
              style={{
                padding:
                  "8px 10px",
                border:
                  "1px solid var(--line)",
                color:
                  "var(--muted)",
              }}
            >
              {children}
            </td>
          ),

          hr: () => (
            <hr
              style={{
                border: 0,
                borderTop:
                  "1px solid var(--line)",
                margin:
                  "16px 0",
              }}
            />
          ),
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  );
}
function ThinkingDots() {
  return (
    <div
      style={{
        display: "flex",
        gap: 4,
        alignItems: "center",
      }}
    >
      {[0, 1, 2].map(
        (index) => (
          <span
            key={index}
            style={{
              width: 6,
              height: 6,
              borderRadius:
                "50%",
              background:
                "#22d3ee",
              animation:
                "assistant-bounce 1.2s ease-in-out infinite",
              animationDelay:
                `${index * 0.18}s`,
            }}
          />
        ),
      )}

      <style>{`
        @keyframes assistant-bounce {
          0%, 80%, 100% {
            transform: scale(.6);
            opacity: .4;
          }
          40% {
            transform: scale(1);
            opacity: 1;
          }
        }
      `}</style>
    </div>
  );
}

export default function AssistantPage({
  params,
}: {
  params: Promise<{
    name: string;
  }>;
}) {
  const { name } =
    use(params);

  const [
    owner,
    setOwner,
  ] = useState("");

  const [
    threads,
    setThreads,
  ] = useState<Thread[]>([]);

  const [
    threadId,
    setThreadId,
  ] = useState<
    string | null
  >(null);

  const [
    messages,
    setMessages,
  ] = useState<Message[]>(
    [],
  );

  const [
    input,
    setInput,
  ] = useState("");

  const [
    isInitializing,
    setIsInitializing,
  ] = useState(true);

  const [
    isLoadingMessages,
    setIsLoadingMessages,
  ] = useState(false);

  const [
    isSending,
    setIsSending,
  ] = useState(false);

  const [
    error,
    setError,
  ] = useState<
    string | null
  >(null);

  const [
    showThreads,
    setShowThreads,
  ] = useState(true);

  const messagesEndRef =
    useRef<HTMLDivElement>(
      null,
    );

  const textareaRef =
    useRef<HTMLTextAreaElement>(
      null,
    );

  const loadThreads =
    useCallback(
      async () => {
        const user =
          await authService.getCurrentUser();

        setOwner(
          user.username,
        );

        const result =
          await apiAuth<Thread[]>(
            `/v1/repositories/${encodeURIComponent(
              user.username,
            )}/${encodeURIComponent(
              name,
            )}/assistant/threads`,
          );

        setThreads(
          result || [],
        );

        return result || [];
      },
      [name],
    );

  const loadMessages =
    useCallback(
      async (
        selectedThreadId: string,
      ) => {
        try {
          setIsLoadingMessages(
            true,
          );
          setError(null);

          const result =
            await apiAuth<Message[]>(
              `/v1/assistant/threads/${encodeURIComponent(
                selectedThreadId,
              )}/messages`,
            );

          setMessages(
            result || [],
          );
        } catch (err: any) {
          console.error(
            "Failed to load assistant messages",
            err,
          );

          setMessages([]);

          setError(
            err?.detail ||
              err?.message ||
              "Failed to load conversation.",
          );
        } finally {
          setIsLoadingMessages(
            false,
          );
        }
      },
      [],
    );

  useEffect(() => {
    const initialise =
      async () => {
        try {
          setIsInitializing(
            true,
          );
          setError(null);

          const existing =
            await loadThreads();

          if (
            existing.length >
            0
          ) {
            const first =
              existing[0];

            setThreadId(
              first.id,
            );

            await loadMessages(
              first.id,
            );
          } else {
            await createNewThread(
              false,
            );
          }
        } catch (err: any) {
          console.error(
            "Failed to initialize assistant",
            err,
          );

          setError(
            err?.detail ||
              err?.message ||
              "Failed to initialize the assistant.",
          );
        } finally {
          setIsInitializing(
            false,
          );
        }
      };

    void initialise();

    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [name]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView(
      {
        behavior: "smooth",
      },
    );
  }, [
    messages,
    isSending,
  ]);

  const createNewThread =
    async (
      refreshThreadList = true,
    ) => {
      if (!owner) {
        return;
      }

      try {
        setError(null);

        const thread =
          await apiAuth<Thread>(
            `/v1/repositories/${encodeURIComponent(
              owner,
            )}/${encodeURIComponent(
              name,
            )}/assistant/threads`,
            {
              method: "POST",
              body: JSON.stringify(
                {
                  title: `${name} Assistant`,
                },
              ),
            },
          );

        setThreadId(
          thread.id,
        );

        setMessages([]);

        if (
          refreshThreadList
        ) {
          await loadThreads();
        }

        window.setTimeout(
          () =>
            textareaRef.current?.focus(),
          0,
        );
      } catch (err: any) {
        console.error(
          "Failed to create assistant thread",
          err,
        );

        setError(
          err?.detail ||
            err?.message ||
            "Failed to create a new conversation.",
        );
      }
    };

  const selectThread =
    async (
      selectedId: string,
    ) => {
      if (
        selectedId ===
        threadId
      ) {
        return;
      }

      setThreadId(
        selectedId,
      );

      await loadMessages(
        selectedId,
      );
    };

  const sendMessage =
    useCallback(
      async () => {
        const content =
          input.trim();

        if (
          !content ||
          !threadId ||
          isSending ||
          isInitializing
        ) {
          return;
        }

        setInput("");
        setError(null);

        const optimistic: Message =
          {
            role: "user",
            content,
          };

        setMessages(
          (previous) => [
            ...previous,
            optimistic,
          ],
        );

        setIsSending(true);

        try {
          const response =
            await apiAuth<Message[]>(
              `/v1/assistant/threads/${encodeURIComponent(
                threadId,
              )}/messages`,
              {
                method: "POST",
                body: JSON.stringify(
                  {
                    content,
                  },
                ),
              },
            );

          if (
            !Array.isArray(
              response,
            )
          ) {
            throw new Error(
              "Assistant returned an invalid response.",
            );
          }

          setMessages(
            (
              previous,
            ) => {
              const withoutOptimistic =
                previous.slice(
                  0,
                  -1,
                );

              return [
                ...withoutOptimistic,
                ...response,
              ];
            },
          );

          await loadThreads();
        } catch (err: any) {
          console.error(
            "Assistant request failed",
            err,
          );

          setMessages(
            (
              previous,
            ) =>
              previous.slice(
                0,
                -1,
              ),
          );

          setError(
            err?.detail ||
              err?.message ||
              "The assistant could not complete that request.",
          );

          setInput(
            content,
          );
        } finally {
          setIsSending(
            false,
          );

          window.setTimeout(
            () =>
              textareaRef.current?.focus(),
            0,
          );
        }
      },
      [
        input,
        threadId,
        isSending,
        isInitializing,
        loadThreads,
      ],
    );

  const handleKeyDown =
    (
      event: React.KeyboardEvent,
    ) => {
      if (
        event.key === "Enter" &&
        !event.shiftKey
      ) {
        event.preventDefault();
        void sendMessage();
      }
    };

  const suggestedQuestions =
    [
      "What does this repository do?",
      "Show me the recent changes",
      "What are the open tasks?",
      "What does the Knowledge Graph contain?",
    ];

  const selectedThread =
    threads.find(
      (thread) =>
        thread.id ===
        threadId,
    );

  return (
    <AppShell>
      <div
        style={{
          height:
            "calc(100vh - 120px)",
          display: "flex",
          flexDirection:
            "column",
          width: "100%",
        }}
      >
        {/* Header */}
        <div
          style={{
            padding:
              "18px 0 14px",
            borderBottom:
              "1px solid rgba(255,255,255,.07)",
            flexShrink: 0,
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
                "linear-gradient(135deg,#06b6d4,#3b82f6)",
              display:
                "grid",
              placeItems:
                "center",
              boxShadow:
                "0 0 20px rgba(6,182,212,.3)",
            }}
          >
            <I.Bot
              size={20}
              color="#fff"
            />
          </div>

          <div
            style={{
              minWidth: 0,
            }}
          >
            <h1
              style={{
                fontSize: 18,
                fontWeight: 700,
                margin: 0,
                color:
                  "var(--fg)",
              }}
            >
              {name} Assistant
            </h1>

            <div
              style={{
                fontSize: 12,
                color:
                  "var(--muted)",
                marginTop: 2,
              }}
            >
              Repository-aware AI
              assistant
            </div>
          </div>

          <div
            style={{
              marginLeft:
                "auto",
              display:
                "flex",
              gap: 8,
              alignItems:
                "center",
            }}
          >
            <span
              style={{
                fontSize: 11,
                padding:
                  "4px 9px",
                borderRadius: 20,
                background:
                  "rgba(34,211,238,.1)",
                border:
                  "1px solid rgba(34,211,238,.25)",
                color:
                  "#22d3ee",
                fontWeight: 600,
              }}
            >
              Live repository
              context
            </span>

            <button
              type="button"
              onClick={() =>
                setShowThreads(
                  (value) =>
                    !value,
                )
              }
              style={{
                display:
                  "none",
              }}
            >
              Threads
            </button>
          </div>
        </div>

        {/* Main layout */}
        <div
          style={{
            flex: 1,
            minHeight: 0,
            display:
              "flex",
            gap: 16,
            padding:
              "16px 0",
          }}
        >
          {/* Thread sidebar */}
          {showThreads && (
            <aside
              style={{
                width: 250,
                flexShrink: 0,
                border:
                  "1px solid rgba(255,255,255,.08)",
                borderRadius: 14,
                background:
                  "rgba(255,255,255,.02)",
                overflow:
                  "hidden",
                display:
                  "flex",
                flexDirection:
                  "column",
              }}
            >
              <div
                style={{
                  padding: 12,
                  borderBottom:
                    "1px solid rgba(255,255,255,.07)",
                  display:
                    "flex",
                  alignItems:
                    "center",
                  justifyContent:
                    "space-between",
                  gap: 8,
                }}
              >
                <span
                  style={{
                    fontSize: 12,
                    fontWeight: 700,
                    color:
                      "var(--muted)",
                    textTransform:
                      "uppercase",
                    letterSpacing: 1,
                  }}
                >
                  Conversations
                </span>

                <button
                  type="button"
                  onClick={() =>
                    void createNewThread()
                  }
                  disabled={
                    isInitializing
                  }
                  title="New conversation"
                  style={{
                    width: 30,
                    height: 30,
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
                      isInitializing
                        ? "default"
                        : "pointer",
                  }}
                >
                  <I.Plus
                    size={14}
                  />
                </button>
              </div>

              <div
                style={{
                  overflowY:
                    "auto",
                  padding: 8,
                  flex: 1,
                }}
              >
                {threads.length ===
                0 ? (
                  <div
                    style={{
                      padding:
                        "28px 14px",
                      textAlign:
                        "center",
                      fontSize: 12,
                      color:
                        "var(--muted)",
                    }}
                  >
                    No conversations
                    yet.
                  </div>
                ) : (
                  threads.map(
                    (
                      thread,
                    ) => (
                      <button
                        key={
                          thread.id
                        }
                        type="button"
                        onClick={() =>
                          void selectThread(
                            thread.id,
                          )
                        }
                        style={{
                          width:
                            "100%",
                          textAlign:
                            "left",
                          padding:
                            "10px 11px",
                          borderRadius: 9,
                          border:
                            "none",
                          background:
                            thread.id ===
                            threadId
                              ? "rgba(34,211,238,.1)"
                              : "transparent",
                          color:
                            thread.id ===
                            threadId
                              ? "var(--fg)"
                              : "var(--muted)",
                          cursor:
                            "pointer",
                          marginBottom: 3,
                        }}
                      >
                        <div
                          style={{
                            fontSize: 13,
                            fontWeight:
                              thread.id ===
                              threadId
                                ? 600
                                : 500,
                            overflow:
                              "hidden",
                            textOverflow:
                              "ellipsis",
                            whiteSpace:
                              "nowrap",
                          }}
                        >
                          {thread.title}
                        </div>

                        <div
                          style={{
                            fontSize: 10,
                            marginTop: 4,
                            opacity:
                              0.65,
                            fontFamily:
                              "monospace",
                          }}
                        >
                          {thread.id.slice(
                            0,
                            8,
                          )}
                        </div>
                      </button>
                    ),
                  )
                )}
              </div>
            </aside>
          )}

          {/* Conversation */}
          <main
            style={{
              flex: 1,
              minWidth: 0,
              minHeight: 0,
              display:
                "flex",
              flexDirection:
                "column",
            }}
          >
            {selectedThread && (
              <div
                style={{
                  fontSize: 12,
                  color:
                    "var(--muted)",
                  marginBottom: 8,
                }}
              >
                {selectedThread.title}
              </div>
            )}

            {error && (
              <div
                style={{
                  marginBottom: 10,
                  padding:
                    "10px 12px",
                  borderRadius: 8,
                  border:
                    "1px solid rgba(239,68,68,.22)",
                  background:
                    "rgba(239,68,68,.06)",
                  color:
                    "var(--red)",
                  fontSize: 12,
                  display:
                    "flex",
                  gap: 8,
                  alignItems:
                    "flex-start",
                }}
              >
                <I.AlertCircle
                  size={14}
                  style={{
                    flexShrink: 0,
                  }}
                />

                <span>
                  {error}
                </span>
              </div>
            )}

            <div
              style={{
                flex: 1,
                minHeight: 0,
                overflowY:
                  "auto",
                padding:
                  "12px 0 20px",
                display:
                  "flex",
                flexDirection:
                  "column",
                gap: 20,
              }}
            >
              {isInitializing ||
              isLoadingMessages ? (
                <div style={{ display: "flex", flexDirection: "column", gap: 18, padding: 16 }}>
                  <div style={{ alignSelf: "flex-end", width: "50%", padding: 14, borderRadius: 12, background: "var(--bg-subtle)" }}>
                    <Skeleton width="85%" height={14} borderRadius={4} style={{ marginBottom: 6 }} />
                    <Skeleton width="60%" height={14} borderRadius={4} />
                  </div>
                  <div style={{ alignSelf: "flex-start", width: "70%", padding: 16, borderRadius: 12, border: "1px solid var(--line)", background: "var(--surface)" }}>
                    <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 12 }}>
                      <Skeleton width={20} height={20} borderRadius="50%" />
                      <Skeleton width={110} height={14} borderRadius={4} />
                    </div>
                    <Skeleton width="95%" height={14} borderRadius={4} style={{ marginBottom: 8 }} />
                    <Skeleton width="90%" height={14} borderRadius={4} style={{ marginBottom: 8 }} />
                    <Skeleton width="65%" height={14} borderRadius={4} />
                  </div>
                </div>
              ) : messages.length ===
                0 ? (
                <div
                  style={{
                    flex: 1,
                    display:
                      "flex",
                    flexDirection:
                      "column",
                    alignItems:
                      "center",
                    justifyContent:
                      "center",
                    gap: 22,
                    padding:
                      "40px 0",
                  }}
                >
                  <div
                    style={{
                      width: 68,
                      height: 68,
                      borderRadius: 19,
                      background:
                        "linear-gradient(135deg,rgba(6,182,212,.15),rgba(59,130,246,.15))",
                      border:
                        "1px solid rgba(6,182,212,.2)",
                      display:
                        "grid",
                      placeItems:
                        "center",
                    }}
                  >
                    <I.Sparkles
                      size={30}
                      color="#22d3ee"
                    />
                  </div>

                  <div
                    style={{
                      textAlign:
                        "center",
                    }}
                  >
                    <h2
                      style={{
                        fontSize: 20,
                        fontWeight: 600,
                        color:
                          "var(--fg)",
                        margin:
                          "0 0 8px",
                      }}
                    >
                      Ask about{" "}
                      <span
                        style={{
                          color:
                            "#22d3ee",
                        }}
                      >
                        {name}
                      </span>
                    </h2>

                    <p
                      style={{
                        fontSize: 13,
                        color:
                          "var(--muted)",
                        margin: 0,
                        maxWidth: 580,
                        lineHeight:
                          1.55,
                      }}
                    >
                      The assistant receives
                      repository metadata,
                      recent changes,
                      open tasks, and
                      Knowledge Graph
                      entities with every
                      request.
                    </p>
                  </div>

                  <div
                    style={{
                      display:
                        "flex",
                      flexWrap:
                        "wrap",
                      gap: 8,
                      justifyContent:
                        "center",
                      maxWidth: 650,
                    }}
                  >
                    {suggestedQuestions.map(
                      (
                        question,
                      ) => (
                        <button
                          key={
                            question
                          }
                          type="button"
                          onClick={() => {
                            setInput(
                              question,
                            );
                            textareaRef.current?.focus();
                          }}
                          style={{
                            padding:
                              "8px 13px",
                            borderRadius:
                              20,
                            border:
                              "1px solid rgba(255,255,255,.12)",
                            background:
                              "rgba(255,255,255,.04)",
                            color:
                              "var(--muted)",
                            fontSize: 12,
                            cursor:
                              "pointer",
                          }}
                        >
                          {question}
                        </button>
                      ),
                    )}
                  </div>
                </div>
              ) : (
                <>
                  {messages.map(
                    (
                      message,
                      index,
                    ) => (
                      <div
                        key={
                          message.id ||
                          `${message.role}-${index}`
                        }
                        style={{
                          display:
                            "flex",
                          flexDirection:
                            message.role ===
                            "user"
                              ? "row-reverse"
                              : "row",
                          gap: 10,
                          alignItems:
                            "flex-start",
                        }}
                      >
                        <div
                          style={{
                            width: 34,
                            height: 34,
                            borderRadius: 10,
                            flexShrink: 0,
                            background:
                              message.role ===
                              "user"
                                ? "linear-gradient(135deg,#8b5cf6,#6366f1)"
                                : "linear-gradient(135deg,#06b6d4,#3b82f6)",
                            display:
                              "grid",
                            placeItems:
                              "center",
                          }}
                        >
                          {message.role ===
                          "user" ? (
                            <I.User
                              size={16}
                              color="#fff"
                            />
                          ) : (
                            <I.Bot
                              size={16}
                              color="#fff"
                            />
                          )}
                        </div>

                        <div
                          style={{
                            maxWidth:
                              "82%",
                            background:
                              message.role ===
                              "user"
                                ? "var(--surface-2)"
                                : "var(--surface)",
                            border:
                              message.role ===
                              "user"
                                ? "1px solid rgba(59,130,246,.25)"
                                : "1px solid var(--line)",
                            borderRadius: "var(--radius-sm)",
                            padding:
                              "10px 14px",
                            color:
                              "var(--text-primary)",
                          }}
                        >
                          {message.role ===
                          "assistant" ? (
                            <MarkdownText
                              content={
                                message.content
                              }
                            />
                          ) : (
                            <div
                              style={{
                                fontSize: 14,
                                lineHeight: 1.55,
                                whiteSpace:
                                  "pre-wrap",
                              }}
                            >
                              {
                                message.content
                              }
                            </div>
                          )}
                        </div>
                      </div>
                    ),
                  )}

                  {isSending && (
                    <div
                      style={{
                        display:
                          "flex",
                        gap: 10,
                        alignItems:
                          "flex-start",
                      }}
                    >
                      <div
                        style={{
                          width: 34,
                          height: 34,
                          borderRadius: 10,
                          background:
                            "linear-gradient(135deg,#06b6d4,#3b82f6)",
                          display:
                            "grid",
                          placeItems:
                            "center",
                        }}
                      >
                        <I.Bot
                          size={16}
                          color="#fff"
                        />
                      </div>

                      <div
                        style={{
                          background:
                            "rgba(255,255,255,.04)",
                          border:
                            "1px solid rgba(255,255,255,.08)",
                          borderRadius: 14,
                          borderTopLeftRadius: 4,
                          padding:
                            "12px 16px",
                        }}
                      >
                        <ThinkingDots />
                      </div>
                    </div>
                  )}
                </>
              )}

              <div
                ref={
                  messagesEndRef
                }
              />
            </div>

            {/* Composer */}
            <div
              style={{
                flexShrink: 0,
                paddingTop: 8,
                paddingBottom:
                  4,
              }}
            >
              <div
                style={{
                  background:
                    "rgba(255,255,255,.04)",
                  border:
                    "1px solid rgba(255,255,255,.1)",
                  borderRadius: 16,
                  padding:
                    "11px 14px",
                  display:
                    "flex",
                  gap: 10,
                  alignItems:
                    "flex-end",
                }}
              >
                <textarea
                  ref={
                    textareaRef
                  }
                  value={input}
                  onChange={(
                    event,
                  ) => {
                    setInput(
                      event.target
                        .value,
                    );

                    const element =
                      event.currentTarget;

                    element.style.height =
                      "auto";

                    element.style.height =
                      `${Math.min(
                        element
                          .scrollHeight,
                        140,
                      )}px`;
                  }}
                  onKeyDown={
                    handleKeyDown
                  }
                  placeholder={
                    threadId
                      ? `Ask about ${name}…`
                      : "Initializing assistant…"
                  }
                  disabled={
                    !threadId ||
                    isSending ||
                    isInitializing
                  }
                  rows={1}
                  style={{
                    flex: 1,
                    minHeight: 24,
                    maxHeight: 140,
                    resize:
                      "none",
                    background:
                      "transparent",
                    border:
                      "none",
                    outline:
                      "none",
                    color:
                      "var(--fg)",
                    fontSize: 14,
                    lineHeight: 1.5,
                    fontFamily:
                      "inherit",
                  }}
                />

                <button
                  type="button"
                  onClick={() =>
                    void sendMessage()
                  }
                  disabled={
                    !input.trim() ||
                    !threadId ||
                    isSending ||
                    isInitializing
                  }
                  style={{
                    width: 36,
                    height: 36,
                    borderRadius: 10,
                    border: "none",
                    flexShrink: 0,
                    background:
                      input.trim() &&
                      !isSending
                        ? "linear-gradient(135deg,#06b6d4,#3b82f6)"
                        : "rgba(255,255,255,.08)",
                    color:
                      input.trim() &&
                      !isSending
                        ? "#fff"
                        : "var(--muted)",
                    cursor:
                      input.trim() &&
                      !isSending
                        ? "pointer"
                        : "not-allowed",
                    display:
                      "grid",
                    placeItems:
                      "center",
                  }}
                >
                  {isSending ? (
                    <I.Loader
                      size={15}
                      className="assistant-spin"
                    />
                  ) : (
                    <I.Send
                      size={15}
                    />
                  )}
                </button>
              </div>

              <div
                style={{
                  fontSize: 11,
                  color:
                    "var(--muted)",
                  textAlign:
                    "center",
                  marginTop: 7,
                }}
              >
                Repository context:
                changes · tasks ·
                Knowledge Graph
              </div>
            </div>
          </main>
        </div>
      </div>

      <style>{`
        .assistant-spin {
          animation:
            assistant-spin 1s linear infinite;
        }

        @keyframes assistant-spin {
          to {
            transform: rotate(360deg);
          }
        }
      `}</style>
    </AppShell>
  );
}