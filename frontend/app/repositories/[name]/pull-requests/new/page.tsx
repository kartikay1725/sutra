"use client";

import { use, useEffect, useState } from "react";
import Link from "next/link";
import { AppShell, PageHead, Card } from "@/components/shell";
import { authService } from "@/lib/auth";
import * as I from "lucide-react";

export default function NewPullRequestPage({ params }: { params: Promise<{ name: string }> }) {
  const { name: repoName } = use(params);
  const [owner, setOwner] = useState("kartikay1725");

  useEffect(() => {
    authService.getCurrentUser().then(u => {
      if (u?.username) setOwner(u.username);
    }).catch(() => {});
  }, []);

  const githubPullsUrl = `https://github.com/${owner}/${repoName}/compare`;

  return (
    <AppShell>
      <div style={{ maxWidth: 720, margin: "40px auto", padding: "0 20px" }}>
        <PageHead
          eyebrow={repoName}
          title="Pull Requests on GitHub"
          sub="SUTRA is an AI-native engineering control plane, not a GitHub replacement."
        />

        <Card style={{ padding: 32, marginTop: 24 }}>
          <div style={{ display: "flex", alignItems: "flex-start", gap: 16 }}>
            <div style={{
              width: 44,
              height: 44,
              borderRadius: 12,
              background: "rgba(168, 85, 247, 0.1)",
              border: "1px solid rgba(168, 85, 247, 0.3)",
              display: "grid",
              placeItems: "center",
              flexShrink: 0,
            }}>
              <I.GitPullRequest size={22} color="#a855f7" />
            </div>

            <div style={{ flex: 1 }}>
              <h3 style={{ margin: "0 0 8px 0", fontSize: 17, color: "var(--fg)" }}>
                Human Pull Requests are Authored on GitHub
              </h3>
              <p style={{ margin: "0 0 16px 0", fontSize: 14, color: "var(--muted)", lineHeight: 1.6 }}>
                Humans open, comment on, and manage pull requests directly on GitHub.
                Autonomous agents author governed PRs through SUTRA Task leases, linking commits,
                reviews, and provenance evidence. All PRs are tracked and governed here in SUTRA.
              </p>

              <div style={{ display: "flex", gap: 12, alignItems: "center" }}>
                <a
                  href={githubPullsUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="btn primary"
                  style={{
                    display: "inline-flex",
                    alignItems: "center",
                    gap: 8,
                    padding: "10px 18px",
                    borderRadius: 8,
                    textDecoration: "none",
                    fontWeight: 600,
                  }}
                >
                  <I.ExternalLink size={15} />
                  Open on GitHub
                </a>

                <Link
                  href={`/repositories/${repoName}/pull-requests`}
                  className="btn"
                  style={{
                    display: "inline-flex",
                    alignItems: "center",
                    gap: 6,
                    padding: "10px 16px",
                    borderRadius: 8,
                    textDecoration: "none",
                    border: "1px solid var(--line)",
                  }}
                >
                  <I.ArrowLeft size={14} />
                  Back to Pull Requests
                </Link>
              </div>
            </div>
          </div>
        </Card>
      </div>
    </AppShell>
  );
}
