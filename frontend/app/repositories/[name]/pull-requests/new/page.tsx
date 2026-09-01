"use client";

import { use, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { AppShell, PageHead, Card, Btn } from "@/components/shell";
import { pullRequestService } from "@/lib/pull-requests";
import { repositoryService } from "@/lib/repositories";
import { changeService, Change } from "@/lib/changes";
import { authService } from "@/lib/auth";
import * as I from "lucide-react";

export default function NewPullRequestPage({ params }: { params: Promise<{ name: string }> }) {
  const { name: repoName } = use(params);
  const router = useRouter();

  const [repo, setRepo] = useState<{ id: string; default_branch: string } | null>(null);
  const [changes, setChanges] = useState<Change[]>([]);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Form state
  const [selectedChangeId, setSelectedChangeId] = useState("");
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [targetBranch, setTargetBranch] = useState("main");
  const [isDraft, setIsDraft] = useState(false);

  useEffect(() => {
    const load = async () => {
      setLoading(true);
      try {
        const user = await authService.getCurrentUser();
        const repoData = await repositoryService.getRepository(user.username, repoName);
        setRepo(repoData);
        setTargetBranch(repoData.default_branch || "main");

        // Load available changes to link as source
        const changesData = await changeService.listChanges(user.username, repoName);
        // Only show changes that don't already have a PR (ideally, but we can show all open ones)
        setChanges(changesData.filter(c => !["merged", "failed", "rejected"].includes(c.status)));
      } catch (e) {
        console.error("Failed to load data", e);
        setError("Failed to load repository data.");
      } finally {
        setLoading(false);
      }
    };
    load();
  }, [repoName]);

  // Auto-fill title from selected change
  useEffect(() => {
    if (selectedChangeId) {
      const change = changes.find(c => c.id === selectedChangeId);
      if (change && !title) {
        setTitle(change.title || change.intent || "");
      }
    }
  }, [selectedChangeId]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!repo || !selectedChangeId || !title || !targetBranch) return;

    setSubmitting(true);
    setError(null);
    try {
      const pr = await pullRequestService.createPR({
        repository_id: repo.id,
        source_change_id: selectedChangeId,
        title,
        description: description || null,
        target_branch: targetBranch,
        is_draft: isDraft,
      });
      router.push(`/repositories/${repoName}/pull-requests/${pr.id}`);
    } catch (e: any) {
      setError(e?.message || "Failed to create pull request. Please check your inputs.");
      setSubmitting(false);
    }
  };

  const inputStyle = {
    width: "100%",
    padding: "10px 14px",
    borderRadius: 8,
    border: "1px solid var(--line)",
    background: "var(--bg)",
    color: "var(--fg)",
    fontSize: 14,
    boxSizing: "border-box" as const,
    outline: "none",
  };

  const labelStyle = {
    display: "block" as const,
    fontSize: 13,
    fontWeight: 600,
    color: "var(--fg)",
    marginBottom: 6,
  };

  if (loading) {
    return <AppShell><div style={{ padding: 48, textAlign: "center", color: "var(--muted)" }}>Loading...</div></AppShell>;
  }

  return (
    <AppShell>
      <PageHead
        eyebrow="Pull Requests"
        title="Open a Pull Request"
        sub={`Select a Change from ${repoName} and describe what you're shipping.`}
      />

      <div style={{ maxWidth: 720, margin: "0 auto", padding: "0 20px" }}>
        <form onSubmit={handleSubmit}>
          <div style={{ display: "flex", flexDirection: "column", gap: 24 }}>

            {/* Source Change selector */}
            <Card style={{ padding: 24 }}>
              <div style={{ fontSize: 12, fontWeight: 700, color: "var(--muted)", textTransform: "uppercase", letterSpacing: "1px", marginBottom: 16 }}>
                Source Change
              </div>
              <label style={labelStyle}>
                Select a Change to create a PR from
                <span style={{ color: "var(--red)", marginLeft: 4 }}>*</span>
              </label>

              {changes.length === 0 ? (
                <div style={{ padding: "14px 16px", borderRadius: 8, border: "1px dashed var(--line)", color: "var(--muted)", fontSize: 14, textAlign: "center" }}>
                  <I.GitCommit size={18} style={{ marginBottom: 8, opacity: 0.5 }} />
                  <div>No open Changes found in this repository.</div>
                  <div style={{ fontSize: 12, marginTop: 4 }}>Create a Change first before opening a Pull Request.</div>
                </div>
              ) : (
                <select
                  value={selectedChangeId}
                  onChange={e => setSelectedChangeId(e.target.value)}
                  required
                  style={{ ...inputStyle, cursor: "pointer" }}
                >
                  <option value="">— Choose a Change —</option>
                  {changes.map(change => (
                    <option key={change.id} value={change.id}>
                      {change.title || change.intent || "Untitled Change"} ({change.status})
                    </option>
                  ))}
                </select>
              )}

              {selectedChangeId && (
                <div style={{ marginTop: 12, padding: "10px 14px", borderRadius: 8, background: "rgba(114, 231, 231, 0.05)", border: "1px solid rgba(114, 231, 231, 0.2)", display: "flex", alignItems: "center", gap: 8, fontSize: 13 }}>
                  <I.GitCommit size={14} color="var(--cyan)" />
                  <span style={{ color: "var(--muted)" }}>Change ID:</span>
                  <span style={{ fontFamily: "monospace", color: "var(--fg)" }}>{selectedChangeId.slice(0, 16)}…</span>
                </div>
              )}
            </Card>

            {/* PR Details */}
            <Card style={{ padding: 24 }}>
              <div style={{ fontSize: 12, fontWeight: 700, color: "var(--muted)", textTransform: "uppercase", letterSpacing: "1px", marginBottom: 16 }}>
                Details
              </div>

              <div style={{ display: "flex", flexDirection: "column", gap: 18 }}>
                <div>
                  <label style={labelStyle}>
                    Title <span style={{ color: "var(--red)" }}>*</span>
                  </label>
                  <input
                    type="text"
                    value={title}
                    onChange={e => setTitle(e.target.value)}
                    placeholder="e.g. Add JWT refresh token rotation"
                    required
                    maxLength={255}
                    style={inputStyle}
                  />
                </div>

                <div>
                  <label style={labelStyle}>Description</label>
                  <textarea
                    value={description}
                    onChange={e => setDescription(e.target.value)}
                    placeholder="Describe what this PR does, why, and any relevant context..."
                    rows={5}
                    maxLength={5000}
                    style={{ ...inputStyle, resize: "vertical", minHeight: 100 }}
                  />
                </div>

                <div>
                  <label style={labelStyle}>
                    Target Branch <span style={{ color: "var(--red)" }}>*</span>
                  </label>
                  <div style={{ position: "relative" }}>
                    <I.GitBranch size={14} style={{ position: "absolute", left: 12, top: "50%", transform: "translateY(-50%)", color: "var(--muted)" }} />
                    <input
                      type="text"
                      value={targetBranch}
                      onChange={e => setTargetBranch(e.target.value)}
                      placeholder="main"
                      required
                      style={{ ...inputStyle, paddingLeft: 34 }}
                    />
                  </div>
                </div>

                <label style={{ display: "flex", alignItems: "center", gap: 10, cursor: "pointer", fontSize: 14 }}>
                  <input
                    type="checkbox"
                    checked={isDraft}
                    onChange={e => setIsDraft(e.target.checked)}
                    style={{ width: 16, height: 16 }}
                  />
                  <span style={{ color: "var(--fg)" }}>Open as Draft</span>
                  <span style={{ color: "var(--muted)", fontSize: 12 }}>Draft PRs cannot be merged until marked ready.</span>
                </label>
              </div>
            </Card>

            {/* Branch comparison visual */}
            {targetBranch && (
              <div style={{ display: "flex", alignItems: "center", gap: 10, padding: "12px 16px", background: "var(--bg-subtle)", borderRadius: 8, border: "1px solid var(--line)", fontSize: 13 }}>
                <I.GitBranch size={14} color="var(--cyan)" />
                <span
                  style={{
                    fontFamily: "monospace",
                    color: "var(--fg)",
                  }}
                >
                  Change {selectedChangeId ? selectedChangeId.slice(0, 8) : "change"} → {targetBranch}
                </span>
                <span
                  style={{
                    color: "var(--muted)",
                    marginLeft: "auto",
                    display: "flex",
                    alignItems: "center",
                    gap: 4,
                  }}
                >
                  <I.Info size={13} />
                  Mergeability will be checked after creation
                </span>
              </div>
            )}

            {/* Error message */}
            {error && (
              <div style={{ padding: "12px 16px", borderRadius: 8, background: "rgba(239, 68, 68, 0.08)", border: "1px solid rgba(239, 68, 68, 0.3)", color: "var(--red)", fontSize: 14, display: "flex", alignItems: "center", gap: 8 }}>
                <I.AlertCircle size={16} />
                {error}
              </div>
            )}

            {/* Submit actions */}
            <div style={{ display: "flex", gap: 12, justifyContent: "flex-end", paddingBottom: 40 }}>
              <Btn type="button" onClick={() => router.back()} disabled={submitting}>
                Cancel
              </Btn>
              <Btn
                primary
                type="submit"
                disabled={submitting || !selectedChangeId || !title || !targetBranch || changes.length === 0}
              >
                {submitting ? (
                  <><I.Loader size={14} style={{ marginRight: 6, animation: "spin 1s linear infinite" }} />Creating...</>
                ) : (
                  <><I.GitPullRequest size={14} style={{ marginRight: 6 }} />{isDraft ? "Create Draft PR" : "Create Pull Request"}</>
                )}
              </Btn>
            </div>
          </div>
        </form>
      </div>
    </AppShell>
  );
}
