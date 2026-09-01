"use client";

import { AppShell, PageHead, Card, Btn, Badge } from "@/components/shell";
import { Page } from "@/components/ui";
import { use, useState } from "react";
import { authService } from "@/lib/auth";
import { issueService } from "@/lib/issues";
import { Settings } from "lucide-react";

export default function NewIssueRoute({ params }: { params: Promise<{ name: string }> }) {
  const { name } = use(params);
  const [title, setTitle] = useState("");
  const [body, setBody] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const handleCreate = async () => {
    if (!title.trim() || !body.trim()) return alert("Title and description are required");
    setSubmitting(true);
    try {
      const user = await authService.getCurrentUser();
      await issueService.createIssue(user.username, name, { title, body });
      window.location.href = `/repositories/${name}/issues`;
    } catch (err: any) {
      alert("Failed to create issue: " + err.message);
      setSubmitting(false);
    }
  };

  return (
    <AppShell>
      <div style={{ padding: "30px 40px", maxWidth: 1000, margin: "0 auto" }}>
        
        <div style={{ marginBottom: 24 }}>
          <h1 style={{ margin: 0, fontSize: "20px", fontWeight: 600, color: "var(--fg)" }}>
            Create new issue
          </h1>
        </div>

        <div style={{ display: "flex", gap: 30 }}>
          {/* Main Content */}
          <div style={{ flex: 1, display: "flex", flexDirection: "column", gap: 20 }}>
            <div>
              <label style={{ display: "block", fontSize: 14, fontWeight: 600, marginBottom: 8, color: "var(--fg)" }}>
                Add a title <span style={{ color: "var(--red)" }}>*</span>
              </label>
              <input 
                className="input" 
                placeholder="Title"
                value={title}
                onChange={e => setTitle(e.target.value)}
                style={{ width: "100%", fontSize: "15px", padding: "8px 12px", background: "var(--bg-subtle)", border: "1px solid var(--line)" }}
              />
            </div>
            
            <div>
              <label style={{ display: "block", fontSize: 14, fontWeight: 600, marginBottom: 8, color: "var(--fg)" }}>
                Add a description
              </label>
              <Card style={{ padding: 0 }}>
                <div style={{ display: "flex", alignItems: "center", gap: 16, borderBottom: "1px solid var(--line)", padding: "8px 16px", background: "var(--bg-subtle)", fontSize: 13 }}>
                  <div style={{ fontWeight: 600, borderBottom: "2px solid var(--cyan)", paddingBottom: 8, marginBottom: -9 }}>Write</div>
                  <div className="muted" style={{ paddingBottom: 8, marginBottom: -9 }}>Preview</div>
                  <div style={{ flex: 1 }}></div>
                  <div className="muted" style={{ display: "flex", gap: 12, letterSpacing: 2 }}>
                    <span>H B I </span>
                    <span>&lt;&gt;</span>
                  </div>
                </div>
                <div style={{ padding: 8 }}>
                  <textarea 
                    className="input" 
                    placeholder="Type your description here..."
                    value={body}
                    onChange={e => setBody(e.target.value)}
                    style={{ width: "100%", minHeight: "250px", padding: "8px", background: "transparent", border: "none", outline: "none", resize: "vertical", color: "var(--fg)" }}
                  />
                </div>
              </Card>
            </div>

            <div style={{ display: "flex", justifyContent: "flex-end", alignItems: "center", gap: 16, marginTop: 10 }}>
              <button 
                className="btn" 
                onClick={() => window.location.href = `/repositories/${name}/issues`}
                style={{ background: "transparent", border: "1px solid var(--line)" }}
              >
                Cancel
              </button>
              <button 
                className="btn primary" 
                onClick={handleCreate} 
                disabled={!title || submitting}
                style={{ background: "var(--green)", borderColor: "var(--green)" }}
              >
                {submitting ? "Creating..." : "Create new issue"}
              </button>
            </div>
          </div>


        </div>

      </div>
    </AppShell>
  );
}
