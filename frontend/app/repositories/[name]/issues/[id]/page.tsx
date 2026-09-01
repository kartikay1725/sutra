"use client";

import { use, useEffect, useState } from "react";
import { AppShell, PageHead, Card, Btn, Badge } from "@/components/shell";
import { issueService, Issue } from "@/lib/issues";
import { authService } from "@/lib/auth";
import * as I from "lucide-react";

export default function IssuePage({ params }: { params: Promise<{ name: string; id: string }> }) {
  const { name, id } = use(params);
  const [issue, setIssue] = useState<Issue | null>(null);
  const [comments, setComments] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [newComment, setNewComment] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [user, setUser] = useState<any>(null);

  const loadIssue = async () => {
    try {
      const u = await authService.getCurrentUser();
      setUser(u);
      const [fetchedIssue, fetchedComments] = await Promise.all([
        issueService.getIssue(u.username, name, id),
        issueService.getComments(u.username, name, id)
      ]);
      setIssue(fetchedIssue);
      setComments(fetchedComments);
    } catch (e: any) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadIssue();
  }, [name, id]);

  const handleAddComment = async (close: boolean = false) => {
    if (!newComment.trim() && !close) return;
    setSubmitting(true);
    try {
      if (newComment.trim()) {
        await issueService.addComment(user.username, name, id, newComment);
      }
      if (close) {
        await issueService.updateIssueStatus(user.username, name, id, { status: "closed" });
      }
      setNewComment("");
      loadIssue();
    } catch (e: any) {
      alert("Action failed: " + e.message);
    } finally {
      setSubmitting(false);
    }
  };

  const handleReopen = async () => {
    setSubmitting(true);
    try {
      await issueService.updateIssueStatus(user.username, name, id, { status: "open" });
      loadIssue();
    } catch (e: any) {
      alert("Action failed: " + e.message);
    } finally {
      setSubmitting(false);
    }
  };

  if (loading) {
    return (
      <AppShell>
        <div style={{ padding: 40 }} className="muted">Loading issue...</div>
      </AppShell>
    );
  }

  if (!issue) {
    return (
      <AppShell>
        <div style={{ padding: 40 }} className="muted">Issue not found.</div>
      </AppShell>
    );
  }

  return (
    <AppShell>
      <div style={{ padding: "20px 40px", maxWidth: 1000, margin: "0 auto" }}>
        
        <div style={{ marginBottom: 20 }}>
          <h1 style={{ margin: 0, fontSize: 24, fontWeight: 600, color: "var(--fg)" }}>
            {issue.title} <span className="muted">#{issue.id.slice(0,8)}</span>
          </h1>
          <div style={{ display: "flex", alignItems: "center", gap: 12, marginTop: 12 }}>
            <Badge tone={issue.state === "open" || issue.status === "open" ? "aqua" : "dim"}>
              {(issue.state || issue.status) === "open" ? (
                <><I.CircleDot size={12} style={{ marginRight: 6 }} /> Open</>
              ) : (
                <><I.CheckCircle2 size={12} style={{ marginRight: 6 }} /> Closed</>
              )}
            </Badge>
            <span className="muted" style={{ fontSize: 14 }}>
              <strong>{user?.username}</strong> opened this issue on {new Date(issue.created_at).toLocaleDateString()}
            </span>
          </div>
        </div>
        
        <div style={{ display: "flex", gap: 20, marginTop: 24 }}>
          
          <div style={{ flex: 1, display: "flex", flexDirection: "column", gap: 20 }}>
            <Card style={{ padding: 20 }}>
              <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 16 }}>
                <div style={{ width: 28, height: 28, borderRadius: "50%", background: "var(--cyan)", display: "flex", alignItems: "center", justifyContent: "center", fontWeight: "bold" }}>U</div>
                <div style={{ fontSize: 14, color: "var(--muted)" }}><strong>{user?.username}</strong> commented</div>
              </div>
              <div style={{ fontSize: 14, color: "var(--fg)", lineHeight: 1.6, whiteSpace: "pre-wrap" }}>
                {issue.body}
              </div>
            </Card>

            {comments.map((c: any) => (
              <Card key={c.id} style={{ padding: 20 }}>
                <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 16 }}>
                  <div style={{ width: 28, height: 28, borderRadius: "50%", background: "var(--cyan)", display: "flex", alignItems: "center", justifyContent: "center", fontWeight: "bold" }}>U</div>
                  <div style={{ fontSize: 14, color: "var(--muted)" }}>
                    <strong>{user?.username}</strong> commented on {new Date(c.created_at).toLocaleDateString()}
                  </div>
                </div>
                <div style={{ fontSize: 14, color: "var(--fg)", lineHeight: 1.6, whiteSpace: "pre-wrap" }}>
                  {c.body}
                </div>
              </Card>
            ))}

            <Card style={{ padding: 20 }}>
              <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 16 }}>
                <div style={{ width: 28, height: 28, borderRadius: "50%", background: "var(--cyan)", display: "flex", alignItems: "center", justifyContent: "center", fontWeight: "bold" }}>U</div>
                <div style={{ fontSize: 14, color: "var(--fg)", fontWeight: 600 }}>Add a comment</div>
              </div>
              <textarea
                className="input"
                placeholder="Leave a comment"
                value={newComment}
                onChange={e => setNewComment(e.target.value)}
                style={{ width: "100%", minHeight: 100, padding: 12, borderRadius: 6, border: "1px solid var(--line)", background: "var(--bg-subtle)", color: "var(--fg)", resize: "vertical" }}
              />
              <div style={{ display: "flex", justifyContent: "flex-end", alignItems: "center", gap: 12, marginTop: 12 }}>
                {(issue.state || issue.status) === "open" ? (
                  <button className="btn" style={{ display: "flex", alignItems: "center", gap: 6 }} onClick={() => handleAddComment(true)} disabled={submitting}>
                    <I.CheckCircle2 size={14} /> Close issue
                  </button>
                ) : (
                  <button className="btn" style={{ display: "flex", alignItems: "center", gap: 6 }} onClick={handleReopen} disabled={submitting}>
                    <I.CircleDot size={14} /> Reopen issue
                  </button>
                )}
                
                <button className="btn primary" onClick={() => handleAddComment(false)} disabled={submitting || !newComment.trim()}>
                  Comment
                </button>
              </div>
            </Card>

          </div>

          <div style={{ width: 260, display: "flex", flexDirection: "column", gap: 20 }}>
            <div>
              <div style={{ display: "flex", justifyContent: "space-between", color: "var(--muted)", fontSize: "12px", fontWeight: 600, borderBottom: "1px solid var(--line)", paddingBottom: "8px", marginBottom: "8px" }}>
                <span>Assignees</span>
                <I.Settings size={14} />
              </div>
              <div style={{ fontSize: "13px", color: "var(--muted)" }}>No one assigned</div>
            </div>
          </div>
          
        </div>

      </div>
    </AppShell>
  );
}
