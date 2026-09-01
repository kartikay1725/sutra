"use client";

import { AppShell } from "@/components/shell";
import React, { useState, useEffect, useCallback, useRef, use } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { authService } from "@/lib/auth";
import { apiAuth } from "@/lib/api";
import {
  GitBranch, GitCommit, ChevronDown, ChevronRight, Folder, FileCode2,
  RotateCcw, Copy, Check, Maximize2, MessageSquare, X, Send, CheckCircle2,
  ArrowLeft, Clock, User as UserIcon, AlertCircle, Edit3, Save, GitPullRequest,
  Code2
} from "lucide-react";

// ─── Types ───────────────────────────────────────────────────────────────────

interface TreeEntry { name: string; path: string; type: "file" | "directory"; size?: number; }
interface FileContent { content: string; encoding: string; size: number; path: string; ref: string; }
interface Commit { sha: string; subject: string; author_name: string; author_email: string; committed_at: number; }
interface Branch { name: string; protected: boolean; commit: string; is_default?: boolean; }
interface InlineComment { id: string; line_number: number; body: string; author_id: string; status: string; created_at: string; replies?: InlineComment[]; }

// ─── Language detection ───────────────────────────────────────────────────────

function detectLang(path: string): string {
  const ext = path.split(".").pop()?.toLowerCase() || "";
  const map: Record<string, string> = {
    ts: "typescript", tsx: "typescript", js: "javascript", jsx: "javascript",
    py: "python", rs: "rust", go: "go", java: "java", cpp: "cpp", c: "c",
    cs: "csharp", rb: "ruby", php: "php", swift: "swift", kt: "kotlin",
    html: "html", css: "css", scss: "css", json: "json", yaml: "yaml",
    yml: "yaml", md: "markdown", sh: "bash", bash: "bash", sql: "sql",
    toml: "toml", xml: "xml", dockerfile: "dockerfile",
  };
  return map[ext] || "plaintext";
}

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

function timeSince(dateStr: string): string {
  const date = new Date(dateStr);
  const now = new Date();
  const secs = Math.floor((now.getTime() - date.getTime()) / 1000);
  if (secs < 60) return "just now";
  if (secs < 3600) return `${Math.floor(secs / 60)}m ago`;
  if (secs < 86400) return `${Math.floor(secs / 3600)}h ago`;
  return `${Math.floor(secs / 86400)}d ago`;
}

// ─── Syntax highlighting (simple token-based) ─────────────────────────────────

function highlightLine(line: string, lang: string): string {
  const esc = (s: string) =>
    s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  const raw = esc(line);
  if (lang === "plaintext" || lang === "markdown") return raw;

  const keywords: Record<string, string[]> = {
    typescript: [
      "import", "export", "from", "const", "let", "var", "function", "return",
      "async", "await", "if", "else", "for", "while", "class", "interface",
      "type", "extends", "implements", "new", "this", "throw", "try", "catch",
      "finally", "null", "undefined", "true", "false", "void", "string",
      "number", "boolean", "any"
    ],
    python: [
      "import", "from", "def", "class", "return", "if", "else", "elif", "for",
      "while", "try", "except", "finally", "with", "as", "pass", "break",
      "continue", "raise", "True", "False", "None", "and", "or", "not", "in",
      "is", "lambda", "yield"
    ],
    go: [
      "package", "import", "func", "var", "const", "type", "struct",
      "interface", "return", "if", "else", "for", "range", "switch", "case",
      "default", "break", "continue", "defer", "go", "select", "chan", "map",
      "make", "new", "nil", "true", "false"
    ],
    rust: [
      "fn", "let", "mut", "const", "use", "mod", "pub", "struct", "enum",
      "impl", "trait", "return", "if", "else", "for", "while", "loop",
      "match", "break", "continue", "self", "Self", "true", "false", "None",
      "Some", "Ok", "Err"
    ],
  };

  // Match comments first
  if (line.trim().startsWith("//") || line.trim().startsWith("#")) {
    return `<span class="cmt">${raw}</span>`;
  }

  const kws = new Set(keywords[lang] || keywords.typescript);
  
  // Tokenize line safely by whitespace/punctuation boundaries
  return raw.replace(/([A-Za-z_][A-Za-z0-9_]*|"(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*'|`(?:\\.|[^`\\])*`|\/\/.*|#.*)/g, (match) => {
    if (match.startsWith("//") || match.startsWith("#")) {
      return `<span class="cmt">${match}</span>`;
    }
    if ((match.startsWith('"') && match.endsWith('"')) || (match.startsWith("'") && match.endsWith("'")) || (match.startsWith('`') && match.endsWith('`'))) {
      return `<span class="str">${match}</span>`;
    }
    if (kws.has(match)) {
      return `<span class="kw">${match}</span>`;
    }
    return match;
  });
}

// ─── Branch Switcher ──────────────────────────────────────────────────────────

function BranchSwitcher({ branches, current, onChange }: { branches: Branch[]; current: string; onChange: (b: string) => void }) {
  const [open, setOpen] = useState(false);
  const [search, setSearch] = useState("");
  const filtered = branches.filter(b => b.name.toLowerCase().includes(search.toLowerCase()));
  return (
    <div style={{ position: "relative" }}>
      <button
        onClick={() => setOpen(o => !o)}
        style={{
          display: "flex", alignItems: "center", gap: 6, padding: "6px 12px",
          background: "var(--bg-card)", border: "1px solid var(--line)",
          borderRadius: 6, cursor: "pointer", color: "var(--fg)", fontSize: 13,
          transition: "all 0.2s"
        }}
      >
        <GitBranch size={13} className="cyan" />
        <span style={{ fontWeight: 500 }}>{current}</span>
        <ChevronDown size={13} style={{ opacity: 0.6 }} />
      </button>
      {open && (
        <div style={{
          position: "absolute", top: "calc(100% + 6px)", left: 0, zIndex: 100,
          background: "var(--bg-card)", border: "1px solid var(--line)", borderRadius: 8,
          width: 240, boxShadow: "0 8px 32px rgba(0,0,0,0.4)", overflow: "hidden"
        }}>
          <div style={{ padding: "8px 10px", borderBottom: "1px solid var(--line)" }}>
            <input
              autoFocus
              value={search}
              onChange={e => setSearch(e.target.value)}
              placeholder="Find a branch..."
              style={{
                width: "100%", background: "var(--bg-page)", border: "1px solid var(--line)",
                borderRadius: 4, padding: "5px 8px", color: "var(--fg)", fontSize: 12,
                outline: "none"
              }}
            />
          </div>
          <div style={{ maxHeight: 240, overflowY: "auto" }}>
            {filtered.map(b => (
              <button
                key={b.name}
                onClick={() => { onChange(b.name); setOpen(false); setSearch(""); }}
                style={{
                  display: "flex", alignItems: "center", gap: 8, width: "100%",
                  padding: "9px 12px", background: b.name === current ? "rgba(255,255,255,0.05)" : "transparent",
                  border: "none", cursor: "pointer", color: "var(--fg)", fontSize: 12, textAlign: "left"
                }}
              >
                <GitBranch size={12} style={{ opacity: 0.5 }} />
                <span style={{ flex: 1 }}>{b.name}</span>
                {b.is_default && <span style={{ fontSize: 10, opacity: 0.5, fontFamily: "monospace" }}>default</span>}
                {b.name === current && <Check size={12} className="cyan" />}
              </button>
            ))}
            {filtered.length === 0 && <div style={{ padding: "12px", fontSize: 12, opacity: 0.5, textAlign: "center" }}>No branches found</div>}
          </div>
        </div>
      )}
    </div>
  );
}

// ─── File Tree ────────────────────────────────────────────────────────────────

function FileTree({
  entries, currentPath, onSelect, owner, repo, branch
}: {
  entries: TreeEntry[];
  currentPath: string;
  onSelect: (e: TreeEntry) => void;
  owner: string; repo: string; branch: string;
}) {
  const [expanded, setExpanded] = useState<Record<string, TreeEntry[]>>({});
  const [loading, setLoading] = useState<Record<string, boolean>>({});

  const toggleDir = async (e: TreeEntry) => {
    if (expanded[e.path]) {
      setExpanded(p => { const n = { ...p }; delete n[e.path]; return n; });
      return;
    }
    setLoading(p => ({ ...p, [e.path]: true }));
    try {
      const data = await apiAuth<{ entries: TreeEntry[] }>(`/v1/repositories/${owner}/${repo}/tree?ref=${encodeURIComponent(branch)}&path=${encodeURIComponent(e.path)}`);
      setExpanded(p => ({ ...p, [e.path]: data.entries || [] }));
    } catch { /* ignore */ }
    finally { setLoading(p => ({ ...p, [e.path]: false })); }
  };

  function renderEntries(list: TreeEntry[], depth = 0): React.ReactNode {
    return list.map(e => (
      <div key={e.path}>
        <div
          onClick={() => e.type === "directory" ? toggleDir(e) : onSelect(e)}
          style={{
            display: "flex", alignItems: "center", gap: 6,
            padding: `5px 10px 5px ${10 + depth * 16}px`,
            cursor: "pointer", fontSize: 13,
            background: e.path === currentPath ? "rgba(99,179,237,0.1)" : "transparent",
            color: e.path === currentPath ? "var(--cyan)" : "var(--fg)",
            borderLeft: e.path === currentPath ? "2px solid var(--cyan)" : "2px solid transparent",
            transition: "all 0.15s"
          }}
          className="tree-row"
        >
          {e.type === "directory" ? (
            <>
              {loading[e.path] ? <span style={{ fontSize: 10, opacity: 0.5 }}>⋯</span> :
                expanded[e.path] ? <ChevronDown size={12} style={{ opacity: 0.5 }} /> : <ChevronRight size={12} style={{ opacity: 0.5 }} />}
              <Folder size={13} style={{ color: "#e6be8a" }} />
            </>
          ) : (
            <>
              <span style={{ width: 12 }} />
              <FileCode2 size={13} style={{ opacity: 0.6 }} />
            </>
          )}
          <span style={{ flex: 1, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{e.name}</span>
          {e.size !== undefined && e.type === "file" && (
            <span style={{ fontSize: 10, opacity: 0.4 }}>{formatSize(e.size)}</span>
          )}
        </div>
        {expanded[e.path] && renderEntries(expanded[e.path], depth + 1)}
      </div>
    ));
  }

  return <div>{renderEntries(entries)}</div>;
}

// ─── Inline Comment Thread ────────────────────────────────────────────────────

function CommentThread({
  lineNo, comments, onAdd, onResolve, currentUser
}: {
  lineNo: number;
  comments: InlineComment[];
  onAdd: (lineNo: number, body: string) => void;
  onResolve: (id: string) => void;
  currentUser: string;
}) {
  const [reply, setReply] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async () => {
    if (!reply.trim()) return;
    setSubmitting(true);
    await onAdd(lineNo, reply);
    setReply("");
    setSubmitting(false);
  };

  return (
    <div style={{
      margin: "0 0 2px 0", borderRadius: 6,
      background: "rgba(255,234,128,0.05)", border: "1px solid rgba(255,234,128,0.15)",
      fontSize: 13, overflow: "hidden"
    }}>
      {comments.map(c => (
        <div key={c.id} style={{ padding: "10px 14px", borderBottom: "1px solid rgba(255,255,255,0.05)" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 6 }}>
            <div style={{
              width: 22, height: 22, borderRadius: "50%", background: "var(--bg-card)",
              display: "flex", alignItems: "center", justifyContent: "center", fontSize: 10, fontWeight: 600
            }}>
              {c.author_id.slice(0, 1).toUpperCase()}
            </div>
            <span style={{ fontWeight: 500, fontSize: 12 }}>{c.author_id.slice(0, 12)}</span>
            <span style={{ fontSize: 11, opacity: 0.5 }}>{timeSince(c.created_at)}</span>
            {c.status === "resolved" && (
              <span style={{ marginLeft: "auto", fontSize: 11, color: "var(--green)" }}>✓ Resolved</span>
            )}
            {c.status !== "resolved" && c.author_id === currentUser && (
              <button
                onClick={() => onResolve(c.id)}
                style={{ marginLeft: "auto", background: "none", border: "1px solid var(--line)", borderRadius: 4, padding: "2px 8px", fontSize: 11, cursor: "pointer", color: "var(--fg)" }}
              >
                Resolve
              </button>
            )}
          </div>
          <div style={{ paddingLeft: 30, lineHeight: 1.6, opacity: c.status === "resolved" ? 0.5 : 1 }}>{c.body}</div>
        </div>
      ))}
      <div style={{ padding: "8px 14px", display: "flex", gap: 8 }}>
        <input
          value={reply}
          onChange={e => setReply(e.target.value)}
          onKeyDown={e => e.key === "Enter" && !e.shiftKey && handleSubmit()}
          placeholder="Leave a comment..."
          style={{
            flex: 1, background: "var(--bg-page)", border: "1px solid var(--line)",
            borderRadius: 4, padding: "6px 10px", color: "var(--fg)", fontSize: 12, outline: "none"
          }}
        />
        <button
          onClick={handleSubmit}
          disabled={!reply.trim() || submitting}
          style={{
            padding: "6px 12px", background: "var(--accent)", color: "#fff",
            border: "none", borderRadius: 4, cursor: "pointer", fontSize: 12,
            opacity: !reply.trim() || submitting ? 0.5 : 1
          }}
        >
          <Send size={12} />
        </button>
      </div>
    </div>
  );
}

// ─── Code Viewer ──────────────────────────────────────────────────────────────

function CodeViewer({
  file, comments, onAddComment, onResolveComment, currentUser, prId, onSaveFile, saving
}: {
  file: FileContent;
  comments: InlineComment[];
  onAddComment: (lineNo: number, body: string) => void;
  onResolveComment: (id: string) => void;
  currentUser: string;
  prId?: string;
  onSaveFile?: (content: string) => void;
  saving?: boolean;
}) {
  const [isEditing, setIsEditing] = useState(false);
  const [editedContent, setEditedContent] = useState(file.content);
  const [hoveredLine, setHoveredLine] = useState<number | null>(null);
  const [activeLines, setActiveLines] = useState<Set<number>>(new Set());
  const [copied, setCopied] = useState(false);
  const lang = detectLang(file.path);
  const lines = file.content.split("\n");

  useEffect(() => {
    setEditedContent(file.content);
    setIsEditing(false);
  }, [file.path, file.content]);

  const commentsPerLine: Record<number, InlineComment[]> = {};
  comments.forEach(c => {
    if (c.line_number) {
      commentsPerLine[c.line_number] = commentsPerLine[c.line_number] || [];
      commentsPerLine[c.line_number].push(c);
    }
  });

  const toggleLineComment = (lineNo: number) => {
    setActiveLines(p => {
      const n = new Set(p);
      n.has(lineNo) ? n.delete(lineNo) : n.add(lineNo);
      return n;
    });
  };

  const copyAll = () => {
    navigator.clipboard.writeText(isEditing ? editedContent : file.content);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%" }}>
      {/* Toolbar */}
      <div style={{
        display: "flex", alignItems: "center", gap: 10, padding: "8px 14px",
        borderBottom: "1px solid var(--line)", background: "var(--bg-card)"
      }}>
        <span style={{ fontSize: 12, fontFamily: "monospace", opacity: 0.7 }}>{file.path}</span>
        <span style={{ fontSize: 11, opacity: 0.4 }}>{formatSize(file.size)}</span>
        <span style={{ fontSize: 11, opacity: 0.4 }}>{lines.length} lines</span>
        <span style={{ fontSize: 11, opacity: 0.4, fontFamily: "monospace" }}>{lang}</span>
        <div style={{ marginLeft: "auto", display: "flex", gap: 6 }}>
          {isEditing ? (
            <>
              <button
                onClick={() => { setEditedContent(file.content); setIsEditing(false); }}
                style={{
                  display: "flex", alignItems: "center", gap: 5, padding: "4px 10px",
                  background: "transparent", border: "1px solid var(--line)", borderRadius: 4,
                  cursor: "pointer", color: "var(--muted)", fontSize: 12
                }}
              >
                Cancel
              </button>
              <button
                onClick={() => onSaveFile && onSaveFile(editedContent)}
                disabled={saving}
                style={{
                  display: "flex", alignItems: "center", gap: 5, padding: "4px 12px",
                  background: "linear-gradient(135deg, var(--violet), var(--aqua))", border: "none",
                  borderRadius: 4, cursor: "pointer", color: "#fff", fontSize: 12, fontWeight: 600
                }}
              >
                <Save size={12} /> {saving ? "Saving..." : "Commit changes"}
              </button>
            </>
          ) : (
            <>
              <button
                onClick={() => setIsEditing(true)}
                title="Edit this file"
                style={{
                  display: "flex", alignItems: "center", gap: 5, padding: "4px 10px",
                  background: "var(--bg-page)", border: "1px solid var(--line)", borderRadius: 4,
                  cursor: "pointer", color: "var(--cyan)", fontSize: 12
                }}
              >
                <Edit3 size={12} /> Edit
              </button>
              <button
                onClick={copyAll}
                title="Copy raw content"
                style={{
                  display: "flex", alignItems: "center", gap: 5, padding: "4px 10px",
                  background: "var(--bg-page)", border: "1px solid var(--line)", borderRadius: 4,
                  cursor: "pointer", color: "var(--fg)", fontSize: 12
                }}
              >
                {copied ? <><Check size={12} /> Copied</> : <><Copy size={12} /> Copy</>}
              </button>
            </>
          )}
        </div>
      </div>

      {/* Code Area */}
      {isEditing ? (
        <div style={{ flex: 1, display: "flex", flexDirection: "column", background: "var(--bg-page)" }}>
          <textarea
            value={editedContent}
            onChange={e => setEditedContent(e.target.value)}
            spellCheck={false}
            style={{
              flex: 1, width: "100%", height: "100%", padding: "16px 20px",
              fontFamily: "'JetBrains Mono', monospace", fontSize: 13, lineHeight: 1.6,
              background: "transparent", color: "var(--fg)", border: "none",
              outline: "none", resize: "none", whiteSpace: "pre", overflowWrap: "normal",
              overflowX: "auto"
            }}
          />
        </div>
      ) : (
        <div style={{ flex: 1, overflowY: "auto", fontFamily: "monospace", fontSize: 13 }}>
          <table style={{ width: "100%", borderCollapse: "collapse" }}>
            <tbody>
              {lines.map((line, i) => {
                const lineNo = i + 1;
                const hasComments = !!commentsPerLine[lineNo]?.length;
                const isActive = activeLines.has(lineNo);
                const isHovered = hoveredLine === lineNo;
                return (
                  <React.Fragment key={lineNo}>
                    <tr
                      onMouseEnter={() => setHoveredLine(lineNo)}
                      onMouseLeave={() => setHoveredLine(null)}
                      style={{
                        background: hasComments ? "rgba(255,234,128,0.04)" :
                          isActive ? "rgba(99,179,237,0.06)" : "transparent"
                      }}
                    >
                      <td style={{
                        width: 50, minWidth: 50, textAlign: "right", padding: "1px 12px 1px 0",
                        userSelect: "none", color: "var(--muted)", fontSize: 12,
                        borderRight: "1px solid var(--line)", verticalAlign: "top"
                      }}>
                        {lineNo}
                      </td>
                      <td style={{ width: 24, padding: "1px 4px", verticalAlign: "top" }}>
                        {(isHovered || hasComments) && (
                          <button
                            onClick={() => toggleLineComment(lineNo)}
                            title="Add comment"
                            style={{
                              background: "none", border: "none", cursor: "pointer",
                              padding: "0 2px", color: hasComments ? "var(--cyan)" : "var(--muted)",
                              opacity: hasComments ? 1 : 0.6
                            }}
                          >
                            <MessageSquare size={11} />
                          </button>
                        )}
                      </td>
                      <td style={{ padding: "1px 0 1px 8px", whiteSpace: "pre", overflowX: "auto" }}>
                        <span dangerouslySetInnerHTML={{ __html: highlightLine(line, lang) }} />
                      </td>
                    </tr>
                    {(isActive || hasComments) && (
                      <tr>
                        <td />
                        <td colSpan={2} style={{ padding: "4px 8px 4px 30px" }}>
                          <CommentThread
                            lineNo={lineNo}
                            comments={commentsPerLine[lineNo] || []}
                            onAdd={(ln, body) => onAddComment(ln, body)}
                            onResolve={onResolveComment}
                            currentUser={currentUser}
                          />
                        </td>
                      </tr>
                    )}
                  </React.Fragment>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

// ─── Commit History Panel ─────────────────────────────────────────────────────

function CommitsPanel({ commits, repoName, owner }: {
  commits: Commit[];
  repoName: string;
  owner: string;
}) {
  const router = useRouter();
  return (
    <div style={{ height: "100%", overflowY: "auto" }}>
      {commits.length === 0 && (
        <div style={{ padding: 30, textAlign: "center", opacity: 0.5, fontSize: 13 }}>No commits yet</div>
      )}
      {commits.map((c, i) => {
        const isBot = c.author_email?.includes("bot@") || c.author_name?.toLowerCase().includes("bot") || c.author_name?.toLowerCase().includes("agent");
        const authorColor = isBot ? "#a78bfa" : `hsl(${i * 67 % 360},55%,42%)`;
        const authorIcon = isBot ? "⚡" : c.author_name.slice(0, 1).toUpperCase();
        return (
          <div
            key={c.sha}
            onClick={() => router.push(`/repositories/${repoName}/commits/${c.sha}`)}
            style={{
              borderBottom: "1px solid var(--line)", padding: "14px 16px",
              cursor: "pointer", transition: "background 0.15s"
            }}
            className="commit-row"
          >
            <div style={{ display: "flex", alignItems: "flex-start", gap: 12 }}>
              <div style={{
                width: 32, height: 32, borderRadius: "50%", background: authorColor,
                display: "flex", alignItems: "center", justifyContent: "center",
                fontSize: 13, fontWeight: 700, flexShrink: 0, color: "#fff"
              }}>
                {authorIcon}
              </div>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ fontWeight: 500, fontSize: 13, lineHeight: 1.45, wordBreak: "break-word" }}>
                  {c.subject}
                </div>
                <div style={{ display: "flex", alignItems: "center", gap: 10, marginTop: 5, flexWrap: "wrap" }}>
                  <span style={{ fontSize: 11, opacity: 0.65 }}>{c.author_name}</span>
                  {isBot && <span style={{ fontSize: 10, background: "rgba(167,139,250,0.15)", color: "#a78bfa", padding: "1px 6px", borderRadius: 10 }}>Agent</span>}
                  <span style={{ fontSize: 11, opacity: 0.4 }}>{timeSince(new Date(c.committed_at * 1000).toISOString())}</span>
                  <code style={{
                    fontSize: 11, fontFamily: "monospace", background: "var(--bg-page)",
                    padding: "1px 6px", borderRadius: 3, border: "1px solid var(--line)", opacity: 0.7
                  }}>{c.sha.slice(0, 7)}</code>
                </div>
              </div>
              <div style={{ opacity: 0.3, fontSize: 12, paddingTop: 2 }}>→</div>
            </div>
          </div>
        );
      })}
    </div>
  );
}

// ─── Main Page ────────────────────────────────────────────────────────────────

export default function CodePage({ params }: { params: Promise<{ name: string }> }) {
  const { name: repoName } = use(params);
  const searchParams = useSearchParams();
  const router = useRouter();

  const [owner, setOwner] = useState("");
  const [branches, setBranches] = useState<Branch[]>([]);
  const [branch, setBranch] = useState(searchParams.get("ref") || "main");
  const [tree, setTree] = useState<TreeEntry[]>([]);
  const [selectedFile, setSelectedFile] = useState<FileContent | null>(null);
  const [selectedPath, setSelectedPath] = useState(searchParams.get("path") || "");
  const [commits, setCommits] = useState<Commit[]>([]);
  const [loadingTree, setLoadingTree] = useState(true);
  const [loadingFile, setLoadingFile] = useState(false);
  const [loadingCommits, setLoadingCommits] = useState(false);
  const [view, setView] = useState<"files" | "commits">("files");
  const [comments, setComments] = useState<InlineComment[]>([]);
  const [rollingBack, setRollingBack] = useState<string | null>(null);
  const [rollbackMsg, setRollbackMsg] = useState("");
  const [error, setError] = useState("");
  const [breadcrumbs, setBreadcrumbs] = useState<string[]>([]);
  const [showCloneDropdown, setShowCloneDropdown] = useState(false);
  const [copiedClone, setCopiedClone] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setShowCloneDropdown(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  // Load current user and branches on mount
  useEffect(() => {
    authService.getCurrentUser().then(u => {
      setOwner(u.username);
    }).catch(() => {});
  }, []);

  useEffect(() => {
    if (!owner) return;
    apiAuth<{ branches: Branch[]; default_branch: string }>(`/v1/repositories/${owner}/${repoName}/branches`)
      .then(data => {
        const bList = data.branches || [];
        setBranches(bList);
        if (!searchParams.get("ref")) {
          const def = data.default_branch || bList.find(b => b.protected)?.name || bList[0]?.name || "main";
          setBranch(def);
        }
      })
      .catch(() => {});
  }, [owner, repoName]);

  // Load commits (defined before any useEffect that calls it)
  const loadCommitsRef = useRef<(() => Promise<void>) | null>(null);
  loadCommitsRef.current = async () => {
    if (!owner) return;
    setLoadingCommits(true);
    try {
      const data = await apiAuth<{ commits: Commit[] }>(`/v1/repositories/${owner}/${repoName}/commits?ref=${encodeURIComponent(branch)}&limit=50`);
      setCommits(data.commits || []);
    } catch (e: any) { 
      if (e.message?.includes("Git ref not found")) setCommits([]);
    } finally { setLoadingCommits(false); }
  };

  const loadCommits = useCallback(() => loadCommitsRef.current?.() ?? Promise.resolve(), []);

  // Load commits when owner or branch changes
  useEffect(() => {
    if (owner) loadCommits();
  }, [owner, branch]); // eslint-disable-line react-hooks/exhaustive-deps

  // Load tree
  useEffect(() => {
    if (!owner) return;
    setLoadingTree(true);
    setError("");
    apiAuth<{ entries: TreeEntry[] }>(`/v1/repositories/${owner}/${repoName}/tree?ref=${encodeURIComponent(branch)}`)
      .then(data => setTree(data.entries || []))
      .catch(e => {
        if (e.message?.includes("Git ref not found")) {
          setTree([]); // Empty repo
        } else {
          setError(e.message);
        }
      })
      .finally(() => setLoadingTree(false));
  }, [owner, repoName, branch]);

  // Load file
  const openFile = useCallback(async (entry: TreeEntry) => {
    if (entry.type !== "file") return;
    setLoadingFile(true);
    setSelectedPath(entry.path);
    setBreadcrumbs(entry.path.split("/"));
    setComments([]);
    try {
      const data = await apiAuth<FileContent>(`/v1/repositories/${owner}/${repoName}/file?path=${encodeURIComponent(entry.path)}&ref=${encodeURIComponent(branch)}`);
      setSelectedFile({ ...data });
    } catch (e: any) {
      setSelectedFile(null);
      setError(e.message);
    } finally {
      setLoadingFile(false);
    }
  }, [owner, repoName, branch]);

  useEffect(() => {
    if (view === "commits") loadCommits();
  }, [view]); // eslint-disable-line react-hooks/exhaustive-deps

  const handleBranchChange = (b: string) => {
    setBranch(b);
    setSelectedFile(null);
    setSelectedPath("");
    setBreadcrumbs([]);
  };

  const handleRollback = async (sha: string) => {
    if (!confirm(`Roll back repository to commit ${sha.slice(0, 7)}? This creates a revert commit on the current branch.`)) return;
    setRollingBack(sha);
    setRollbackMsg("");
    try {
      await apiAuth(`/v1/repositories/${owner}/${repoName}/commits/${sha}/revert`, { method: "POST" });
      setRollbackMsg(`Successfully created revert of ${sha.slice(0, 7)}`);
      loadCommits();
    } catch (e: any) {
      setRollbackMsg(`Rollback failed: ${e.message}`);
    } finally {
      setRollingBack(null);
    }
  };

  const handleAddComment = async (lineNo: number, body: string) => {
    // For code browser we create a standalone comment (no PR required)
    const newComment: InlineComment = {
      id: crypto.randomUUID(),
      line_number: lineNo,
      body,
      author_id: owner,
      status: "active",
      created_at: new Date().toISOString(),
    };
    setComments(p => [...p, newComment]);
  };

  const handleResolveComment = async (id: string) => {
    setComments(p => p.map(c => c.id === id ? { ...c, status: "resolved" } : c));
  };

  const [commitModalOpen, setCommitModalOpen] = useState(false);
  const [pendingContent, setPendingContent] = useState("");
  const [commitTitle, setCommitTitle] = useState("");
  const [commitDescription, setCommitDescription] = useState("");
  const [savingFile, setSavingFile] = useState(false);
  const [successToast, setSuccessToast] = useState("");

  const handleOpenCommitModal = (content: string) => {
    setPendingContent(content);
    const fileName = selectedPath ? selectedPath.split("/").pop() : "file";
    setCommitTitle(`Update ${fileName}`);
    setCommitDescription("");
    setCommitModalOpen(true);
  };

  const handleCommitFile = async () => {
    if (!commitTitle.trim()) return;
    setSavingFile(true);
    setError("");
    try {
      await apiAuth(`/v1/repositories/${owner}/${repoName}/file`, {
        method: "PUT",
        body: JSON.stringify({
          path: selectedPath,
          content: pendingContent,
          branch: branch,
          commit_title: commitTitle.trim(),
          commit_description: commitDescription.trim() || undefined,
        }),
      });
      setCommitModalOpen(false);
      setSuccessToast(`Committed "${commitTitle.trim()}" successfully`);
      setTimeout(() => setSuccessToast(""), 4000);

      // Refresh file and tree
      const updated = await apiAuth<FileContent>(
        `/v1/repositories/${owner}/${repoName}/file?path=${encodeURIComponent(selectedPath)}&ref=${encodeURIComponent(branch)}`
      );
      setSelectedFile({ ...updated });
      loadCommits();
    } catch (e: any) {
      setError(e?.detail || e?.message || "Failed to commit changes");
    } finally {
      setSavingFile(false);
    }
  };

  return (
    <AppShell>
      <div style={{ display: "flex", flexDirection: "column", height: "calc(100vh - 56px)", overflow: "hidden" }}>
        {/* Top bar */}
        <div style={{
          display: "flex", alignItems: "center", gap: 10, padding: "10px 20px",
          borderBottom: "1px solid var(--line)", background: "var(--bg-card)", flexShrink: 0
        }}>
          <BranchSwitcher branches={branches} current={branch} onChange={handleBranchChange} />

          {/* Breadcrumbs */}
          {breadcrumbs.length > 0 && (
            <div style={{ display: "flex", alignItems: "center", gap: 4, fontSize: 13 }}>
              <button
                onClick={() => { setSelectedFile(null); setSelectedPath(""); setBreadcrumbs([]); }}
                style={{ background: "none", border: "none", color: "var(--cyan)", cursor: "pointer", padding: 0 }}
              >
                {repoName}
              </button>
              {breadcrumbs.map((seg, i) => (
                <span key={i} style={{ display: "flex", alignItems: "center", gap: 4 }}>
                  <span style={{ opacity: 0.4 }}>/</span>
                  <span style={{ opacity: i === breadcrumbs.length - 1 ? 1 : 0.6 }}>{seg}</span>
                </span>
              ))}
            </div>
          )}

          <div style={{ marginLeft: "auto", display: "flex", gap: 6 }}>
            <button
              onClick={() => setView("files")}
              style={{
                padding: "5px 12px", borderRadius: 5, fontSize: 12, cursor: "pointer",
                background: view === "files" ? "var(--accent)" : "var(--bg-page)",
                border: "1px solid var(--line)", color: view === "files" ? "#fff" : "var(--fg)"
              }}
            >
              Files
            </button>
            <button
              onClick={() => setView("commits")}
              style={{
                display: "flex", alignItems: "center", gap: 6,
                padding: "5px 12px", borderRadius: 5, fontSize: 12, cursor: "pointer",
                background: view === "commits" ? "linear-gradient(135deg, var(--violet), var(--aqua))" : "var(--bg-page)",
                border: "1px solid var(--line)", color: view === "commits" ? "#fff" : "var(--fg)",
                fontWeight: view === "commits" ? 600 : 400
              }}
            >
              <GitCommit size={13} />
              <span>History</span>
              {commits.length > 0 && (
                <span style={{
                  fontSize: 10, background: view === "commits" ? "rgba(0,0,0,0.3)" : "rgba(255,255,255,0.1)",
                  padding: "1px 6px", borderRadius: 10, marginLeft: 2
                }}>
                  {commits.length}
                </span>
              )}
            </button>
            <div ref={dropdownRef} style={{ position: "relative" }}>
              <button
                onClick={() => setShowCloneDropdown(!showCloneDropdown)}
                style={{
                  display: "flex", alignItems: "center", gap: 6,
                  padding: "5px 12px", borderRadius: 5, fontSize: 12, cursor: "pointer",
                  background: showCloneDropdown ? "var(--accent)" : "var(--bg-page)",
                  border: "1px solid var(--line)", color: showCloneDropdown ? "#fff" : "var(--fg)",
                  fontWeight: 500
                }}
              >
                <Code2 size={13} />
                <span>Code</span>
                <ChevronDown size={12} style={{ opacity: 0.6 }} />
              </button>
              {showCloneDropdown && (
                <div style={{
                  position: "absolute", top: "calc(100% + 6px)", right: 0, zIndex: 100,
                  background: "var(--bg-card)", border: "1px solid var(--line)", borderRadius: 8,
                  width: 320, padding: 14, boxShadow: "0 8px 32px rgba(0,0,0,0.4)"
                }}>
                  <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 8, color: "var(--fg)" }}>Clone repository</div>
                  <div style={{ fontSize: 11, opacity: 0.6, marginBottom: 10 }}>Use this command to clone this repository locally.</div>
                  <div style={{
                    display: "flex", alignItems: "center", gap: 6,
                    background: "var(--bg-page)", border: "1px solid var(--line)",
                    borderRadius: 6, padding: "6px 10px", fontSize: 12, fontFamily: "monospace"
                  }}>
                    <span style={{
                      flex: 1, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap",
                      color: "var(--fg)"
                    }}>
                      {`git clone ${typeof window !== "undefined" ? window.location.origin.replace(":3000", ":8000") : "http://localhost:8000"}/git/${owner}/${repoName}.git`}
                    </span>
                    <button
                      onClick={() => {
                        const url = `${typeof window !== "undefined" ? window.location.origin.replace(":3000", ":8000") : "http://localhost:8000"}/git/${owner}/${repoName}.git`;
                        navigator.clipboard.writeText(`git clone ${url}`);
                        setCopiedClone(true);
                        setTimeout(() => setCopiedClone(false), 1500);
                      }}
                      style={{
                        background: "none", border: "none", cursor: "pointer",
                        color: copiedClone ? "var(--cyan)" : "var(--fg)", opacity: 0.8,
                        padding: 2, display: "flex", alignItems: "center", justifyContent: "center"
                      }}
                      title="Copy clone command"
                    >
                      {copiedClone ? <Check size={14} /> : <Copy size={14} />}
                    </button>
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Success / Error notification */}
        {successToast && (
          <div style={{
            padding: "8px 20px", fontSize: 13, flexShrink: 0,
            background: "rgba(34,197,94,0.15)", color: "#22c55e",
            display: "flex", alignItems: "center", gap: 8
          }}>
            <CheckCircle2 size={14} /> {successToast}
            <button onClick={() => setSuccessToast("")} style={{ marginLeft: "auto", background: "none", border: "none", cursor: "pointer", color: "inherit" }}><X size={14} /></button>
          </div>
        )}

        {rollbackMsg && (
          <div style={{
            padding: "8px 20px", fontSize: 13, flexShrink: 0,
            background: rollbackMsg.includes("failed") ? "rgba(239,68,68,0.15)" : "rgba(34,197,94,0.15)",
            color: rollbackMsg.includes("failed") ? "#ef4444" : "#22c55e",
            display: "flex", alignItems: "center", gap: 8
          }}>
            {rollbackMsg.includes("failed") ? <AlertCircle size={14} /> : <CheckCircle2 size={14} />}
            {rollbackMsg}
            <button onClick={() => setRollbackMsg("")} style={{ marginLeft: "auto", background: "none", border: "none", cursor: "pointer", color: "inherit" }}>
              <X size={14} />
            </button>
          </div>
        )}

        {error && (
          <div style={{
            padding: "8px 20px", fontSize: 13, background: "rgba(239,68,68,0.1)", color: "#ef4444",
            display: "flex", alignItems: "center", gap: 8, flexShrink: 0
          }}>
            <AlertCircle size={14} /> {error}
            <button onClick={() => setError("")} style={{ marginLeft: "auto", background: "none", border: "none", cursor: "pointer", color: "inherit" }}><X size={14} /></button>
          </div>
        )}

        {/* Body */}
        <div style={{ display: "flex", flex: 1, overflow: "hidden" }}>
          {view === "commits" ? (
            <div style={{ flex: 1, overflowY: "auto" }}>
              {loadingCommits ? (
                <div style={{ padding: 30, textAlign: "center", opacity: 0.5, fontSize: 13 }}>Loading commits...</div>
              ) : (
                <CommitsPanel commits={commits} repoName={repoName} owner={owner} />
              )}
            </div>
          ) : (
            <>
              {/* File tree sidebar */}
              <div style={{
                width: 260, minWidth: 200, borderRight: "1px solid var(--line)",
                overflowY: "auto", background: "var(--bg-card)"
              }}>
                <div style={{ padding: "10px 14px 6px", fontSize: 11, fontWeight: 600, letterSpacing: "0.08em", opacity: 0.5, textTransform: "uppercase" }}>
                  Files
                </div>
                {loadingTree ? (
                  <div style={{ padding: "12px 14px", fontSize: 13, opacity: 0.5 }}>Loading...</div>
                ) : tree.length === 0 ? (
                  <div style={{ padding: "12px 14px", fontSize: 13, opacity: 0.5 }}>Repository is empty</div>
                ) : (
                  <FileTree
                    entries={tree}
                    currentPath={selectedPath}
                    onSelect={openFile}
                    owner={owner}
                    repo={repoName}
                    branch={branch}
                  />
                )}
              </div>

              {/* Code viewer */}
              <div style={{ flex: 1, overflow: "hidden", display: "flex", flexDirection: "column" }}>
                {loadingFile ? (
                  <div style={{ display: "flex", alignItems: "center", justifyContent: "center", height: "100%", opacity: 0.5, fontSize: 13 }}>
                    Loading file...
                  </div>
                ) : selectedFile ? (
                  <CodeViewer
                    file={selectedFile}
                    comments={comments}
                    onAddComment={handleAddComment}
                    onResolveComment={handleResolveComment}
                    currentUser={owner}
                    onSaveFile={handleOpenCommitModal}
                    saving={savingFile}
                  />
                ) : (
                  <div style={{
                    display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center",
                    height: "100%", gap: 12, opacity: 0.4
                  }}>
                    <FileCode2 size={48} style={{ opacity: 0.3 }} />
                    <p style={{ fontSize: 14 }}>Select a file to view its contents</p>
                    <p style={{ fontSize: 12 }}>Click any file in the tree on the left</p>
                  </div>
                )}
              </div>
            </>
          )}
        </div>
      </div>

      {/* Commit Modal */}
      {commitModalOpen && (
        <div style={{
          position: "fixed", inset: 0, background: "rgba(0,0,0,0.7)", backdropFilter: "blur(6px)",
          zIndex: 200, display: "flex", alignItems: "center", justifyContent: "center"
        }}>
          <div style={{
            background: "#110e1f", border: "1px solid rgba(168,85,247,0.3)",
            borderRadius: 14, width: 480, padding: 24, boxShadow: "0 20px 60px rgba(0,0,0,0.5)"
          }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 18 }}>
              <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                <GitCommit size={18} className="cyan" />
                <h2 style={{ fontSize: 17, margin: 0, fontWeight: 600 }}>Commit changes</h2>
              </div>
              <button
                onClick={() => setCommitModalOpen(false)}
                style={{ background: "none", border: "none", cursor: "pointer", color: "var(--muted)" }}
              >
                <X size={18} />
              </button>
            </div>

            <div style={{ display: "flex", flexDirection: "column", gap: 14, marginBottom: 20 }}>
              <div>
                <label style={{ display: "block", fontSize: 12, fontWeight: 500, marginBottom: 6, color: "var(--muted)" }}>
                  Commit title
                </label>
                <input
                  className="input"
                  value={commitTitle}
                  onChange={e => setCommitTitle(e.target.value)}
                  placeholder="Update file description"
                  style={{ width: "100%" }}
                  autoFocus
                />
              </div>

              <div>
                <label style={{ display: "block", fontSize: 12, fontWeight: 500, marginBottom: 6, color: "var(--muted)" }}>
                  Extended description (optional)
                </label>
                <textarea
                  className="input"
                  value={commitDescription}
                  onChange={e => setCommitDescription(e.target.value)}
                  placeholder="Add an optional extended description..."
                  rows={3}
                  style={{ width: "100%", height: 75, padding: "8px 12px", resize: "vertical" }}
                />
              </div>

              <div style={{ fontSize: 12, color: "var(--muted)", background: "rgba(255,255,255,0.02)", padding: "10px 12px", borderRadius: 6, border: "1px solid var(--line)" }}>
                Commit directly to branch <strong style={{ color: "var(--cyan)" }}>{branch}</strong>
              </div>
            </div>

            <div style={{ display: "flex", justifyContent: "flex-end", gap: 10 }}>
              <button
                className="btn"
                onClick={() => setCommitModalOpen(false)}
                disabled={savingFile}
              >
                Cancel
              </button>
              <button
                className="btn primary"
                onClick={handleCommitFile}
                disabled={!commitTitle.trim() || savingFile}
              >
                {savingFile ? "Committing..." : "Commit changes"}
              </button>
            </div>
          </div>
        </div>
      )}

      <style>{`
        .tree-row:hover { background: rgba(255,255,255,0.04) !important; }
        .commit-row:hover { background: rgba(255,255,255,0.03) !important; }
        .kw { color: #c792ea; font-weight: 500; }
        .str { color: #c3e88d; }
        .cmt { color: #546e7a; font-style: italic; }
        table tbody tr:hover > td { background: rgba(255,255,255,0.02); }
      `}</style>
    </AppShell>
  );
}
