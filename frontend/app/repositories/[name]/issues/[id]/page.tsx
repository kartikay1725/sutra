"use client";

import { use, useCallback, useEffect, useState } from "react";
import { AppShell, Card, Badge } from "@/components/shell";
import { issueService, Issue } from "@/lib/issues";
import { authService } from "@/lib/auth";
import * as I from "lucide-react";

type Comment = {
  id: string;
  body: string;
  created_at: string;
  author_id?: string;
};

export default function IssuePage({
  params,
}: {
  params: Promise<{ name: string; id: string }>;
}) {
  const { name, id } = use(params);

  const [issue, setIssue] = useState<Issue | null>(null);
  const [comments, setComments] = useState<Comment[]>([]);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [newComment, setNewComment] = useState("");
  const [user, setUser] = useState<any>(null);

  const loadIssue = useCallback(async () => {
    try {
      setLoading(true);

      const currentUser = await authService.getCurrentUser();

      if (!currentUser?.username) {
        throw new Error("Unable to determine the current user.");
      }

      setUser(currentUser);

      const [fetchedIssue, fetchedComments] = await Promise.all([
        issueService.getIssue(currentUser.username, name, id),
        issueService.getComments(currentUser.username, name, id),
      ]);

      setIssue(fetchedIssue);
      setComments(fetchedComments || []);
    } catch (error: any) {
      console.error("Failed to load issue:", error);
      alert(
        "Failed to load issue: " +
          (error?.message || "Unknown error")
      );
    } finally {
      setLoading(false);
    }
  }, [name, id]);

  useEffect(() => {
    loadIssue();
  }, [loadIssue]);

  /**
   * Add a normal comment.
   */
  const handleComment = async () => {
    const body = newComment.trim();

    if (!body) {
      return;
    }

    if (!user?.username) {
      alert("Unable to determine the current user.");
      return;
    }

    setSubmitting(true);

    try {
      await issueService.addComment(
        user.username,
        name,
        id,
        body
      );

      setNewComment("");
      await loadIssue();
    } catch (error: any) {
      console.error("Failed to add comment:", error);
      alert(
        "Action failed: " +
          (error?.message || "Unable to add comment.")
      );
    } finally {
      setSubmitting(false);
    }
  };

  /**
   * Close the issue.
   *
   * IMPORTANT:
   * The backend requires a resolution whenever status becomes "closed".
   * Therefore resolution is explicitly sent here.
   */
  const handleClose = async () => {
    if (!user?.username) {
      alert("Unable to determine the current user.");
      return;
    }

    setSubmitting(true);

    try {
      // Add the comment first, when one was entered.
      const body = newComment.trim();

      if (body) {
        await issueService.addComment(
          user.username,
          name,
          id,
          body
        );
      }

      // Explicitly send the required resolution.
      const payload = {
        status: "closed" as const,
        resolution: "completed" as const,
        comment: body || "Closed by user",
      };

      console.log("Closing issue with payload:", payload);

      await issueService.updateIssueStatus(
        user.username,
        name,
        id,
        payload
      );

      setNewComment("");
      await loadIssue();
    } catch (error: any) {
      console.error("Failed to close issue:", error);
      alert(
        "Action failed: " +
          (error?.message || "Unable to close issue.")
      );
    } finally {
      setSubmitting(false);
    }
  };

  /**
   * Reopen a closed issue.
   */
  const handleReopen = async () => {
    if (!user?.username) {
      alert("Unable to determine the current user.");
      return;
    }

    setSubmitting(true);

    try {
      await issueService.updateIssueStatus(
        user.username,
        name,
        id,
        {
          status: "open",
        }
      );

      await loadIssue();
    } catch (error: any) {
      console.error("Failed to reopen issue:", error);
      alert(
        "Action failed: " +
          (error?.message || "Unable to reopen issue.")
      );
    } finally {
      setSubmitting(false);
    }
  };

  if (loading) {
    return (
      <AppShell>
        <div
          style={{ padding: 40 }}
          className="muted"
        >
          Loading issue...
        </div>
      </AppShell>
    );
  }

  if (!issue) {
    return (
      <AppShell>
        <div
          style={{ padding: 40 }}
          className="muted"
        >
          Issue not found.
        </div>
      </AppShell>
    );
  }

  const issueStatus =
    issue.state || issue.status || "open";

  const isOpen = issueStatus === "open";

  return (
    <AppShell>
      <div
        style={{
          padding: "20px 40px",
          maxWidth: 1000,
          margin: "0 auto",
        }}
      >
        {/* Header */}
        <div style={{ marginBottom: 20 }}>
          <h1
            style={{
              margin: 0,
              fontSize: 24,
              fontWeight: 600,
              color: "var(--fg)",
            }}
          >
            {issue.title}{" "}
            <span className="muted">
              #{issue.id.slice(0, 8)}
            </span>
          </h1>

          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: 12,
              marginTop: 12,
            }}
          >
            <Badge tone={isOpen ? "aqua" : "dim"}>
              {isOpen ? (
                <>
                  <I.CircleDot
                    size={12}
                    style={{ marginRight: 6 }}
                  />
                  Open
                </>
              ) : (
                <>
                  <I.CheckCircle2
                    size={12}
                    style={{ marginRight: 6 }}
                  />
                  Closed
                </>
              )}
            </Badge>

            <span
              className="muted"
              style={{ fontSize: 14 }}
            >
              <strong>{user?.username}</strong>{" "}
              opened this issue on{" "}
              {new Date(
                issue.created_at
              ).toLocaleDateString()}
            </span>
          </div>
        </div>

        {/* Main layout */}
        <div
          style={{
            display: "flex",
            gap: 20,
            marginTop: 24,
          }}
        >
          {/* Main column */}
          <div
            style={{
              flex: 1,
              display: "flex",
              flexDirection: "column",
              gap: 20,
            }}
          >
            {/* Original issue body */}
            <Card style={{ padding: 20 }}>
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 12,
                  marginBottom: 16,
                }}
              >
                <div
                  style={{
                    width: 28,
                    height: 28,
                    borderRadius: "50%",
                    background: "var(--cyan)",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    fontWeight: "bold",
                  }}
                >
                  U
                </div>

                <div
                  style={{
                    fontSize: 14,
                    color: "var(--muted)",
                  }}
                >
                  <strong>{user?.username}</strong>{" "}
                  opened this issue
                </div>
              </div>

              <div
                style={{
                  fontSize: 14,
                  color: "var(--fg)",
                  lineHeight: 1.6,
                  whiteSpace: "pre-wrap",
                }}
              >
                {issue.body}
              </div>
            </Card>

            {/* Comments */}
            {comments.map((comment) => (
              <Card
                key={comment.id}
                style={{ padding: 20 }}
              >
                <div
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: 12,
                    marginBottom: 16,
                  }}
                >
                  <div
                    style={{
                      width: 28,
                      height: 28,
                      borderRadius: "50%",
                      background: "var(--cyan)",
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      fontWeight: "bold",
                    }}
                  >
                    U
                  </div>

                  <div
                    style={{
                      fontSize: 14,
                      color: "var(--muted)",
                    }}
                  >
                    <strong>{user?.username}</strong>{" "}
                    commented on{" "}
                    {new Date(
                      comment.created_at
                    ).toLocaleDateString()}
                  </div>
                </div>

                <div
                  style={{
                    fontSize: 14,
                    color: "var(--fg)",
                    lineHeight: 1.6,
                    whiteSpace: "pre-wrap",
                  }}
                >
                  {comment.body}
                </div>
              </Card>
            ))}

            {/* Comment / action box */}
            <Card style={{ padding: 20 }}>
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 12,
                  marginBottom: 16,
                }}
              >
                <div
                  style={{
                    width: 28,
                    height: 28,
                    borderRadius: "50%",
                    background: "var(--cyan)",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    fontWeight: "bold",
                  }}
                >
                  U
                </div>

                <div
                  style={{
                    fontSize: 14,
                    color: "var(--fg)",
                    fontWeight: 600,
                  }}
                >
                  Add a comment
                </div>
              </div>

              <textarea
                className="input"
                placeholder="Leave a comment"
                value={newComment}
                onChange={(event) =>
                  setNewComment(event.target.value)
                }
                style={{
                  width: "100%",
                  minHeight: 100,
                  padding: 12,
                  borderRadius: 6,
                  border:
                    "1px solid var(--line)",
                  background:
                    "var(--bg-subtle)",
                  color: "var(--fg)",
                  resize: "vertical",
                }}
              />

              <div
                style={{
                  display: "flex",
                  justifyContent: "flex-end",
                  alignItems: "center",
                  gap: 12,
                  marginTop: 12,
                }}
              >
                {isOpen ? (
                  <button
                    className="btn"
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: 6,
                    }}
                    onClick={handleClose}
                    disabled={submitting}
                  >
                    <I.CheckCircle2 size={14} />
                    {submitting
                      ? "Closing..."
                      : "Close issue"}
                  </button>
                ) : (
                  <button
                    className="btn"
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: 6,
                    }}
                    onClick={handleReopen}
                    disabled={submitting}
                  >
                    <I.CircleDot size={14} />
                    {submitting
                      ? "Reopening..."
                      : "Reopen issue"}
                  </button>
                )}

                <button
                  className="btn primary"
                  onClick={handleComment}
                  disabled={
                    submitting ||
                    !newComment.trim()
                  }
                >
                  {submitting
                    ? "Working..."
                    : "Comment"}
                </button>
              </div>
            </Card>
          </div>

          {/* Sidebar */}
          <div
            style={{
              width: 260,
              display: "flex",
              flexDirection: "column",
              gap: 20,
            }}
          >
            <div>
              <div
                style={{
                  display: "flex",
                  justifyContent:
                    "space-between",
                  color: "var(--muted)",
                  fontSize: "12px",
                  fontWeight: 600,
                  borderBottom:
                    "1px solid var(--line)",
                  paddingBottom: "8px",
                  marginBottom: "8px",
                }}
              >
                <span>Assignees</span>
                <I.Settings size={14} />
              </div>

              <div
                style={{
                  fontSize: "13px",
                  color: "var(--muted)",
                }}
              >
                No one assigned
              </div>
            </div>
          </div>
        </div>
      </div>
    </AppShell>
  );
}