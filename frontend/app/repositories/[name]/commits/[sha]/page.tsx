"use client";

import { AppShell } from "@/components/shell";
import React, { useState, useEffect, use } from "react";
import { useRouter } from "next/navigation";
import { authService } from "@/lib/auth";
import { apiAuth } from "@/lib/api";
import {
  ArrowLeft, GitCommit, RotateCcw, User as UserIcon,
  CheckCircle2, AlertCircle, X, Zap, Clock, FileCode2
} from "lucide-react";
import { ConfirmModal } from "@/components/ConfirmModal";

interface CommitDetail {
  sha: string; short_sha: string; author_name: string; author_email: string;
  committed_at: number; subject: string; body: string; is_agent: boolean;
  parent_sha: string | null; file_stats: string[]; diff: string;
}

function timeSince(iso: string): string {
  const s = (Date.now() - new Date(iso).getTime()) / 1000;
  if (s < 60) return `${Math.floor(s)}s ago`;
  if (s < 3600) return `${Math.floor(s / 60)}m ago`;
  if (s < 86400) return `${Math.floor(s / 3600)}h ago`;
  return `${Math.floor(s / 86400)}d ago`;
}

interface DiffFile {
  filename: string;
  hunks: { header: string; lines: { type: "add" | "del" | "ctx"; text: string }[] }[];
}

function parseDiff(raw: string): DiffFile[] {
  const files: DiffFile[] = [];
  let cur: DiffFile | null = null;
  let curHunk: DiffFile["hunks"][0] | null = null;
  for (const line of raw.split("\n")) {
    if (line.startsWith("diff --git")) {
      if (cur) files.push(cur);
      const m = line.match(/diff --git a\/(.*?) b\/(.*)/);
      cur = { filename: m ? m[2] : line, hunks: [] };
      curHunk = null;
    } else if (line.startsWith("@@") && cur) {
      curHunk = { header: line, lines: [] };
      cur.hunks.push(curHunk);
    } else if (curHunk) {
      if (line.startsWith("+") && !line.startsWith("+++")) curHunk.lines.push({ type: "add", text: line.slice(1) });
      else if (line.startsWith("-") && !line.startsWith("---")) curHunk.lines.push({ type: "del", text: line.slice(1) });
      else if (!line.startsWith("---") && !line.startsWith("+++") && !line.startsWith("\\")) curHunk.lines.push({ type: "ctx", text: line.slice(1) });
    }
  }
  if (cur) files.push(cur);
  return files;
}

function DiffViewer({ diff }: { diff: string }) {
  const files = parseDiff(diff);
  if (!files.length) return <div style={{ padding: 30, textAlign: "center", opacity: 0.5, fontSize: 13 }}>No file changes</div>;
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      {files.map((file, fi) => (
        <div key={fi} style={{ border: "1px solid var(--line)", borderRadius: 8, overflow: "hidden", background: "var(--bg-card)" }}>
          <div style={{ padding: "10px 16px", background: "rgba(255,255,255,0.03)", borderBottom: "1px solid var(--line)", display: "flex", alignItems: "center", gap: 8 }}>
            <FileCode2 size={14} style={{ opacity: 0.6 }} />
            <span style={{ fontFamily: "monospace", fontSize: 13, fontWeight: 500 }}>{file.filename}</span>
          </div>
          {file.hunks.map((hunk, hi) => (
            <div key={hi}>
              <div style={{ padding: "4px 14px", fontSize: 12, fontFamily: "monospace", background: "rgba(99,179,237,0.06)", color: "var(--cyan)", opacity: 0.8 }}>{hunk.header}</div>
              <table style={{ width: "100%", borderCollapse: "collapse", fontFamily: "monospace", fontSize: 12 }}>
                <tbody>
                  {hunk.lines.map((l, li) => (
                    <tr key={li} style={{ background: l.type === "add" ? "rgba(34,197,94,0.08)" : l.type === "del" ? "rgba(239,68,68,0.08)" : "transparent" }}>
                      <td style={{ width: 16, paddingLeft: 12, color: l.type === "add" ? "#22c55e" : l.type === "del" ? "#ef4444" : "var(--muted)", userSelect: "none", lineHeight: "20px" }}>
                        {l.type === "add" ? "+" : l.type === "del" ? "-" : " "}
                      </td>
                      <td style={{ padding: "0 12px 0 4px", whiteSpace: "pre", lineHeight: "20px" }}>{l.text || " "}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ))}
        </div>
      ))}
    </div>
  );
}

export default function CommitDetailPage({ params }: { params: Promise<{ name: string; sha: string }> }) {
  const { name: repoName, sha } = use(params);
  const router = useRouter();
  const [owner, setOwner] = useState("");
  const [commit, setCommit] = useState<CommitDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [rolling, setRolling] = useState(false);
  const [showRollbackModal, setShowRollbackModal] = useState(false);
  const [toast, setToast] = useState<{ msg: string; ok: boolean } | null>(null);

  useEffect(() => { authService.getCurrentUser().then(u => setOwner(u.username)).catch(() => {}); }, []);

  useEffect(() => {
    if (!owner) return;
    setLoading(true);
    apiAuth<CommitDetail>(`/v1/repositories/${owner}/${repoName}/commits/${sha}`)
      .then(setCommit).catch(e => setError(e?.detail || e?.message || "Failed to load commit"))
      .finally(() => setLoading(false));
  }, [owner, repoName, sha]);

  const handleRollback = () => {
    setShowRollbackModal(true);
  };

  const executeRollback = async () => {
    setRolling(true);
    try {
      const res = await apiAuth<{ message: string; new_commit: string }>(
        `/v1/repositories/${owner}/${repoName}/commits/${sha}/revert`, { method: "POST" }
      );
      setShowRollbackModal(false);
      setToast({ msg: `${res.message} — branch updated. Clone/pull will reflect rolled-back code.`, ok: true });
      setTimeout(() => router.push(`/repositories/${repoName}/code`), 3500);
    } catch (e: any) {
      setToast({ msg: e?.detail || e?.message || "Rollback failed", ok: false });
    } finally {
      setRolling(false);
    }
  };

  const date = commit ? new Date(commit.committed_at * 1000) : null;

  return (
    <AppShell>
      <div style={{ width: "100%" }}>

        {/* Toast */}
        {toast && (
          <div style={{
            position: "fixed", top: 20, right: 20, zIndex: 400, maxWidth: 460,
            background: toast.ok ? "rgba(34,197,94,0.12)" : "rgba(239,68,68,0.12)",
            border: `1px solid ${toast.ok ? "rgba(34,197,94,0.3)" : "rgba(239,68,68,0.3)"}`,
            color: toast.ok ? "#22c55e" : "#ef4444",
            padding: "12px 16px", borderRadius: 10, fontSize: 13,
            display: "flex", alignItems: "center", gap: 10, boxShadow: "0 8px 30px rgba(0,0,0,0.5)"
          }}>
            {toast.ok ? <CheckCircle2 size={16} /> : <AlertCircle size={16} />}
            <span style={{ flex: 1 }}>{toast.msg}</span>
            <button onClick={() => setToast(null)} style={{ background: "none", border: "none", cursor: "pointer", color: "inherit" }}><X size={14} /></button>
          </div>
        )}

        {/* Back */}
        <button onClick={() => router.push(`/repositories/${repoName}/code`)} style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 20, background: "none", border: "none", cursor: "pointer", color: "var(--muted)", fontSize: 13 }}>
          <ArrowLeft size={14} /> Back to Code Browser
        </button>

        {loading && <div style={{ padding: 60, textAlign: "center", opacity: 0.5 }}>Loading commit...</div>}
        {error && <div style={{ padding: 16, background: "rgba(239,68,68,0.1)", color: "#ef4444", borderRadius: 8, fontSize: 13 }}>{error}</div>}

        {commit && (
          <>
            {/* Header */}
            <div style={{ background: "var(--bg-card)", border: "1px solid var(--line)", borderRadius: 12, padding: "22px 24px", marginBottom: 20 }}>
              <div style={{ display: "flex", alignItems: "flex-start", gap: 16, marginBottom: 18 }}>
                <div style={{ flex: 1 }}>
                  <h1 style={{ fontSize: 20, fontWeight: 700, margin: "0 0 6px", lineHeight: 1.4 }}>{commit.subject}</h1>
                  {commit.body && <p style={{ margin: 0, fontSize: 13, opacity: 0.6, lineHeight: 1.6, whiteSpace: "pre-wrap" }}>{commit.body}</p>}
                </div>
                {/* Rollback button */}
                <button
                  onClick={handleRollback} disabled={rolling}
                  style={{
                    display: "flex", alignItems: "center", gap: 8, padding: "9px 18px",
                    background: "rgba(239,68,68,0.1)", border: "1px solid rgba(239,68,68,0.4)",
                    borderRadius: 8, color: "#ef4444", cursor: rolling ? "not-allowed" : "pointer",
                    fontSize: 13, fontWeight: 600, flexShrink: 0, opacity: rolling ? 0.5 : 1, transition: "all 0.2s"
                  }}
                >
                  <RotateCcw size={14} />
                  {rolling ? "Rolling back..." : "Rollback to this state"}
                </button>
              </div>

              {/* Author / date / sha */}
              <div style={{ display: "flex", alignItems: "center", gap: 14, flexWrap: "wrap", borderTop: "1px solid var(--line)", paddingTop: 16 }}>
                <div style={{ display: "flex", alignItems: "center", gap: 9 }}>
                  <div style={{
                    width: 32, height: 32, borderRadius: "50%",
                    background: commit.is_agent ? "rgba(167,139,250,0.2)" : "rgba(99,179,237,0.15)",
                    border: `2px solid ${commit.is_agent ? "#a78bfa" : "var(--cyan)"}`,
                    display: "flex", alignItems: "center", justifyContent: "center"
                  }}>
                    {commit.is_agent ? <Zap size={15} color="#a78bfa" /> : <UserIcon size={15} color="var(--cyan)" />}
                  </div>
                  <div>
                    <div style={{ fontSize: 13, fontWeight: 600 }}>{commit.author_name}</div>
                    <div style={{ fontSize: 11, opacity: 0.45 }}>{commit.author_email}</div>
                  </div>
                  {commit.is_agent && (
                    <span style={{ fontSize: 11, background: "rgba(167,139,250,0.15)", color: "#a78bfa", padding: "2px 8px", borderRadius: 12, fontWeight: 600 }}>
                      AI Agent
                    </span>
                  )}
                </div>

                <span style={{ opacity: 0.2 }}>|</span>

                <div style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 12, opacity: 0.6 }}>
                  <Clock size={13} />
                  {date?.toLocaleString()} ({timeSince(date!.toISOString())})
                </div>

                <span style={{ opacity: 0.2 }}>|</span>

                <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                  <GitCommit size={13} style={{ opacity: 0.5 }} />
                  <code style={{ fontSize: 11, fontFamily: "monospace", background: "var(--bg-page)", padding: "2px 8px", borderRadius: 4, border: "1px solid var(--line)" }}>{commit.sha}</code>
                </div>
              </div>

              {/* File stats */}
              {commit.file_stats.length > 0 && (
                <div style={{ marginTop: 14, display: "flex", flexWrap: "wrap", gap: 6 }}>
                  {commit.file_stats.map((fs, i) => (
                    <span key={i} style={{ fontSize: 11, fontFamily: "monospace", background: "rgba(255,255,255,0.04)", padding: "3px 8px", borderRadius: 4, border: "1px solid var(--line)" }}>{fs}</span>
                  ))}
                </div>
              )}

              {/* Rollback explanation */}
              <div style={{ marginTop: 14, padding: "10px 14px", background: "rgba(239,68,68,0.05)", border: "1px solid rgba(239,68,68,0.15)", borderRadius: 8, fontSize: 12, color: "var(--muted)", lineHeight: 1.6 }}>
                <strong style={{ color: "#ef4444" }}>How rollback works:</strong> A new revert commit is appended to the branch.
                The branch HEAD is updated — <code style={{ fontFamily: "monospace" }}>git clone</code> and <code style={{ fontFamily: "monospace" }}>git pull</code> will serve the rolled-back code.
                The original commit history is preserved.
              </div>
            </div>

            {/* Diff label */}
            <div style={{ marginBottom: 10, fontSize: 11, fontWeight: 700, opacity: 0.4, letterSpacing: "0.1em", textTransform: "uppercase" }}>
              Files changed
            </div>

            <DiffViewer diff={commit.diff} />
          </>
        )}
      </div>
      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
      <ConfirmModal
        isOpen={showRollbackModal}
        onClose={() => setShowRollbackModal(false)}
        onConfirm={executeRollback}
        title="Rollback Commit"
        description={
          <>
            Are you sure you want to rollback to state before <strong>&ldquo;{commit?.subject}&rdquo;</strong>? This creates a new revert commit on the branch and updates branch HEAD immediately.
          </>
        }
        confirmText="Confirm Rollback"
        confirmTone="danger"
        loading={rolling}
      />
    </AppShell>
  );
}
