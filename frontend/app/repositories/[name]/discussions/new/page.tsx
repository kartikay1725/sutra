"use client";

import { use } from "react";
import { AppShell, PageHead, Card, Btn } from "@/components/shell";
import * as I from "lucide-react";

export default function NewDiscussionCategoryPage({ params }: { params: Promise<{ name: string }> }) {
  const { name: repoId } = use(params);

  const categories = [
    { name: "Announcements", desc: "Updates from maintainers", icon: <I.Megaphone size={18} /> },
    { name: "General", desc: "Chat about anything and everything here", icon: <I.MessageCircle size={18} /> },
    { name: "Ideas", desc: "Share ideas for new features", icon: <I.Lightbulb size={18} /> },
    { name: "Polls", desc: "Take a vote from the community", icon: <I.BarChart2 size={18} /> },
    { name: "Q&A", desc: "Ask the community for help", icon: <I.HelpCircle size={18} /> },
    { name: "Show and tell", desc: "Show off something you've made", icon: <I.Eye size={18} /> }
  ];

  return (
    <AppShell>
      <PageHead
        eyebrow={repoId}
        title="Discussions"
      />
      <div style={{ maxWidth: "900px", margin: "40px auto", padding: "0 20px" }}>
        
        <div style={{ fontSize: "24px", fontWeight: 600, color: "var(--fg)", marginBottom: "24px" }}>
          Select a discussion category
        </div>

        <Card style={{ padding: 0, overflow: "hidden" }}>
          {categories.map((cat, idx) => (
            <div 
              key={cat.name}
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                padding: "24px",
                borderBottom: idx < categories.length - 1 ? "1px solid var(--line)" : "none",
                background: "var(--bg-subtle)"
              }}
            >
              <div style={{ display: "flex", alignItems: "center", gap: "16px" }}>
                <div style={{ color: "var(--cyan)", display: "flex", alignItems: "center", justifyContent: "center" }}>
                  {cat.icon}
                </div>
                <div>
                  <div style={{ fontWeight: 600, color: "var(--fg)", fontSize: "16px", marginBottom: "4px" }}>{cat.name}</div>
                  <div style={{ color: "var(--muted)", fontSize: "14px" }}>{cat.desc}</div>
                </div>
              </div>
              <Btn 
                primary 
                onClick={() => window.location.href = `/repositories/${repoId}/discussions/new/${encodeURIComponent(cat.name.toLowerCase())}`}
              >
                Get started
              </Btn>
            </div>
          ))}
        </Card>

      </div>
    </AppShell>
  );
}
