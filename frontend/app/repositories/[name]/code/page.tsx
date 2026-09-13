"use client";

import { AppShell } from "@/components/shell";
import React, {
  useState,
  useEffect,
  useCallback,
  useRef,
  use,
} from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { authService } from "@/lib/auth";
import { repositoryService } from "@/lib/repositories";
import { apiAuth, API_URL } from "@/lib/api";
import { clientCache, CACHE_TTL } from "@/lib/cache";
import {
  GitBranch,
  GitCommit,
  ChevronDown,
  ChevronRight,
  Folder,
  FileCode2,
  Copy,
  Check,
  MessageSquare,
  X,
  Send,
  CheckCircle2,
  AlertCircle,
} from "lucide-react";

// ─── Types ───────────────────────────────────────────────────────────────────

interface TreeEntry {
  name: string;
  path: string;
  type: "file" | "directory";
  size?: number;
}

interface FileContent {
  content: string;
  encoding: string;
  size: number;
  path: string;
  ref: string;
}

interface Commit {
  sha: string;
  subject: string;
  author_name: string;
  author_email: string;
  committed_at: number;
}

interface Branch {
  name: string;
  protected: boolean;
  commit: string;
  is_default?: boolean;
}

interface InlineComment {
  id: string;
  line_number: number;
  body: string;
  author_id: string;
  status: string;
  created_at: string;
  replies?: InlineComment[];
}

interface ProvenanceAgent {
  id: string;
  name: string;
  provider?: string | null;
  model?: string | null;
}

interface ProvenanceSession {
  id: string;
  status: string;
  expires_at?: string | null;
}

interface ProvenanceTask {
  id: string;
  title: string;
  status: string;
  task_type: string;
}

interface LineProvenance {
  source: "sutra" | "github";
  tracked: boolean;
  identity_type:
    | "agent"
    | "human"
    | "external"
    | "unknown";
  actor_id: string | null;
  actor_name: string | null;
  change_id: string | null;
  agent: ProvenanceAgent | null;
  session: ProvenanceSession | null;
  task: ProvenanceTask | null;
}

interface BlameRange {
  start_line: number;
  end_line: number;
  age?: number;
  commit: string;
  short_commit: string;
  subject: string;
  author_name: string;
  author_email: string;
  github_login?: string | null;
  authored_at?: string | null;
  provenance: LineProvenance;
}

interface BlameResponse {
  repository_id: string;
  path: string;
  ref: string;
  ranges: BlameRange[];
}

// ─── Language detection ───────────────────────────────────────────────────────

function detectLang(path: string): string {
  const ext =
    path.split(".").pop()?.toLowerCase() || "";

  const map: Record<string, string> = {
    ts: "typescript",
    tsx: "typescript",
    js: "javascript",
    jsx: "javascript",
    py: "python",
    rs: "rust",
    go: "go",
    java: "java",
    cpp: "cpp",
    c: "c",
    cs: "csharp",
    rb: "ruby",
    php: "php",
    swift: "swift",
    kt: "kotlin",
    html: "html",
    css: "css",
    scss: "css",
    json: "json",
    yaml: "yaml",
    yml: "yaml",
    md: "markdown",
    sh: "bash",
    bash: "bash",
    sql: "sql",
    toml: "toml",
    xml: "xml",
    dockerfile: "dockerfile",
  };

  return map[ext] || "plaintext";
}

function formatSize(bytes: number): string {
  if (bytes < 1024) {
    return `${bytes} B`;
  }

  if (bytes < 1024 * 1024) {
    return `${(bytes / 1024).toFixed(1)} KB`;
  }

  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

function timeSince(dateStr: string): string {
  const date = new Date(dateStr);
  const now = new Date();

  const secs = Math.floor(
    (now.getTime() - date.getTime()) / 1000,
  );

  if (secs < 60) {
    return "just now";
  }

  if (secs < 3600) {
    return `${Math.floor(secs / 60)}m ago`;
  }

  if (secs < 86400) {
    return `${Math.floor(secs / 3600)}h ago`;
  }

  return `${Math.floor(secs / 86400)}d ago`;
}

// ─── Syntax highlighting ─────────────────────────────────────────────────────

function highlightLine(
  line: string,
  lang: string,
): string {
  const esc = (s: string) =>
    s
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;");

  const raw = esc(line);

  if (
    lang === "plaintext" ||
    lang === "markdown"
  ) {
    return raw;
  }

  const keywords: Record<
    string,
    string[]
  > = {
    typescript: [
      "import",
      "export",
      "from",
      "const",
      "let",
      "var",
      "function",
      "return",
      "async",
      "await",
      "if",
      "else",
      "for",
      "while",
      "class",
      "interface",
      "type",
      "extends",
      "implements",
      "new",
      "this",
      "throw",
      "try",
      "catch",
      "finally",
      "null",
      "undefined",
      "true",
      "false",
      "void",
      "string",
      "number",
      "boolean",
      "any",
    ],

    python: [
      "import",
      "from",
      "def",
      "class",
      "return",
      "if",
      "else",
      "elif",
      "for",
      "while",
      "try",
      "except",
      "finally",
      "with",
      "as",
      "pass",
      "break",
      "continue",
      "raise",
      "True",
      "False",
      "None",
      "and",
      "or",
      "not",
      "in",
      "is",
      "lambda",
      "yield",
    ],

    go: [
      "package",
      "import",
      "func",
      "var",
      "const",
      "type",
      "struct",
      "interface",
      "return",
      "if",
      "else",
      "for",
      "range",
      "switch",
      "case",
      "default",
      "break",
      "continue",
      "defer",
      "go",
      "select",
      "chan",
      "map",
      "make",
      "new",
      "nil",
      "true",
      "false",
    ],

    rust: [
      "fn",
      "let",
      "mut",
      "const",
      "use",
      "mod",
      "pub",
      "struct",
      "enum",
      "impl",
      "trait",
      "return",
      "if",
      "else",
      "for",
      "while",
      "loop",
      "match",
      "break",
      "continue",
      "self",
      "Self",
      "true",
      "false",
      "None",
      "Some",
      "Ok",
      "Err",
    ],
  };

  if (
    line.trim().startsWith("//") ||
    line.trim().startsWith("#")
  ) {
    return `<span class="cmt">${raw}</span>`;
  }

  const kws = new Set(
    keywords[lang] ||
      keywords.typescript,
  );

  return raw.replace(
    /([A-Za-z_][A-Za-z0-9_]*|"(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*'|`(?:\\.|[^`\\])*`|\/\/.*|#.*)/g,
    (match) => {
      if (
        match.startsWith("//") ||
        match.startsWith("#")
      ) {
        return `<span class="cmt">${match}</span>`;
      }

      if (
        (match.startsWith('"') &&
          match.endsWith('"')) ||
        (match.startsWith("'") &&
          match.endsWith("'")) ||
        (match.startsWith("`") &&
          match.endsWith("`"))
      ) {
        return `<span class="str">${match}</span>`;
      }

      if (kws.has(match)) {
        return `<span class="kw">${match}</span>`;
      }

      return match;
    },
  );
}

// ─── Provenance helpers ──────────────────────────────────────────────────────

function provenanceForLine(
  ranges: BlameRange[],
  lineNumber: number,
): BlameRange | null {
  return (
    ranges.find(
      (range) =>
        lineNumber >= range.start_line &&
        lineNumber <= range.end_line,
    ) || null
  );
}

function provenanceLabel(
  provenance: LineProvenance,
): string {
  if (
    provenance.identity_type ===
    "agent"
  ) {
    return (
      provenance.agent?.name ||
      provenance.actor_name ||
      "SUTRA Agent"
    );
  }

  if (
    provenance.identity_type ===
    "human"
  ) {
    return (
      provenance.actor_name ||
      "SUTRA Human"
    );
  }

  if (
    provenance.identity_type ===
    "external"
  ) {
    return "GitHub";
  }

  return "Unknown";
}

function provenanceIcon(
  provenance: LineProvenance,
): string {
  if (
    provenance.identity_type ===
    "agent"
  ) {
    return "🤖";
  }

  if (
    provenance.identity_type ===
    "human"
  ) {
    return "👤";
  }

  if (
    provenance.identity_type ===
    "external"
  ) {
    return "◉";
  }

  return "•";
}

function provenanceColor(
  provenance: LineProvenance,
): string {
  if (
    provenance.identity_type ===
    "agent"
  ) {
    return "#a78bfa";
  }

  if (
    provenance.identity_type ===
    "human"
  ) {
    return "#22d3ee";
  }

  if (
    provenance.identity_type ===
    "external"
  ) {
    return "#94a3b8";
  }

  return "#a78bfa";
}

// ─── Branch Switcher ─────────────────────────────────────────────────────────

function BranchSwitcher({
  branches,
  current,
  onChange,
}: {
  branches: Branch[];
  current: string;
  onChange: (branch: string) => void;
}) {
  const [open, setOpen] =
    useState(false);

  const [search, setSearch] =
    useState("");

  const filtered =
    branches.filter((branch) =>
      branch.name
        .toLowerCase()
        .includes(
          search.toLowerCase(),
        ),
    );

  return (
    <div
      style={{
        position: "relative",
      }}
    >
      <button
        onClick={() =>
          setOpen((value) => !value)
        }
        style={{
          display: "flex",
          alignItems: "center",
          gap: 6,
          padding: "6px 12px",
          background:
            "var(--bg-card)",
          border:
            "1px solid var(--line)",
          borderRadius: 6,
          cursor: "pointer",
          color: "var(--fg)",
          fontSize: 13,
          transition:
            "all 0.2s",
        }}
      >
        <GitBranch
          size={13}
          className="cyan"
        />

        <span
          style={{
            fontWeight: 500,
          }}
        >
          {current || "Select branch"}
        </span>

        <ChevronDown
          size={13}
          style={{
            opacity: 0.6,
          }}
        />
      </button>

      {open && (
        <div
          style={{
            position:
              "absolute",
            top:
              "calc(100% + 6px)",
            left: 0,
            zIndex: 100,
            background:
              "var(--bg-card)",
            border:
              "1px solid var(--line)",
            borderRadius: 8,
            width: 240,
            boxShadow:
              "0 8px 32px rgba(0,0,0,0.4)",
            overflow: "hidden",
          }}
        >
          <div
            style={{
              padding: "8px 10px",
              borderBottom:
                "1px solid var(--line)",
            }}
          >
            <input
              autoFocus
              value={search}
              onChange={(event) =>
                setSearch(
                  event.target.value,
                )
              }
              placeholder="Find a branch..."
              style={{
                width: "100%",
                background:
                  "var(--bg-page)",
                border:
                  "1px solid var(--line)",
                borderRadius: 4,
                padding:
                  "5px 8px",
                color:
                  "var(--fg)",
                fontSize: 12,
                outline: "none",
              }}
            />
          </div>

          <div
            style={{
              maxHeight: 240,
              overflowY: "auto",
            }}
          >
            {filtered.map(
              (item) => (
                <button
                  key={item.name}
                  onClick={() => {
                    onChange(
                      item.name,
                    );
                    setOpen(false);
                    setSearch("");
                  }}
                  style={{
                    display:
                      "flex",
                    alignItems:
                      "center",
                    gap: 8,
                    width: "100%",
                    padding:
                      "9px 12px",
                    background:
                      item.name ===
                      current
                        ? "rgba(255,255,255,0.05)"
                        : "transparent",
                    border: "none",
                    cursor:
                      "pointer",
                    color:
                      "var(--fg)",
                    fontSize: 12,
                    textAlign:
                      "left",
                  }}
                >
                  <GitBranch
                    size={12}
                    style={{
                      opacity:
                        0.5,
                    }}
                  />

                  <span
                    style={{
                      flex: 1,
                    }}
                  >
                    {item.name}
                  </span>

                  {item.is_default && (
                    <span
                      style={{
                        fontSize: 10,
                        opacity: 0.5,
                        fontFamily:
                          "monospace",
                      }}
                    >
                      default
                    </span>
                  )}

                  {item.name ===
                    current && (
                    <Check
                      size={12}
                      className="cyan"
                    />
                  )}
                </button>
              ),
            )}

            {filtered.length ===
              0 && (
              <div
                style={{
                  padding:
                    "12px",
                  fontSize: 12,
                  opacity: 0.5,
                  textAlign:
                    "center",
                }}
              >
                No branches found
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

// ─── File Tree ───────────────────────────────────────────────────────────────

function FileTree({
  entries,
  currentPath,
  onSelect,
  owner,
  repo,
  branch,
}: {
  entries: TreeEntry[];
  currentPath: string;
  onSelect: (
    entry: TreeEntry,
  ) => void;
  owner: string;
  repo: string;
  branch: string;
}) {
  const [expanded, setExpanded] =
    useState<
      Record<
        string,
        TreeEntry[]
      >
    >({});

  const [loading, setLoading] =
    useState<
      Record<
        string,
        boolean
      >
    >({});

  const toggleDir = async (
    entry: TreeEntry,
  ) => {
    if (expanded[entry.path]) {
      setExpanded(
        (previous) => {
          const next = {
            ...previous,
          };

          delete next[
            entry.path
          ];

          return next;
        },
      );

      return;
    }

    setLoading(
      (previous) => ({
        ...previous,
        [entry.path]: true,
      }),
    );

    try {
      const treeKey = `tree:${owner.toLowerCase()}/${repo.toLowerCase()}:${branch}:${entry.path}`;
      const data =
        await clientCache.fetch<{
          entries: TreeEntry[];
        }>(
          treeKey,
          () =>
            apiAuth<{
              entries: TreeEntry[];
            }>(
              `/v1/repositories/${owner}/${repo}/tree?ref=${encodeURIComponent(
                branch,
              )}&path=${encodeURIComponent(
                entry.path,
              )}`,
            ),
          CACHE_TTL.TREE
        );

      setExpanded(
        (previous) => ({
          ...previous,
          [entry.path]:
            data.entries || [],
        }),
      );
    } catch {
      // Ignore directory expansion
      // failures in the tree.
    } finally {
      setLoading(
        (previous) => ({
          ...previous,
          [entry.path]: false,
        }),
      );
    }
  };

  function renderEntries(
    list: TreeEntry[],
    depth = 0,
  ): React.ReactNode {
    return list.map(
      (entry) => (
        <div key={entry.path}>
          <div
            onClick={() =>
              entry.type ===
              "directory"
                ? toggleDir(
                    entry,
                  )
                : onSelect(
                    entry,
                  )
            }
            style={{
              display: "flex",
              alignItems:
                "center",
              gap: 6,
              padding: `5px 10px 5px ${
                10 + depth * 16
              }px`,
              cursor:
                "pointer",
              fontSize: 13,
              background:
                entry.path ===
                currentPath
                  ? "rgba(99,179,237,0.1)"
                  : "transparent",
              color:
                entry.path ===
                currentPath
                  ? "var(--cyan)"
                  : "var(--fg)",
              borderLeft:
                entry.path ===
                currentPath
                  ? "2px solid var(--cyan)"
                  : "2px solid transparent",
              transition:
                "all 0.15s",
            }}
            className="tree-row"
          >
            {entry.type ===
            "directory" ? (
              <>
                {loading[
                  entry.path
                ] ? (
                  <span
                    style={{
                      fontSize: 10,
                      opacity: 0.5,
                    }}
                  >
                    ⋯
                  </span>
                ) : expanded[
                    entry.path
                  ] ? (
                  <ChevronDown
                    size={12}
                    style={{
                      opacity:
                        0.5,
                    }}
                  />
                ) : (
                  <ChevronRight
                    size={12}
                    style={{
                      opacity:
                        0.5,
                    }}
                  />
                )}

                <Folder
                  size={13}
                  style={{
                    color:
                      "#e6be8a",
                  }}
                />
              </>
            ) : (
              <>
                <span
                  style={{
                    width: 12,
                  }}
                />

                <FileCode2
                  size={13}
                  style={{
                    opacity: 0.6,
                  }}
                />
              </>
            )}

            <span
              style={{
                flex: 1,
                overflow:
                  "hidden",
                textOverflow:
                  "ellipsis",
                whiteSpace:
                  "nowrap",
              }}
            >
              {entry.name}
            </span>

            {entry.size !==
              undefined &&
              entry.type ===
                "file" && (
                <span
                  style={{
                    fontSize: 10,
                    opacity: 0.4,
                  }}
                >
                  {formatSize(
                    entry.size,
                  )}
                </span>
              )}
          </div>

          {expanded[
            entry.path
          ] &&
            renderEntries(
              expanded[
                entry.path
              ],
              depth + 1,
            )}
        </div>
      ),
    );
  }

  return (
    <div>
      {renderEntries(entries)}
    </div>
  );
}

// ─── Inline Comment Thread ───────────────────────────────────────────────────

function CommentThread({
  lineNo,
  comments,
  onAdd,
  onResolve,
  currentUser,
}: {
  lineNo: number;
  comments: InlineComment[];
  onAdd: (
    lineNo: number,
    body: string,
  ) => void;
  onResolve: (
    id: string,
  ) => void;
  currentUser: string;
}) {
  const [reply, setReply] =
    useState("");

  const [submitting, setSubmitting] =
    useState(false);

  const handleSubmit =
    async () => {
      if (!reply.trim()) {
        return;
      }

      setSubmitting(true);

      await onAdd(
        lineNo,
        reply,
      );

      setReply("");
      setSubmitting(false);
    };

  return (
    <div
      style={{
        margin:
          "0 0 2px 0",
        borderRadius: 6,
        background:
          "rgba(255,234,128,0.05)",
        border:
          "1px solid rgba(255,234,128,0.15)",
        fontSize: 13,
        overflow:
          "hidden",
      }}
    >
      {comments.map(
        (comment) => (
          <div
            key={comment.id}
            style={{
              padding:
                "10px 14px",
              borderBottom:
                "1px solid rgba(255,255,255,0.05)",
            }}
          >
            <div
              style={{
                display:
                  "flex",
                alignItems:
                  "center",
                gap: 8,
                marginBottom: 6,
              }}
            >
              <div
                style={{
                  width: 22,
                  height: 22,
                  borderRadius:
                    "50%",
                  background:
                    "var(--bg-card)",
                  display:
                    "flex",
                  alignItems:
                    "center",
                  justifyContent:
                    "center",
                  fontSize: 10,
                  fontWeight:
                    600,
                }}
              >
                {comment.author_id
                  .slice(
                    0,
                    1,
                  )
                  .toUpperCase()}
              </div>

              <span
                style={{
                  fontWeight:
                    500,
                  fontSize: 12,
                }}
              >
                {comment.author_id.slice(
                  0,
                  12,
                )}
              </span>

              <span
                style={{
                  fontSize: 11,
                  opacity: 0.5,
                }}
              >
                {timeSince(
                  comment.created_at,
                )}
              </span>

              {comment.status ===
                "resolved" && (
                <span
                  style={{
                    marginLeft:
                      "auto",
                    fontSize: 11,
                    color:
                      "var(--green)",
                  }}
                >
                  ✓ Resolved
                </span>
              )}

              {comment.status !==
                "resolved" &&
                comment.author_id ===
                  currentUser && (
                  <button
                    onClick={() =>
                      onResolve(
                        comment.id,
                      )
                    }
                    style={{
                      marginLeft:
                        "auto",
                      background:
                        "none",
                      border:
                        "1px solid var(--line)",
                      borderRadius:
                        4,
                      padding:
                        "2px 8px",
                      fontSize: 11,
                      cursor:
                        "pointer",
                      color:
                        "var(--fg)",
                    }}
                  >
                    Resolve
                  </button>
                )}
            </div>

            <div
              style={{
                paddingLeft:
                  30,
                lineHeight:
                  1.6,
                opacity:
                  comment.status ===
                  "resolved"
                    ? 0.5
                    : 1,
              }}
            >
              {comment.body}
            </div>
          </div>
        ),
      )}

      <div
        style={{
          padding:
            "8px 14px",
          display:
            "flex",
          gap: 8,
        }}
      >
        <input
          value={reply}
          onChange={(event) =>
            setReply(
              event.target.value,
            )
          }
          onKeyDown={(event) => {
            if (
              event.key ===
                "Enter" &&
              !event.shiftKey
            ) {
              void handleSubmit();
            }
          }}
          placeholder="Leave a comment..."
          style={{
            flex: 1,
            background:
              "var(--bg-page)",
            border:
              "1px solid var(--line)",
            borderRadius: 4,
            padding:
              "6px 10px",
            color:
              "var(--fg)",
            fontSize: 12,
            outline:
              "none",
          }}
        />

        <button
          onClick={() =>
            void handleSubmit()
          }
          disabled={
            !reply.trim() ||
            submitting
          }
          style={{
            padding:
              "6px 12px",
            background:
              "var(--accent)",
            color: "#fff",
            border: "none",
            borderRadius:
              4,
            cursor:
              "pointer",
            fontSize: 12,
            opacity:
              !reply.trim() ||
              submitting
                ? 0.5
                : 1,
          }}
        >
          <Send size={12} />
        </button>
      </div>
    </div>
  );
}

// ─── Provenance Details ──────────────────────────────────────────────────────

function ProvenanceDetails({
  range,
}: {
  range: BlameRange;
}) {
  const provenance =
    range.provenance;

  const color =
    provenanceColor(
      provenance,
    );

  return (
    <div
      style={{
        marginTop: 6,
        padding: 10,
        borderRadius: 6,
        background:
          "var(--bg-page)",
        border:
          `1px solid ${color}33`,
        fontSize: 10,
        textAlign: "left",
        fontFamily:
          "DM Sans, system-ui, sans-serif",
      }}
    >
      <div
        style={{
          display:
            "flex",
          justifyContent:
            "space-between",
          alignItems:
            "center",
          gap: 8,
          marginBottom: 8,
        }}
      >
        <strong
          style={{
            color,
          }}
        >
          {provenanceLabel(
            provenance,
          )}
        </strong>

        <code
          style={{
            opacity: 0.55,
            fontSize: 9,
          }}
        >
          {range.short_commit}
        </code>
      </div>

      <div
        style={{
          display:
            "grid",
          gridTemplateColumns:
            "72px 1fr",
          rowGap: 4,
          columnGap: 8,
          lineHeight: 1.4,
        }}
      >
        <span
          style={{
            opacity: 0.45,
          }}
        >
          Identity
        </span>

        <span>
          {provenance.identity_type}
        </span>

        <span
          style={{
            opacity: 0.45,
          }}
        >
          Author
        </span>

        <span
          style={{
            wordBreak:
              "break-word",
          }}
        >
          {range.author_name ||
            "Unknown"}
        </span>

        {provenance.agent && (
          <>
            <span
              style={{
                opacity: 0.45,
              }}
            >
              Agent
            </span>

            <span>
              {provenance.agent.name}
            </span>

            <span
              style={{
                opacity: 0.45,
              }}
            >
              Model
            </span>

            <span>
              {provenance.agent.model ||
                "—"}
            </span>

            <span
              style={{
                opacity: 0.45,
              }}
            >
              Provider
            </span>

            <span>
              {provenance.agent.provider ||
                "—"}
            </span>
          </>
        )}

        {provenance.task && (
          <>
            <span
              style={{
                opacity: 0.45,
              }}
            >
              Task
            </span>

            <span>
              {provenance.task.title}
            </span>

            <span
              style={{
                opacity: 0.45,
              }}
            >
              Task ID
            </span>

            <code
              style={{
                fontSize: 9,
                opacity: 0.8,
              }}
            >
              {provenance.task.id}
            </code>

            <span
              style={{
                opacity: 0.45,
              }}
            >
              Status
            </span>

            <span>
              {provenance.task.status}
            </span>
          </>
        )}

        {provenance.session && (
          <>
            <span
              style={{
                opacity: 0.45,
              }}
            >
              Session
            </span>

            <code
              style={{
                fontSize: 9,
                opacity: 0.8,
              }}
            >
              {provenance.session.id}
            </code>

            <span
              style={{
                opacity: 0.45,
              }}
            >
              Session status
            </span>

            <span>
              {provenance.session.status}
            </span>
          </>
        )}

        {provenance.change_id && (
          <>
            <span
              style={{
                opacity: 0.45,
              }}
            >
              Change
            </span>

            <code
              style={{
                fontSize: 9,
                opacity: 0.8,
              }}
            >
              {provenance.change_id}
            </code>
          </>
        )}
      </div>

      <div
        style={{
          marginTop: 8,
          paddingTop: 7,
          borderTop:
            "1px solid var(--line)",
          opacity: 0.45,
          fontSize: 9,
        }}
      >
        Lines {range.start_line}
        {range.end_line !==
        range.start_line
          ? `–${range.end_line}`
          : ""}
        {" · "}
        {range.subject}
      </div>
    </div>
  );
}

// ─── Code Viewer ─────────────────────────────────────────────────────────────

function CodeViewer({
  file,
  comments,
  onAddComment,
  onResolveComment,
  currentUser,
  blameRanges,
}: {
  file: FileContent;
  comments: InlineComment[];
  onAddComment: (
    lineNo: number,
    body: string,
  ) => void;
  onResolveComment: (
    id: string,
  ) => void;
  currentUser: string;
  blameRanges: BlameRange[];
}) {
  const [hoveredLine, setHoveredLine] =
    useState<number | null>(
      null,
    );

  const [activeLines, setActiveLines] =
    useState<Set<number>>(
      new Set(),
    );

  const [
    provenanceLine,
    setProvenanceLine,
  ] = useState<
    number | null
  >(null);

  const [copied, setCopied] =
    useState(false);

  const lang =
    detectLang(file.path);

  const lines =
    file.content.split("\n");

  const commentsPerLine: Record<
    number,
    InlineComment[]
  > = {};

  comments.forEach(
    (comment) => {
      if (comment.line_number) {
        commentsPerLine[
          comment.line_number
        ] =
          commentsPerLine[
            comment.line_number
          ] || [];

        commentsPerLine[
          comment.line_number
        ].push(comment);
      }
    },
  );

  const toggleLineComment = (
    lineNo: number,
  ) => {
    setActiveLines(
      (previous) => {
        const next = new Set(
          previous,
        );

        if (
          next.has(lineNo)
        ) {
          next.delete(
            lineNo,
          );
        } else {
          next.add(lineNo);
        }

        return next;
      },
    );
  };

  const copyAll = () => {
    void navigator.clipboard.writeText(
      file.content,
    );

    setCopied(true);

    window.setTimeout(
      () => setCopied(false),
      1500,
    );
  };

  return (
    <div
      style={{
        display:
          "flex",
        flexDirection:
          "column",
        height: "100%",
      }}
    >
      {/* File toolbar */}
      <div
        style={{
          display:
            "flex",
          alignItems:
            "center",
          gap: 10,
          padding:
            "8px 14px",
          borderBottom:
            "1px solid var(--line)",
          background:
            "var(--bg-card)",
          flexShrink: 0,
        }}
      >
        <span
          style={{
            fontSize: 12,
            fontFamily:
              "monospace",
            opacity: 0.7,
          }}
        >
          {file.path}
        </span>

        <span
          style={{
            fontSize: 11,
            opacity: 0.4,
          }}
        >
          {formatSize(
            file.size,
          )}
        </span>

        <span
          style={{
            fontSize: 11,
            opacity: 0.4,
          }}
        >
          {lines.length} lines
        </span>

        <span
          style={{
            fontSize: 11,
            opacity: 0.4,
            fontFamily:
              "monospace",
          }}
        >
          {lang}
        </span>

        <div
          style={{
            marginLeft:
              "auto",
            display:
              "flex",
            gap: 6,
          }}
        >
          <button
            onClick={copyAll}
            title="Copy file"
            style={{
              display:
                "flex",
              alignItems:
                "center",
              gap: 5,
              padding:
                "4px 10px",
              background:
                "var(--bg-page)",
              border:
                "1px solid var(--line)",
              borderRadius: 4,
              cursor:
                "pointer",
              color:
                "var(--fg)",
              fontSize: 12,
            }}
          >
            {copied ? (
              <>
                <Check
                  size={12}
                />
                Copied
              </>
            ) : (
              <>
                <Copy
                  size={12}
                />
                Copy
              </>
            )}
          </button>
        </div>
      </div>

      {/* Provenance legend */}
      <div
        style={{
          display:
            "flex",
          alignItems:
            "center",
          gap: 14,
          padding:
            "6px 14px",
          borderBottom:
            "1px solid var(--line)",
          background:
            "rgba(255,255,255,0.015)",
          fontSize: 11,
          flexShrink: 0,
        }}
      >
        <span
          style={{
            opacity: 0.45,
            textTransform:
              "uppercase",
            letterSpacing:
              "0.06em",
            fontWeight:
              600,
          }}
        >
          Provenance
        </span>

        <span>
          🤖 SUTRA Agent
        </span>

        <span>
          👤 SUTRA Human
        </span>

        <span>
          ◉ GitHub
        </span>

        <span
          style={{
            marginLeft:
              "auto",
            opacity: 0.4,
            fontSize: 10,
          }}
        >
          Click a provenance badge
          for details
        </span>
      </div>

      {/* Code */}
      <div
        style={{
          flex: 1,
          overflowY:
            "auto",
          fontFamily:
            "monospace",
          fontSize: 13,
        }}
      >
        <table
          style={{
            width: "100%",
            borderCollapse:
              "collapse",
          }}
        >
          <tbody>
            {lines.map(
              (line, i) => {
                const lineNo =
                  i + 1;

                const range =
                  provenanceForLine(
                    blameRanges,
                    lineNo,
                  );

                const provenance =
                  range?.provenance;

                const hasComments =
                  !!commentsPerLine[
                    lineNo
                  ]?.length;

                const isActive =
                  activeLines.has(
                    lineNo,
                  );

                const isHovered =
                  hoveredLine ===
                  lineNo;

                const isProvenanceOpen =
                  provenanceLine ===
                  lineNo;

                return (
                  <React.Fragment
                    key={
                      lineNo
                    }
                  >
                    <tr
                      onMouseEnter={() =>
                        setHoveredLine(
                          lineNo,
                        )
                      }
                      onMouseLeave={() =>
                        setHoveredLine(
                          null,
                        )
                      }
                      style={{
                        background:
                          hasComments
                            ? "rgba(255,234,128,0.04)"
                            : isActive
                              ? "rgba(99,179,237,0.06)"
                              : "transparent",
                      }}
                    >
                      {/* Line number */}
                      <td
                        style={{
                          width: 50,
                          minWidth: 50,
                          textAlign:
                            "right",
                          padding:
                            "1px 12px 1px 0",
                          userSelect:
                            "none",
                          color:
                            "var(--muted)",
                          fontSize: 12,
                          borderRight:
                            "1px solid var(--line)",
                          verticalAlign:
                            "top",
                        }}
                      >
                        {lineNo}
                      </td>

                      {/* Comment control */}
                      <td
                        style={{
                          width: 24,
                          padding:
                            "1px 4px",
                          verticalAlign:
                            "top",
                        }}
                      >
                        {(
                          isHovered ||
                          hasComments
                        ) && (
                          <button
                            onClick={() =>
                              toggleLineComment(
                                lineNo,
                              )
                            }
                            title="Add comment"
                            style={{
                              background:
                                "none",
                              border:
                                "none",
                              cursor:
                                "pointer",
                              padding:
                                "0 2px",
                              color:
                                hasComments
                                  ? "var(--cyan)"
                                  : "var(--muted)",
                              opacity:
                                hasComments
                                  ? 1
                                  : 0.6,
                            }}
                          >
                            <MessageSquare
                              size={11}
                            />
                          </button>
                        )}
                      </td>

                      {/* Code */}
                      <td
                        style={{
                          padding:
                            "1px 0 1px 8px",
                          whiteSpace:
                            "pre",
                          overflowX:
                            "auto",
                          position:
                            "relative",
                        }}
                      >
                        <span
                          dangerouslySetInnerHTML={{
                            __html:
                              highlightLine(
                                line,
                                lang,
                              ),
                          }}
                        />
                      </td>

                      {/* Provenance */}
                      <td
                        style={{
                          width: 230,
                          minWidth: 230,
                          padding:
                            "1px 12px 1px 10px",
                          verticalAlign:
                            "top",
                          textAlign:
                            "right",
                          position:
                            "relative",
                        }}
                      >
                        {provenance &&
                          range && (
                            <div
                              style={{
                                display:
                                  "inline-flex",
                                flexDirection:
                                  "column",
                                alignItems:
                                  "flex-end",
                                maxWidth:
                                  220,
                              }}
                            >
                              <button
                                onClick={() =>
                                  setProvenanceLine(
                                    (
                                      previous,
                                    ) =>
                                      previous ===
                                      lineNo
                                        ? null
                                        : lineNo,
                                  )
                                }
                                title={`${range.subject} · ${range.short_commit}`}
                                style={{
                                  display:
                                    "inline-flex",
                                  alignItems:
                                    "center",
                                  gap: 6,
                                  maxWidth:
                                    210,
                                  padding:
                                    "2px 7px",
                                  borderRadius:
                                    5,
                                  border: `1px solid ${provenanceColor(provenance)}33`,
                                  background: `${provenanceColor(provenance)}0d`,
                                  color:
                                    provenanceColor(
                                      provenance,
                                    ),
                                  fontSize:
                                    10,
                                  whiteSpace:
                                    "nowrap",
                                  overflow:
                                    "hidden",
                                  textOverflow:
                                    "ellipsis",
                                  opacity:
                                    isHovered ||
                                    isProvenanceOpen
                                      ? 1
                                      : 0.75,
                                  cursor:
                                    "pointer",
                                }}
                              >
                                <span>
                                  {provenanceIcon(
                                    provenance,
                                  )}
                                </span>

                                <span
                                  style={{
                                    overflow:
                                      "hidden",
                                    textOverflow:
                                      "ellipsis",
                                  }}
                                >
                                  {provenanceLabel(
                                    provenance,
                                  )}
                                </span>

                                <span
                                  style={{
                                    opacity:
                                      0.55,
                                  }}
                                >
                                  {range.short_commit}
                                </span>
                              </button>

                              {isProvenanceOpen && (
                                <ProvenanceDetails
                                  range={
                                    range
                                  }
                                />
                              )}
                            </div>
                          )}
                      </td>
                    </tr>

                    {(isActive ||
                      hasComments) && (
                      <tr>
                        <td />
                        <td
                          colSpan={3}
                          style={{
                            padding:
                              "4px 8px 4px 30px",
                          }}
                        >
                          <CommentThread
                            lineNo={
                              lineNo
                            }
                            comments={
                              commentsPerLine[
                                lineNo
                              ] ||
                              []
                            }
                            onAdd={
                              onAddComment
                            }
                            onResolve={
                              onResolveComment
                            }
                            currentUser={
                              currentUser
                            }
                          />
                        </td>
                      </tr>
                    )}
                  </React.Fragment>
                );
              },
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// ─── Commit History Panel ─────────────────────────────────────────────────────

function CommitsPanel({
  commits,
  repoName,
}: {
  commits: Commit[];
  repoName: string;
}) {
  const router =
    useRouter();

  return (
    <div
      style={{
        height: "100%",
        overflowY: "auto",
      }}
    >
      {commits.length === 0 && (
        <div
          style={{
            padding: 30,
            textAlign:
              "center",
            opacity: 0.5,
            fontSize: 13,
          }}
        >
          No commits yet
        </div>
      )}

      {commits.map(
        (commit) => (
          <div
            key={commit.sha}
            onClick={() =>
              router.push(
                `/repositories/${repoName}/commits/${commit.sha}`,
              )
            }
            style={{
              borderBottom:
                "1px solid var(--line)",
              padding:
                "14px 16px",
              cursor:
                "pointer",
              transition:
                "background 0.15s",
            }}
            className="commit-row"
          >
            <div
              style={{
                display:
                  "flex",
                alignItems:
                  "flex-start",
                gap: 12,
              }}
            >
              <div
                style={{
                  width: 32,
                  height: 32,
                  borderRadius:
                    "50%",
                  background:
                    "var(--bg-page)",
                  border:
                    "1px solid var(--line)",
                  display:
                    "flex",
                  alignItems:
                    "center",
                  justifyContent:
                    "center",
                  flexShrink: 0,
                }}
              >
                <GitCommit
                  size={14}
                />
              </div>

              <div
                style={{
                  flex: 1,
                  minWidth: 0,
                }}
              >
                <div
                  style={{
                    fontWeight:
                      500,
                    fontSize: 13,
                    lineHeight:
                      1.45,
                    wordBreak:
                      "break-word",
                  }}
                >
                  {
                    commit.subject
                  }
                </div>

                <div
                  style={{
                    display:
                      "flex",
                    alignItems:
                      "center",
                    gap: 10,
                    marginTop: 5,
                    flexWrap:
                      "wrap",
                  }}
                >
                  <span
                    style={{
                      fontSize: 11,
                      opacity:
                        0.65,
                    }}
                  >
                    {
                      commit.author_name
                    }
                  </span>

                  <span
                    style={{
                      fontSize: 11,
                      opacity:
                        0.4,
                    }}
                  >
                    {timeSince(
                      new Date(
                        commit.committed_at *
                          1000,
                      ).toISOString(),
                    )}
                  </span>

                  <code
                    style={{
                      fontSize: 11,
                      fontFamily:
                        "monospace",
                      background:
                        "var(--bg-page)",
                      padding:
                        "1px 6px",
                      borderRadius:
                        3,
                      border:
                        "1px solid var(--line)",
                      opacity:
                        0.7,
                    }}
                  >
                    {commit.sha.slice(
                      0,
                      7,
                    )}
                  </code>
                </div>
              </div>

              <div
                style={{
                  opacity:
                    0.3,
                  fontSize: 12,
                  paddingTop: 2,
                }}
              >
                →
              </div>
            </div>
          </div>
        ),
      )}
    </div>
  );
}

// ─── Main Page ────────────────────────────────────────────────────────────────

export default function CodePage({
  params,
}: {
  params: Promise<{
    name: string;
  }>;
}) {
  const {
    name: repoName,
  } = use(params);

  const searchParams =
    useSearchParams();

  const router =
    useRouter();

  const [
    owner,
    setOwner,
  ] = useState("");

  const [
    branches,
    setBranches,
  ] = useState<Branch[]>(
    [],
  );

  const [
    branch,
    setBranch,
  ] = useState(
    searchParams.get(
      "ref",
    ) || "",
  );

  const [
    tree,
    setTree,
  ] = useState<TreeEntry[]>(
    [],
  );

  const [
    selectedFile,
    setSelectedFile,
  ] = useState<
    FileContent | null
  >(null);

  const [
    selectedPath,
    setSelectedPath,
  ] = useState(
    searchParams.get(
      "path",
    ) || "",
  );

  const [
    blameRanges,
    setBlameRanges,
  ] = useState<
    BlameRange[]
  >([]);

  const [
    loadingBlame,
    setLoadingBlame,
  ] = useState(false);

  const [
    commits,
    setCommits,
  ] = useState<Commit[]>(
    [],
  );

  const [
    loadingTree,
    setLoadingTree,
  ] = useState(true);

  const [
    loadingFile,
    setLoadingFile,
  ] = useState(false);

  const [
    loadingCommits,
    setLoadingCommits,
  ] = useState(false);

  const [
    view,
    setView,
  ] = useState<
    "files" | "commits"
  >("files");

  const [
    comments,
    setComments,
  ] = useState<
    InlineComment[]
  >([]);

  const [
    error,
    setError,
  ] = useState("");

  const [
    breadcrumbs,
    setBreadcrumbs,
  ] = useState<
    string[]
  >([]);

  const [
    showCloneDropdown,
    setShowCloneDropdown,
  ] = useState(false);

  const [
    copiedClone,
    setCopiedClone,
  ] = useState(false);

  const dropdownRef =
    useRef<HTMLDivElement>(
      null,
    );

  useEffect(() => {
    function handleClickOutside(
      event: MouseEvent,
    ) {
      if (
        dropdownRef.current &&
        !dropdownRef.current.contains(
          event.target as Node,
        )
      ) {
        setShowCloneDropdown(
          false,
        );
      }
    }

    document.addEventListener(
      "mousedown",
      handleClickOutside,
    );

    return () =>
      document.removeEventListener(
        "mousedown",
        handleClickOutside,
      );
  }, []);

  // ─── Load current user ─────────────────────────────────────

  useEffect(() => {
    authService
      .getCurrentUser()
      .then((user) => {
        setOwner(
          user.username,
        );
      })
      .catch(() => {});
  }, []);

  // ─── Load branches ─────────────────────────────────────────

  useEffect(() => {
    if (!owner) {
      return;
    }

    repositoryService.getBranches(owner, repoName)
      .then((data) => {
        const branchList: Branch[] = (data.branches || []).map((b) => ({
          name: b.name,
          commit: b.commit,
          protected: !!b.protected,
        }));

        setBranches(
          branchList,
        );

        if (
          !searchParams.get(
            "ref",
          )
        ) {
          const defaultBranch =
            data.default_branch ||
            branchList.find(
              (item) =>
                item.protected,
            )?.name ||
            branchList[0]
              ?.name ||
            "main";

          setBranch(
            defaultBranch,
          );
        }
      })
      .catch((err: unknown) => {
        setError(
          err instanceof Error
            ? err.message
            : "Failed to load branches",
        );
      });
  }, [
    owner,
    repoName,
    searchParams,
  ]);

  // ─── Load commits ──────────────────────────────────────────

  const loadCommitsRef =
    useRef<
      ((
        overrideBranch?: string,
      ) => Promise<void>
    ) | null
    >(null);

  loadCommitsRef.current =
    async (
      overrideBranch?: string,
    ) => {
      if (
        !owner ||
        !overrideBranch &&
          !branch
      ) {
        return;
      }

      const selectedBranch =
        overrideBranch ||
        branch;

      setLoadingCommits(
        true,
      );

      try {
        const commitKey = `commits:${owner.toLowerCase()}/${repoName.toLowerCase()}:${selectedBranch}:50`;
        const data =
          await clientCache.fetch<{
            commits: Commit[];
          }>(
            commitKey,
            () =>
              apiAuth<{
                commits: Commit[];
              }>(
                `/v1/repositories/${owner}/${repoName}/commits?ref=${encodeURIComponent(
                  selectedBranch,
                )}&limit=50`,
              ),
            CACHE_TTL.COMMITS
          );

        setCommits(
          data.commits || [],
        );
      } catch (err: any) {
        if (
          err?.message?.includes(
            "Git ref not found",
          )
        ) {
          setCommits([]);
        } else {
          setError(
            err?.message ||
              "Failed to load commits",
          );
        }
      } finally {
        setLoadingCommits(
          false,
        );
      }
    };

  const loadCommits =
    useCallback(
      (
        overrideBranch?: string,
      ) =>
        loadCommitsRef.current?.(
          overrideBranch,
        ) ??
        Promise.resolve(),
      [],
    );

  useEffect(() => {
    if (
      owner &&
      branch
    ) {
      void loadCommits();
    }
  }, [
    owner,
    branch,
    loadCommits,
  ]);

  // ─── Load tree ──────────────────────────────────────────────

  useEffect(() => {
    if (
      !owner ||
      !branch
    ) {
      return;
    }

    setLoadingTree(true);
    setError("");

    const treeKey = `tree:${owner.toLowerCase()}/${repoName.toLowerCase()}:${branch}:root`;
    clientCache
      .fetch<{
        entries: TreeEntry[];
      }>(
        treeKey,
        () =>
          apiAuth<{
            entries: TreeEntry[];
          }>(
            `/v1/repositories/${owner}/${repoName}/tree?ref=${encodeURIComponent(
              branch,
            )}`,
          ),
        CACHE_TTL.TREE
      )
      .then((data) => {
        setTree(
          data.entries || [],
        );
      })
      .catch((err: any) => {
        if (
          err?.message?.includes(
            "Git ref not found",
          )
        ) {
          setTree([]);
        } else {
          setError(
            err?.message ||
              "Failed to load repository tree",
          );
        }
      })
      .finally(() => {
        setLoadingTree(
          false,
        );
      });
  }, [
    owner,
    repoName,
    branch,
  ]);

  // ─── Open file + blame ─────────────────────────────────────

  const openFile =
    useCallback(
      async (
        entry: TreeEntry,
      ) => {
        if (
          entry.type !==
          "file"
        ) {
          return;
        }

        setLoadingFile(
          true,
        );

        setLoadingBlame(
          true,
        );

        setSelectedPath(
          entry.path,
        );

        setBreadcrumbs(
          entry.path.split(
            "/",
          ),
        );

        setComments([]);
        setBlameRanges([]);
        setSelectedFile(null);
        setError("");

        const fileUrl =
          `/v1/repositories/${owner}/${repoName}/file?path=${encodeURIComponent(
            entry.path,
          )}&ref=${encodeURIComponent(
            branch,
          )}`;

        const blameUrl =
          `/v1/repositories/${owner}/${repoName}/blame?path=${encodeURIComponent(
            entry.path,
          )}&ref=${encodeURIComponent(
            branch,
          )}`;

        const fileKey = `file:${owner.toLowerCase()}/${repoName.toLowerCase()}:${branch}:${entry.path}`;
        const blameKey = `blame:${owner.toLowerCase()}/${repoName.toLowerCase()}:${branch}:${entry.path}`;

        try {
          const filePromise = clientCache.fetch<FileContent>(
            fileKey,
            () => apiAuth<FileContent>(fileUrl),
            CACHE_TTL.FILE
          );

          const blamePromise = clientCache.fetch<BlameResponse | null>(
            blameKey,
            () =>
              apiAuth<BlameResponse>(blameUrl).catch(() => null),
            CACHE_TTL.FILE
          );

          const [
            fileData,
            blameData,
          ] =
            await Promise.all([
              filePromise,
              blamePromise,
            ]);

          setSelectedFile(
            {
              ...fileData,
            },
          );

          if (
            blameData
          ) {
            setBlameRanges(
              blameData.ranges ||
                [],
            );
          } else {
            setBlameRanges(
              [],
            );
          }
        } catch (err: any) {
          setSelectedFile(
            null,
          );
          setBlameRanges(
            [],
          );
          setError(
            err?.message ||
              "Failed to load file",
          );
        } finally {
          setLoadingFile(
            false,
          );
          setLoadingBlame(
            false,
          );
        }
      },
      [
        owner,
        repoName,
        branch,
      ],
    );

  useEffect(() => {
    if (
      view ===
      "commits"
    ) {
      void loadCommits();
    }
  }, [
    view,
    loadCommits,
  ]);

  // ─── Branch change ─────────────────────────────────────────

  const handleBranchChange =
    (nextBranch: string) => {
      setBranch(
        nextBranch,
      );
      setSelectedFile(
        null,
      );
      setBlameRanges(
        [],
      );
      setSelectedPath(
        "",
      );
      setBreadcrumbs(
        [],
      );
      setComments([]);
      setError("");

      router.replace(
        `/repositories/${repoName}/code?ref=${encodeURIComponent(
          nextBranch,
        )}`,
      );
    };

  // ─── Comments ──────────────────────────────────────────────

  const handleAddComment =
    async (
      lineNo: number,
      body: string,
    ) => {
      const newComment: InlineComment =
        {
          id: crypto.randomUUID(),
          line_number: lineNo,
          body,
          author_id:
            owner,
          status: "active",
          created_at:
            new Date().toISOString(),
        };

      setComments(
        (previous) => [
          ...previous,
          newComment,
        ],
      );
    };

  const handleResolveComment =
    async (
      id: string,
    ) => {
      setComments(
        (previous) =>
          previous.map(
            (comment) =>
              comment.id ===
              id
                ? {
                    ...comment,
                    status:
                      "resolved",
                  }
                : comment,
          ),
      );
    };

  return (
    <AppShell>
      <div
        style={{
          display:
            "flex",
          flexDirection:
            "column",
          height:
            "calc(100vh - 56px)",
          overflow:
            "hidden",
        }}
      >
        {/* Top bar */}
        <div
          style={{
            display:
              "flex",
            alignItems:
              "center",
            gap: 10,
            padding:
              "10px 20px",
            borderBottom:
              "1px solid var(--line)",
            background:
              "var(--bg-card)",
            flexShrink: 0,
          }}
        >
          <BranchSwitcher
            branches={
              branches
            }
            current={
              branch
            }
            onChange={
              handleBranchChange
            }
          />

          {/* Breadcrumbs */}
          {breadcrumbs.length >
            0 && (
            <div
              style={{
                display:
                  "flex",
                alignItems:
                  "center",
                gap: 4,
                fontSize: 13,
                minWidth: 0,
              }}
            >
              <button
                onClick={() => {
                  setSelectedFile(
                    null,
                  );
                  setSelectedPath(
                    "",
                  );
                  setBlameRanges(
                    [],
                  );
                  setBreadcrumbs(
                    [],
                  );
                  setComments(
                    [],
                  );
                }}
                style={{
                  background:
                    "none",
                  border:
                    "none",
                  color:
                    "var(--cyan)",
                  cursor:
                    "pointer",
                  padding: 0,
                }}
              >
                {repoName}
              </button>

              {breadcrumbs.map(
                (
                  segment,
                  index,
                ) => (
                  <span
                    key={
                      `${segment}-${index}`
                    }
                    style={{
                      display:
                        "flex",
                      alignItems:
                        "center",
                      gap: 4,
                      minWidth: 0,
                    }}
                  >
                    <span
                      style={{
                        opacity:
                          0.4,
                      }}
                    >
                      /
                    </span>

                    <span
                      style={{
                        opacity:
                          index ===
                          breadcrumbs.length -
                            1
                            ? 1
                            : 0.6,
                        overflow:
                          "hidden",
                        textOverflow:
                          "ellipsis",
                        whiteSpace:
                          "nowrap",
                      }}
                    >
                      {
                        segment
                      }
                    </span>
                  </span>
                ),
              )}
            </div>
          )}

          <div
            style={{
              marginLeft:
                "auto",
              display:
                "flex",
              gap: 6,
            }}
          >
            <button
              onClick={() =>
                setView(
                  "files",
                )
              }
              style={{
                padding:
                  "5px 12px",
                borderRadius:
                  5,
                fontSize: 12,
                cursor:
                  "pointer",
                background:
                  view ===
                  "files"
                    ? "var(--accent)"
                    : "var(--bg-page)",
                border:
                  "1px solid var(--line)",
                color:
                  view ===
                  "files"
                    ? "#fff"
                    : "var(--fg)",
              }}
            >
              Files
            </button>

            <button
              onClick={() =>
                setView(
                  "commits",
                )
              }
              style={{
                display:
                  "flex",
                alignItems:
                  "center",
                gap: 6,
                padding:
                  "5px 12px",
                borderRadius:
                  5,
                fontSize: 12,
                cursor:
                  "pointer",
                background:
                  view ===
                  "commits"
                    ? "linear-gradient(135deg, var(--violet), var(--aqua))"
                    : "var(--bg-page)",
                border:
                  "1px solid var(--line)",
                color:
                  view ===
                  "commits"
                    ? "#fff"
                    : "var(--fg)",
                fontWeight:
                  view ===
                  "commits"
                    ? 600
                    : 400,
              }}
            >
              <GitCommit
                size={13}
              />

              <span>
                History
              </span>

              {commits.length >
                0 && (
                <span
                  style={{
                    fontSize:
                      10,
                    background:
                      view ===
                      "commits"
                        ? "rgba(0,0,0,0.3)"
                        : "rgba(255,255,255,0.1)",
                    padding:
                      "1px 6px",
                    borderRadius:
                      10,
                    marginLeft: 2,
                  }}
                >
                  {
                    commits.length
                  }
                </span>
              )}
            </button>

            <div
              ref={
                dropdownRef
              }
              style={{
                position:
                  "relative",
              }}
            >
              <button
                onClick={() =>
                  setShowCloneDropdown(
                    (value) =>
                      !value,
                  )
                }
                style={{
                  display:
                    "flex",
                  alignItems:
                    "center",
                  gap: 6,
                  padding:
                    "5px 12px",
                  borderRadius:
                    5,
                  fontSize: 12,
                  cursor:
                    "pointer",
                  background:
                    showCloneDropdown
                      ? "var(--accent)"
                      : "var(--bg-page)",
                  border:
                    "1px solid var(--line)",
                  color:
                    showCloneDropdown
                      ? "#fff"
                      : "var(--fg)",
                  fontWeight:
                    500,
                }}
              >
                <GitBranch
                  size={13}
                />

                <span>
                  Clone
                </span>

                <ChevronDown
                  size={12}
                  style={{
                    opacity:
                      0.6,
                  }}
                />
              </button>

              {showCloneDropdown && (
                <div
                  style={{
                    position:
                      "absolute",
                    top:
                      "calc(100% + 6px)",
                    right: 0,
                    zIndex: 100,
                    background:
                      "var(--bg-card)",
                    border:
                      "1px solid var(--line)",
                    borderRadius:
                      8,
                    width: 320,
                    padding: 14,
                    boxShadow:
                      "0 8px 32px rgba(0,0,0,0.4)",
                  }}
                >
                  <div
                    style={{
                      fontSize: 13,
                      fontWeight:
                        600,
                      marginBottom:
                        8,
                      color:
                        "var(--fg)",
                    }}
                  >
                    Clone repository
                  </div>

                  <div
                    style={{
                      fontSize: 11,
                      opacity:
                        0.6,
                      marginBottom:
                        10,
                    }}
                  >
                    Use this command
                    to clone this
                    repository
                    locally.
                  </div>

                  <div
                    style={{
                      display:
                        "flex",
                      alignItems:
                        "center",
                      gap: 6,
                      background:
                        "var(--bg-page)",
                      border:
                        "1px solid var(--line)",
                      borderRadius:
                        6,
                      padding:
                        "6px 10px",
                      fontSize: 12,
                      fontFamily:
                        "monospace",
                    }}
                  >
                    <span
                      style={{
                        flex: 1,
                        overflow:
                          "hidden",
                        textOverflow:
                          "ellipsis",
                        whiteSpace:
                          "nowrap",
                        color:
                          "var(--fg)",
                      }}
                    >
                      {`git clone ${
                        typeof window !== "undefined" && !API_URL.includes("localhost")
                          ? API_URL
                          : typeof window !== "undefined"
                          ? window.location.origin.replace(":3000", ":8000")
                          : API_URL
                      }/git/${owner}/${repoName}.git`}
                    </span>

                    <button
                      onClick={() => {
                        const baseUrl =
                          typeof window !== "undefined" && !API_URL.includes("localhost")
                            ? API_URL
                            : typeof window !== "undefined"
                            ? window.location.origin.replace(":3000", ":8000")
                            : API_URL;
                        const url = `${baseUrl}/git/${owner}/${repoName}.git`;

                        void navigator.clipboard.writeText(
                          `git clone ${url}`,
                        );

                        setCopiedClone(
                          true,
                        );

                        window.setTimeout(
                          () =>
                            setCopiedClone(
                              false,
                            ),
                          1500,
                        );
                      }}
                      style={{
                        background:
                          "none",
                        border:
                          "none",
                        cursor:
                          "pointer",
                        color:
                          copiedClone
                            ? "var(--cyan)"
                            : "var(--fg)",
                        opacity:
                          0.8,
                        padding: 2,
                        display:
                          "flex",
                        alignItems:
                          "center",
                        justifyContent:
                          "center",
                      }}
                      title="Copy clone command"
                    >
                      {copiedClone ? (
                        <Check
                          size={14}
                        />
                      ) : (
                        <Copy
                          size={14}
                        />
                      )}
                    </button>
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Error notification */}
        {error && (
          <div
            style={{
              padding:
                "8px 20px",
              fontSize: 13,
              background:
                "rgba(239,68,68,0.1)",
              color:
                "#ef4444",
              display:
                "flex",
              alignItems:
                "center",
              gap: 8,
              flexShrink: 0,
            }}
          >
            <AlertCircle
              size={14}
            />

            {error}

            <button
              onClick={() =>
                setError(
                  "",
                )
              }
              style={{
                marginLeft:
                  "auto",
                background:
                  "none",
                border:
                  "none",
                cursor:
                  "pointer",
                color:
                  "inherit",
              }}
            >
              <X size={14} />
            </button>
          </div>
        )}

        {/* Body */}
        <div
          style={{
            display:
              "flex",
            flex: 1,
            overflow:
              "hidden",
          }}
        >
          {view ===
          "commits" ? (
            <div
              style={{
                flex: 1,
                overflowY:
                  "auto",
              }}
            >
              {loadingCommits ? (
                <div
                  style={{
                    padding: 30,
                    textAlign:
                      "center",
                    opacity: 0.5,
                    fontSize: 13,
                  }}
                >
                  Loading commits...
                </div>
              ) : (
                <CommitsPanel
                  commits={
                    commits
                  }
                  repoName={
                    repoName
                  }
                />
              )}
            </div>
          ) : (
            <>
              {/* File tree sidebar */}
              <div
                style={{
                  width: 260,
                  minWidth: 200,
                  borderRight:
                    "1px solid var(--line)",
                  overflowY:
                    "auto",
                  background:
                    "var(--bg-card)",
                }}
              >
                <div
                  style={{
                    padding:
                      "10px 14px 6px",
                    fontSize: 11,
                    fontWeight:
                      600,
                    letterSpacing:
                      "0.08em",
                    opacity: 0.5,
                    textTransform:
                      "uppercase",
                  }}
                >
                  Files
                </div>

                {loadingTree ? (
                  <div
                    style={{
                      padding:
                        "12px 14px",
                      fontSize: 13,
                      opacity:
                        0.5,
                    }}
                  >
                    Loading...
                  </div>
                ) : tree.length ===
                  0 ? (
                  <div
                    style={{
                      padding:
                        "12px 14px",
                      fontSize: 13,
                      opacity:
                        0.5,
                    }}
                  >
                    Repository is
                    empty
                  </div>
                ) : (
                  <FileTree
                    entries={
                      tree
                    }
                    currentPath={
                      selectedPath
                    }
                    onSelect={
                      openFile
                    }
                    owner={
                      owner
                    }
                    repo={
                      repoName
                    }
                    branch={
                      branch
                    }
                  />
                )}
              </div>

              {/* Code viewer */}
              <div
                style={{
                  flex: 1,
                  overflow:
                    "hidden",
                  display:
                    "flex",
                  flexDirection:
                    "column",
                }}
              >
                {loadingFile ? (
                  <div
                    style={{
                      display:
                        "flex",
                      alignItems:
                        "center",
                      justifyContent:
                        "center",
                      height:
                        "100%",
                      opacity:
                        0.5,
                      fontSize: 13,
                    }}
                  >
                    Loading file...
                  </div>
                ) : selectedFile ? (
                  loadingBlame ? (
                    <div
                      style={{
                        display:
                          "flex",
                        alignItems:
                          "center",
                        justifyContent:
                          "center",
                        height:
                          "100%",
                        opacity:
                          0.5,
                        fontSize: 13,
                      }}
                    >
                      Loading line
                      provenance...
                    </div>
                  ) : (
                    <CodeViewer
                      file={
                        selectedFile
                      }
                      comments={
                        comments
                      }
                      onAddComment={
                        handleAddComment
                      }
                      onResolveComment={
                        handleResolveComment
                      }
                      currentUser={
                        owner
                      }
                      blameRanges={
                        blameRanges
                      }
                    />
                  )
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
                      height:
                        "100%",
                      gap: 12,
                      opacity:
                        0.4,
                    }}
                  >
                    <FileCode2
                      size={48}
                      style={{
                        opacity:
                          0.3,
                      }}
                    />

                    <p
                      style={{
                        fontSize: 14,
                      }}
                    >
                      Select a
                      file to view
                      its contents
                    </p>

                    <p
                      style={{
                        fontSize: 12,
                      }}
                    >
                      Click any file
                      in the tree on
                      the left
                    </p>
                  </div>
                )}
              </div>
            </>
          )}
        </div>
      </div>

      <style>
        {`
          .tree-row:hover {
            background: rgba(255,255,255,0.04) !important;
          }

          .commit-row:hover {
            background: rgba(255,255,255,0.03) !important;
          }

          .kw {
            color: #c792ea;
            font-weight: 500;
          }

          .str {
            color: #c3e88d;
          }

          .cmt {
            color: #546e7a;
            font-style: italic;
          }

          table tbody tr:hover > td {
            background: rgba(255,255,255,0.02);
          }
        `}
      </style>
    </AppShell>
  );
}