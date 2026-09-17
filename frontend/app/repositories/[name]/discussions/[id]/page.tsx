"use client";

import { use, useEffect, useState } from "react";
import { AppShell, PageHead, Card, Btn, Badge } from "@/components/shell";
import { discussionService, Discussion } from "@/lib/discussions";
import { authService } from "@/lib/auth";
import * as I from "lucide-react";
import Link from "next/link";

export default function DiscussionDetailPage({ params }: { params: Promise<{ name: string; id: string }> }) {
  const { name: repoId, id: discussionId } = use(params);
  const [discussion, setDiscussion] = useState<any | null>(null);
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
      setComments(fetchedComments || []);
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
        <div style={{ padding: 40, textAlign: "center" }} className="muted">Loading discussion...</div>
      </AppShell>
    );
  }

  if (!discussion) {
    return (
      <AppShell>
        <div style={{ padding: 40, textAlign: "center" }} className="muted">Discussion not found.</div>
      </AppShell>
    );
  }

  const isMainAgent = discussion.author_type === "agent" || discussion.body?.includes("[SUTRA Agent:");

  return (
    <AppShell>
      <div style={{ width: "100%" }}>
        
        {/* Header */}
        <div style={{ marginBottom: 24 }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 16 }}>
            <div>
              <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 8 }}>
                <Badge tone="cyan">{discussion.category || "General"}</Badge>
                {isMainAgent ? (
                  <Badge tone="orange"><I.Bot size={12} style={{ marginRight: 4 }} /> SUTRA Agent</Badge>
                ) : (
                  <Badge tone="dim"><I.User size={12} style={{ marginRight: 4 }} /> Human</Badge>
                )}
                {discussion.task_id && (
                  <Badge tone="indigo"><I.CheckSquare size={12} style={{ marginRight: 4 }} /> Task Linked</Badge>
                )}
              </div>
              <h1 style={{ margin: 0, fontSize: 24, fontWeight: 700, color: "#fff" }}>
                {discussion.title}
              </h1>
              <div style={{ fontSize: 13, color: "var(--muted)", marginTop: 6 }}>
                Started by <b>{discussion.author_name || "Author"}</b> on {new Date(discussion.created_at).toLocaleDateString()}
              </div>
            </div>

            {discussion.github_url && (
              <a
                href={discussion.github_url}
                target="_blank"
                rel="noreferrer"
                style={{ textDecoration: "none" }}
              >
                <Btn>
                  <I.ExternalLink size={14} /> Open on GitHub
                </Btn>
              </a>
            )}
          </div>
        </div>

        {/* Content & Sidebar Layout */}
        <div style={{ display: "flex", gap: 24, alignItems: "flex-start" }}>
          
          {/* Main Discussion Thread */}
          <div style={{ flex: 1, display: "flex", flexDirection: "column", gap: 20 }}>
            {/* Opener Post */}
            <Card style={{ padding: 24 }}>
              <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 16, borderBottom: "1px solid var(--line)", paddingBottom: 14 }}>
                <div
                  style={{
                    width: 34,
                    height: 34,
                    borderRadius: "50%",
                    background: isMainAgent ? "linear-gradient(135deg, #059669, #10b981)" : "linear-gradient(135deg, #0891b2, #06b6d4)",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    color: "#fff",
                  }}
                >
                  {isMainAgent ? <I.Bot size={18} /> : <I.User size={18} />}
                </div>
                <div>
                  <div style={{ fontSize: 14, fontWeight: 600, color: "#fff", display: "flex", alignItems: "center", gap: 6 }}>
                    {discussion.author_name || "Author"}
                    {isMainAgent && <span style={{ fontSize: 11, color: "#10b981", fontWeight: 700 }}>[Agent]</span>}
                  </div>
                  <div style={{ fontSize: 12, color: "var(--muted)" }}>
                    {new Date(discussion.created_at).toLocaleString()}
                  </div>
                </div>
              </div>
              <div style={{ fontSize: 14, color: "var(--fg)", lineHeight: 1.7, whiteSpace: "pre-wrap" }}>
                {discussion.body}
              </div>
            </Card>

            {/* Comments */}
            {comments.map((c: any) => {
              const isCommentAgent = c.author_type === "agent" || c.body?.includes("[SUTRA Agent:");
              return (
                <Card key={c.id} style={{ padding: 20 }}>
                  <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 14, borderBottom: "1px solid var(--line)", paddingBottom: 12 }}>
                    <div
                      style={{
                        width: 30,
                        height: 30,
                        borderRadius: "50%",
                        background: isCommentAgent ? "linear-gradient(135deg, #059669, #10b981)" : "linear-gradient(135deg, #0891b2, #06b6d4)",
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "center",
                        color: "#fff",
                      }}
                    >
                      {isCommentAgent ? <I.Bot size={16} /> : <I.User size={16} />}
                    </div>
                    <div>
                      <div style={{ fontSize: 14, fontWeight: 600, color: "#fff", display: "flex", alignItems: "center", gap: 6 }}>
                        {c.author_name || "Author"}
                        {isCommentAgent && <span style={{ fontSize: 11, color: "#10b981", fontWeight: 700 }}>[Agent]</span>}
                      </div>
                      <div style={{ fontSize: 12, color: "var(--muted)" }}>
                        {new Date(c.created_at).toLocaleString()}
                      </div>
                    </div>
                  </div>
                  <div style={{ fontSize: 14, color: "var(--fg)", lineHeight: 1.6, whiteSpace: "pre-wrap" }}>
                    {c.body}
                  </div>
                </Card>
              );
            })}

            {/* Add Comment */}
            <Card style={{ padding: 20 }}>
              <div style={{ fontSize: 14, color: "#fff", fontWeight: 600, marginBottom: 12, display: "flex", alignItems: "center", gap: 8 }}>
                <I.MessageCircle size={16} style={{ color: "var(--cyan)" }} /> Add your reply
              </div>
              <textarea
                className="input"
                placeholder="Share your thoughts or instructions..."
                value={newComment}
                onChange={(e) => setNewComment(e.target.value)}
                style={{
                  width: "100%",
                  minHeight: 110,
                  padding: 14,
                  borderRadius: 8,
                  border: "1px solid var(--line)",
                  background: "var(--bg-subtle)",
                  color: "var(--fg)",
                  fontSize: 14,
                  resize: "vertical",
                  boxSizing: "border-box",
                }}
              />
              <div style={{ display: "flex", justifyContent: "flex-end", marginTop: 12 }}>
                <Btn primary onClick={handleAddComment} disabled={submitting || !newComment.trim()}>
                  {submitting ? "Posting..." : "Comment"}
                </Btn>
              </div>
            </Card>
          </div>

          {/* SUTRA Context Sidebar */}
          <div style={{ width: 300, flexShrink: 0 }}>
            <Card style={{ padding: 20 }}>
              <div style={{ fontSize: 13, fontWeight: 700, color: "var(--muted)", textTransform: "uppercase", letterSpacing: 0.8, marginBottom: 16 }}>
                SUTRA Context
              </div>

              <div style={{ display: "flex", flexDirection: "column", gap: 14, fontSize: 13 }}>
                <div>
                  <div style={{ color: "var(--muted)", fontSize: 12, marginBottom: 2 }}>Repository</div>
                  <div style={{ fontWeight: 600, color: "#fff" }}>{repoId}</div>
                </div>

                <div>
                  <div style={{ color: "var(--muted)", fontSize: 12, marginBottom: 2 }}>Category</div>
                  <div><Badge tone="cyan">{discussion.category || "General"}</Badge></div>
                </div>

                <div>
                  <div style={{ color: "var(--muted)", fontSize: 12, marginBottom: 2 }}>Author Type</div>
                  <div>
                    {isMainAgent ? (
                      <span style={{ color: "var(--accent, #f97316)", fontWeight: 600, display: "inline-flex", alignItems: "center", gap: 4 }}>
                        <I.Bot size={13} /> SUTRA Agent
                      </span>
                    ) : (
                      <span style={{ color: "var(--fg)", fontWeight: 600, display: "inline-flex", alignItems: "center", gap: 4 }}>
                        <I.User size={13} /> Human Operator
                      </span>
                    )}
                  </div>
                </div>

                {discussion.task_id && (
                  <div>
                    <div style={{ color: "var(--muted)", fontSize: 12, marginBottom: 2 }}>Linked Task</div>
                    <Link
                      href={`/tasks/${discussion.task_id}`}
                      style={{ color: "var(--cyan)", textDecoration: "none", fontWeight: 600, display: "inline-flex", alignItems: "center", gap: 4 }}
                    >
                      <I.CheckSquare size={13} /> Task #{discussion.task_id.slice(0, 8)}
                    </Link>
                  </div>
                )}

                {discussion.agent_id && (
                  <div>
                    <div style={{ color: "var(--muted)", fontSize: 12, marginBottom: 2 }}>Agent ID</div>
                    <code style={{ fontSize: 11, background: "rgba(255,255,255,0.05)", padding: "2px 6px", borderRadius: 4 }}>
                      {discussion.agent_id.slice(0, 12)}...
                    </code>
                  </div>
                )}

                {discussion.session_id && (
                  <div>
                    <div style={{ color: "var(--muted)", fontSize: 12, marginBottom: 2 }}>Session ID</div>
                    <code style={{ fontSize: 11, background: "rgba(255,255,255,0.05)", padding: "2px 6px", borderRadius: 4 }}>
                      {discussion.session_id.slice(0, 12)}...
                    </code>
                  </div>
                )}
              </div>
            </Card>
          </div>

        </div>

      </div>
    </AppShell>
  );
}
