"use client";

import { use, useEffect, useState } from "react";
import { AppShell, PageHead, Card, Btn, Badge } from "@/components/shell";
import { discussionService, Discussion } from "@/lib/discussions";
import { authService } from "@/lib/auth";
import * as I from "lucide-react";

export default function DiscussionsPage({ params }: { params: Promise<{ name: string }> }) {
  const { name: repoId } = use(params);
  const [discussions, setDiscussions] = useState<Discussion[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState("");
  const [sortOrder, setSortOrder] = useState<"newest" | "oldest">("newest");
  const [categoryFilter, setCategoryFilter] = useState<string>("View all discussions");
  const [user, setUser] = useState<any>(null);

  const categories = [
    { name: "View all discussions", icon: <I.MessageSquare size={16} /> },
    { name: "Announcements", icon: <I.Megaphone size={16} /> },
    { name: "General", icon: <I.MessageCircle size={16} /> },
    { name: "Ideas", icon: <I.Lightbulb size={16} /> },
    { name: "Polls", icon: <I.BarChart2 size={16} /> },
    { name: "Q&A", icon: <I.HelpCircle size={16} /> },
    { name: "Show and tell", icon: <I.Eye size={16} /> }
  ];

  const loadDiscussions = async (category: string) => {
    setLoading(true);
    try {
      const u = await authService.getCurrentUser();
      setUser(u);
      const data = await discussionService.listDiscussions(u.username, repoId, category === "View all discussions" ? undefined : category);
      setDiscussions(data);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadDiscussions(categoryFilter);
  }, [repoId, categoryFilter]);

  const filteredDiscussions = discussions
    .filter(d => !searchQuery || d.title.toLowerCase().includes(searchQuery.toLowerCase()))
    .sort((a, b) => {
      const dateA = new Date(a.created_at).getTime();
      const dateB = new Date(b.created_at).getTime();
      return sortOrder === "newest" ? dateB - dateA : dateA - dateB;
    });

  return (
    <AppShell>
      <PageHead
        eyebrow={repoId}
        title="Discussions"
        sub="Welcome to Discussions! Ask questions, share ideas, or make announcements."
      />
      <div style={{ display: "flex", gap: "24px", maxWidth: "1200px", margin: "0 auto", padding: "0 20px", marginTop: "20px" }}>
        
        {/* Left Sidebar - Categories */}
        <div style={{ width: "240px", flexShrink: 0 }}>
          <div style={{ fontWeight: 600, fontSize: "14px", color: "var(--fg)", marginBottom: "12px", paddingLeft: "12px" }}>
            Categories
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: "4px" }}>
            {categories.map(cat => (
              <button 
                key={cat.name}
                onClick={() => setCategoryFilter(cat.name)}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: "10px",
                  padding: "8px 12px",
                  borderRadius: "6px",
                  background: categoryFilter === cat.name ? "var(--bg-subtle)" : "transparent",
                  color: categoryFilter === cat.name ? "var(--fg)" : "var(--muted)",
                  border: "none",
                  cursor: "pointer",
                  textAlign: "left",
                  fontSize: "14px",
                  fontWeight: categoryFilter === cat.name ? 600 : 400,
                  transition: "all 0.2s ease"
                }}
              >
                <span style={{ color: categoryFilter === cat.name ? "var(--cyan)" : "inherit" }}>
                  {cat.icon}
                </span>
                {cat.name}
              </button>
            ))}
          </div>
        </div>

        {/* Right Content - Search and List */}
        <div style={{ flex: 1 }}>
          
          <div style={{ display: "flex", gap: "12px", marginBottom: "20px" }}>
            <div style={{ position: "relative", flex: 1 }}>
              <I.Search size={14} style={{ position: "absolute", left: "12px", top: "50%", transform: "translateY(-50%)", color: "var(--muted)" }} />
              <input 
                type="text" 
                placeholder={`Search ${categoryFilter !== "View all discussions" ? categoryFilter : "all discussions"}...`}
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                style={{ width: "100%", padding: "8px 12px 8px 34px", borderRadius: "6px", border: "1px solid var(--line)", background: "transparent", color: "var(--fg)", fontSize: "14px" }}
              />
            </div>
            <select 
              value={sortOrder} 
              onChange={(e) => setSortOrder(e.target.value as any)}
              style={{ padding: "8px 12px", borderRadius: "6px", border: "1px solid var(--line)", background: "transparent", color: "var(--fg)", fontSize: "14px", cursor: "pointer" }}
            >
              <option value="newest" style={{ background: "var(--bg)" }}>Sort by: Latest activity</option>
              <option value="oldest" style={{ background: "var(--bg)" }}>Sort by: Oldest</option>
            </select>
            <Btn primary onClick={() => window.open(`https://github.com/${encodeURIComponent(user?.username || "github")}/${encodeURIComponent(repoId)}/discussions`, "_blank", "noopener,noreferrer")}>
              <I.ExternalLink size={14} style={{ marginRight: 6 }} />
              Open on GitHub
            </Btn>
          </div>

          {loading ? (
            <div style={{ padding: 40, textAlign: "center" }} className="muted">Loading discussions...</div>
          ) : filteredDiscussions.length === 0 ? (
            <div style={{ padding: "60px 20px", textAlign: "center", border: "1px solid var(--line)", borderRadius: "8px", background: "var(--bg-subtle)" }}>
              <I.MessageSquare size={32} style={{ color: "var(--muted)", marginBottom: "16px", opacity: 0.5 }} />
              <div style={{ fontSize: "18px", fontWeight: 600, color: "var(--fg)", marginBottom: "8px" }}>
                There are no matching discussions.
              </div>
              <div style={{ color: "var(--muted)", fontSize: "14px" }}>
                Discussions are authored directly on <a href={`https://github.com/${encodeURIComponent(user?.username || "github")}/${encodeURIComponent(repoId)}/discussions`} target="_blank" rel="noopener noreferrer" style={{ color: "var(--cyan)", textDecoration: "none" }}>GitHub Discussions</a> where autonomous agents observe and participate.
              </div>
            </div>
          ) : (
            <div style={{ display: "flex", flexDirection: "column", border: "1px solid var(--line)", borderRadius: "8px", overflow: "hidden" }}>
              {filteredDiscussions.map((discussion, idx) => (
                <div 
                  key={discussion.id}
                  onClick={() => window.location.href = `/repositories/${repoId}/discussions/${discussion.id}`}
                  style={{ 
                    padding: "16px", 
                    display: "flex", 
                    gap: "16px", 
                    borderBottom: idx < filteredDiscussions.length - 1 ? "1px solid var(--line)" : "none",
                    cursor: "pointer",
                    background: "transparent",
                    transition: "background 0.2s"
                  }}
                  onMouseEnter={(e) => e.currentTarget.style.background = "var(--bg-subtle)"}
                  onMouseLeave={(e) => e.currentTarget.style.background = "transparent"}
                >
                  <div style={{ display: "flex", alignItems: "center", justifyContent: "center", width: 40, height: 40, borderRadius: "50%", background: "var(--bg-subtle)", flexShrink: 0 }}>
                    <I.MessageCircle size={20} style={{ color: "var(--cyan)" }} />
                  </div>
                  <div style={{ flex: 1 }}>
                    <div style={{ fontSize: "16px", fontWeight: 600, color: "var(--fg)", marginBottom: "4px" }}>
                      {discussion.title}
                    </div>
                    <div style={{ fontSize: "13px", color: "var(--muted)", display: "flex", alignItems: "center", gap: "8px" }}>
                      <Badge tone="dim">{discussion.category}</Badge>
                      <span>•</span>
                      <span>#{discussion.id.slice(0, 8)} opened on {new Date(discussion.created_at).toLocaleDateString()}</span>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}

        </div>
      </div>
    </AppShell>
  );
}
