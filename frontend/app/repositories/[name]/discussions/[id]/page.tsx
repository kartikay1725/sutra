"use client";

import { use, useEffect, useState } from "react";
import { AppShell, PageHead, Card, Btn, Badge } from "@/components/shell";
import { discussionService, Discussion } from "@/lib/discussions";
import { authService } from "@/lib/auth";
import * as I from "lucide-react";

export default function DiscussionPage({ params }: { params: Promise<{ name: string; id: string }> }) {
  const { name: repoId, id: discussionId } = use(params);
  const [discussion, setDiscussion] = useState<Discussion | null>(null);
  const [comments, setComments] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [newComment, setNewComment] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [user, setUser] = useState<any>(null);

  const loadDiscussion = async () => {
    try {
      const u = await authService.getCurrentUser();
      setUser(u);
      const [fetchedDiscussion, fetchedComments] = await Promise.all([
        discussionService.getDiscussion(u.username, repoId, discussionId),
        discussionService.getComments(u.username, repoId, discussionId)
      ]);
      setDiscussion(fetchedDiscussion);
      setComments(fetchedComments);
    } catch (e: any) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadDiscussion();
  }, [repoId, discussionId]);

  const handleAddComment = async () => {
    if (!newComment.trim()) return;
    setSubmitting(true);
    try {
      await discussionService.addComment(user.username, repoId, discussionId, newComment);
      setNewComment("");
      loadDiscussion();
    } catch (e: any) {
      alert("Action failed: " + e.message);
    } finally {
      setSubmitting(false);
    }
  };

  if (loading) {
    return (
      <AppShell>
        <div style={{ padding: 40 }} className="muted">Loading discussion...</div>
      </AppShell>
    );
  }

  if (!discussion) {
    return (
      <AppShell>
        <div style={{ padding: 40 }} className="muted">Discussion not found.</div>
      </AppShell>
    );
  }

  return (
    <AppShell>
      <div style={{ padding: "20px 40px", maxWidth: 1000, margin: "0 auto" }}>
        
        <div style={{ marginBottom: 20 }}>
          <h1 style={{ margin: 0, fontSize: 24, fontWeight: 600, color: "var(--fg)" }}>
            {discussion.title} <span className="muted">#{discussion.id.slice(0,8)}</span>
          </h1>
          <div style={{ display: "flex", alignItems: "center", gap: 12, marginTop: 12 }}>
            <Badge tone="dim">{discussion.category}</Badge>
            <span className="muted" style={{ fontSize: 14 }}>
              <strong>{user?.username}</strong> started this discussion on {new Date(discussion.created_at).toLocaleDateString()}
            </span>
          </div>
        </div>
        
        <div style={{ display: "flex", gap: 20, marginTop: 24 }}>
          
          <div style={{ flex: 1, display: "flex", flexDirection: "column", gap: 20 }}>
            <Card style={{ padding: 20 }}>
              <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 16 }}>
                <div style={{ width: 28, height: 28, borderRadius: "50%", background: "var(--cyan)", display: "flex", alignItems: "center", justifyContent: "center", fontWeight: "bold" }}>U</div>
                <div
                  style={{
                    fontSize: 14,
                    color: "var(--muted)",
                  }}
                >
                  <strong>
                    Author
                  </strong>{" "}
                  · {discussion.author_id}
                  ·{" "}
                  {new Date(
                    discussion.created_at,
                  ).toLocaleString()}
                </div>
              </div>
              <div style={{ fontSize: 14, color: "var(--fg)", lineHeight: 1.6, whiteSpace: "pre-wrap" }}>
                {discussion.body}
              </div>
            </Card>

            {comments.map((c: any) => (
              <Card key={c.id} style={{ padding: 20 }}>
                <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 16 }}>
                  <div style={{ width: 28, height: 28, borderRadius: "50%", background: "var(--cyan)", display: "flex", alignItems: "center", justifyContent: "center", fontWeight: "bold" }}>U</div>
                  <div style={{ fontSize: 14, color: "var(--muted)" }}>
                  <strong>Author</strong>
                  {" "}
                  · {c.author_id}
                  ·{" "}
                  {new Date(
                    c.created_at,
                  ).toLocaleString()}
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
                <button className="btn primary" onClick={handleAddComment} disabled={submitting || !newComment.trim()}>
                  Comment
                </button>
              </div>
            </Card>

          </div>
          
        </div>

      </div>
    </AppShell>
  );
}
