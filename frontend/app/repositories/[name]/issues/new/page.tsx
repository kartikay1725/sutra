"use client";

import { AppShell, PageHead, Card, Btn } from "@/components/shell";
import { use, useEffect, useState } from "react";
import { authService } from "@/lib/auth";
import { ExternalLink, ArrowLeft, Info } from "lucide-react";
import Link from "next/link";

export default function NewIssueRoute({ params }: { params: Promise<{ name: string }> }) {
  const { name } = use(params);
  const [owner, setOwner] = useState<string>("kartikay1725");

  useEffect(() => {
    authService.getCurrentUser().then(u => {
      if (u?.username) setOwner(u.username);
    }).catch(() => {});
  }, []);

  const githubIssuesUrl = `https://github.com/${owner}/${name}/issues/new`;

  return (
    <AppShell>
      <div style={{ maxWidth: 720, margin: "0 auto" }}>
        <PageHead
          eyebrow={name}
          title="Issues on GitHub"
          sub="SUTRA is an AI-native engineering control plane, not a GitHub replacement."
        />

        <Card style={{ padding: 32, marginTop: 20 }}>
          <div style={{ display: "flex", alignItems: "flex-start", gap: 16 }}>
            <div style={{
              width: 44,
              height: 44,
              borderRadius: 12,
              background: "rgba(114, 231, 231, 0.1)",
              border: "1px solid rgba(114, 231, 231, 0.3)",
              display: "grid",
              placeItems: "center",
              flexShrink: 0,
            }}>
              <Info size={22} color="var(--cyan)" />
            </div>

            <div style={{ flex: 1 }}>
              <h3 style={{ margin: "0 0 8px 0", fontSize: 17, color: "var(--fg)" }}>
                Issues are Authored on GitHub
              </h3>
              <p style={{ margin: "0 0 16px 0", fontSize: 14, color: "var(--muted)", lineHeight: 1.6 }}>
                Humans create and collaborate on issues directly in GitHub repository issues. 
                SUTRA synchronizes and indexes these issues in real time into its unified Knowledge Graph,
                allowing autonomous agents to execute governed tasks against them.
              </p>

              <div style={{ display: "flex", gap: 12, alignItems: "center" }}>
                <a
                  href={githubIssuesUrl}
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
                  <ExternalLink size={15} />
                  Open on GitHub
                </a>

                <Link
                  href={`/repositories/${name}/issues`}
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
                  <ArrowLeft size={14} />
                  Back to Issues
                </Link>
              </div>
            </div>
          </div>
        </Card>
      </div>
    </AppShell>
  );
}
