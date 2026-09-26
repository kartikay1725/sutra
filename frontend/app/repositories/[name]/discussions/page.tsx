"use client";

import { use, useEffect, useState } from "react";
import { AppShell, PageHead, Badge } from "@/components/shell";
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
    { name: "View all discussions", icon: <I.MessageSquare size={15} /> },
    { name: "Announcements", icon: <I.Megaphone size={15} /> },
    { name: "General", icon: <I.MessageCircle size={15} /> },
    { name: "Ideas", icon: <I.Lightbulb size={15} /> },
    { name: "Polls", icon: <I.BarChart2 size={15} /> },
    { name: "Q&A", icon: <I.HelpCircle size={15} /> },
    { name: "Show and tell", icon: <I.Eye size={15} /> }
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
        sub="Sovereign engineering discourse with autonomous agents and engineering peers."
      />

      <div style={{ display: "flex", gap: "28px", width: "100%", marginTop: "24px", alignItems: "flex-start", flexWrap: "wrap" }}>
        
        {/* Left Sidebar - Categories inside double-bezel */}
        <div style={{ width: "260px", flexShrink: 0 }}>
          <div className="bezel-shell">
            <div className="bezel-core" style={{ padding: "16px 12px" }}>
              <div style={{ 
                fontSize: "11px", 
                fontWeight: 700, 
                textTransform: "uppercase", 
                letterSpacing: "0.12em", 
                color: "var(--text-muted)", 
                marginBottom: "14px", 
                paddingLeft: "8px" 
              }}>
                Categories
              </div>
              <div style={{ display: "flex", flexDirection: "column", gap: "3px" }}>
                {categories.map(cat => {
                  const isActive = categoryFilter === cat.name;
                  return (
                    <button 
                      key={cat.name}
                      onClick={() => setCategoryFilter(cat.name)}
                      style={{
                        display: "flex",
                        alignItems: "center",
                        gap: "12px",
                        padding: "9px 12px",
                        borderRadius: "10px",
                        background: isActive ? "rgba(249, 115, 22, 0.12)" : "transparent",
                        color: isActive ? "#FFFFFF" : "var(--text-secondary)",
                        border: isActive ? "1px solid rgba(249, 115, 22, 0.28)" : "1px solid transparent",
                        cursor: "pointer",
                        textAlign: "left",
                        fontSize: "13px",
                        fontWeight: isActive ? 600 : 400,
                        transition: "all 180ms cubic-bezier(0.32, 0.72, 0, 1)",
                      }}
                      className={isActive ? "" : "card-haptic"}
                    >
                      <span style={{ 
                        color: isActive ? "var(--accent)" : "var(--text-muted)",
                        display: "flex",
                        alignItems: "center"
                      }}>
                        {cat.icon}
                      </span>
                      <span>{cat.name}</span>
                    </button>
                  );
                })}
              </div>
            </div>
          </div>
        </div>

        {/* Right Content - Controls & Discussions Stream */}
        <div style={{ flex: 1, minWidth: "min(100%, 360px)" }}>
          
          {/* Action & Filter Bar */}
          <div style={{ display: "flex", gap: "12px", marginBottom: "20px", flexWrap: "wrap", alignItems: "center" }}>
            <div style={{ position: "relative", flex: "1 1 240px" }}>
              <I.Search size={15} style={{ position: "absolute", left: "14px", top: "50%", transform: "translateY(-50%)", color: "var(--text-muted)", pointerEvents: "none" }} />
              <input 
                type="text" 
                placeholder={`Filter in ${categoryFilter !== "View all discussions" ? categoryFilter : "all discussions"}...`}
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="input-recessed"
                style={{ 
                  width: "100%", 
                  padding: "10px 14px 10px 38px", 
                  color: "var(--text-primary)", 
                  fontSize: "13px",
                  lineHeight: "1.4"
                }}
              />
            </div>
            
            <select 
              value={sortOrder} 
              onChange={(e) => setSortOrder(e.target.value as any)}
              className="select input-recessed"
              style={{ 
                height: 40, 
                minWidth: 180, 
                fontSize: 13, 
                color: "var(--text-secondary)",
                padding: "0 14px"
              }}
            >
              <option value="newest">Sort by: Latest activity</option>
              <option value="oldest">Sort by: Oldest</option>
            </select>

            <button 
              className="btn-island"
              onClick={() => window.open(`https://github.com/${encodeURIComponent(user?.username || "github")}/${encodeURIComponent(repoId)}/discussions`, "_blank", "noopener,noreferrer")}
              title="Open GitHub Discussions in new tab"
            >
              <span>Open on GitHub</span>
              <span className="icon-pill">
                <I.ExternalLink size={12} />
              </span>
            </button>
          </div>

          {/* Discussion List / States */}
          {loading ? (
            <div className="bezel-shell">
              <div className="bezel-core" style={{ padding: "20px", display: "flex", flexDirection: "column", gap: "14px" }}>
                {[1, 2, 3].map(i => (
                  <div key={i} style={{ display: "flex", gap: "16px", alignItems: "center", padding: "12px", borderBottom: i < 3 ? "1px solid rgba(255,255,255,0.04)" : "none" }}>
                    <div className="skeleton" style={{ width: 40, height: 40, borderRadius: "50%", flexShrink: 0 }} />
                    <div style={{ flex: 1, display: "flex", flexDirection: "column", gap: "8px" }}>
                      <div className="skeleton" style={{ width: "65%", height: 16, borderRadius: "4px" }} />
                      <div className="skeleton" style={{ width: "35%", height: 12, borderRadius: "4px" }} />
                    </div>
                  </div>
                ))}
              </div>
            </div>
          ) : filteredDiscussions.length === 0 ? (
            <div className="bezel-shell">
              <div className="bezel-core" style={{ padding: "56px 24px", textAlign: "center", display: "flex", flexDirection: "column", alignItems: "center" }}>
                <div style={{ 
                  width: 56, 
                  height: 56, 
                  borderRadius: "16px", 
                  background: "rgba(249, 115, 22, 0.08)", 
                  border: "1px solid rgba(249, 115, 22, 0.2)",
                  display: "flex", 
                  alignItems: "center", 
                  justifyContent: "center",
                  marginBottom: "20px",
                  color: "var(--accent)"
                }}>
                  <I.MessageSquare size={24} />
                </div>
                <div style={{ fontSize: "17px", fontWeight: 600, color: "var(--text-primary)", marginBottom: "8px" }}>
                  No matching discussions found
                </div>
                <p style={{ color: "var(--text-muted)", fontSize: "14px", maxWidth: "480px", lineHeight: "1.6", margin: "0 0 20px 0" }}>
                  Discussions are authored and synchronized directly with <a href={`https://github.com/${encodeURIComponent(user?.username || "github")}/${encodeURIComponent(repoId)}/discussions`} target="_blank" rel="noopener noreferrer" style={{ color: "var(--accent)", textDecoration: "underline" }}>GitHub Discussions</a> where autonomous agents observe and participate.
                </p>
                <button 
                  className="btn-island-ghost"
                  onClick={() => setSearchQuery("")}
                >
                  Clear search filters
                </button>
              </div>
            </div>
          ) : (
            <div className="bezel-shell">
              <div className="bezel-core">
                {filteredDiscussions.map((discussion, idx) => (
                  <div 
                    key={discussion.id}
                    onClick={() => window.location.href = `/repositories/${repoId}/discussions/${discussion.id}`}
                    style={{ 
                      padding: "18px 20px", 
                      display: "flex", 
                      alignItems: "center",
                      gap: "16px", 
                      borderBottom: idx < filteredDiscussions.length - 1 ? "1px solid rgba(255,255,255,0.04)" : "none",
                      cursor: "pointer",
                      background: "transparent",
                      transition: "all 200ms cubic-bezier(0.32, 0.72, 0, 1)"
                    }}
                    className="card-haptic"
                  >
                    <div style={{ 
                      display: "flex", 
                      alignItems: "center", 
                      justifyContent: "center", 
                      width: 42, 
                      height: 42, 
                      borderRadius: "12px", 
                      background: "rgba(255, 255, 255, 0.03)", 
                      border: "1px solid rgba(255, 255, 255, 0.06)",
                      flexShrink: 0 
                    }}>
                      <I.MessageCircle size={18} style={{ color: "var(--accent)" }} />
                    </div>
                    
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{ 
                        fontSize: "15px", 
                        fontWeight: 600, 
                        color: "var(--text-primary)", 
                        marginBottom: "6px",
                        whiteSpace: "nowrap",
                        overflow: "hidden",
                        textOverflow: "ellipsis"
                      }}>
                        {discussion.title}
                      </div>
                      <div style={{ fontSize: "12px", color: "var(--text-muted)", display: "flex", alignItems: "center", gap: "8px", flexWrap: "wrap" }}>
                        <span style={{ 
                          padding: "2px 8px", 
                          borderRadius: "6px", 
                          background: "rgba(255,255,255,0.04)", 
                          border: "1px solid rgba(255,255,255,0.06)",
                          color: "var(--text-secondary)",
                          fontSize: "11px",
                          fontWeight: 500
                        }}>
                          {discussion.category}
                        </span>
                        <span style={{ opacity: 0.4 }}>•</span>
                        <span style={{ fontFamily: "var(--font-mono, monospace)", color: "var(--text-muted)" }}>
                          #{discussion.id.slice(0, 8)}
                        </span>
                        <span style={{ opacity: 0.4 }}>•</span>
                        <span style={{ fontVariantNumeric: "tabular-nums" }}>
                          opened {new Date(discussion.created_at).toLocaleDateString()}
                        </span>
                      </div>
                    </div>

                    <div style={{ color: "var(--text-muted)", opacity: 0.4, paddingRight: 4 }}>
                      <I.ChevronRight size={16} />
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

        </div>
      </div>
    </AppShell>
  );
}

