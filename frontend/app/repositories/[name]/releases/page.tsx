"use client";
import { AppShell } from "@/components/shell";
import { Page, Card, Badge, Btn } from "@/components/ui";
import { Tag, FileArchive, Clock } from "lucide-react";
import { useState, useEffect } from "react";
import { use } from "react";
import { apiAuth } from "@/lib/api";
import { authService } from "@/lib/auth";

export default function ReleasesRoute({ params }: { params: Promise<{ name: string }> }) {
  const { name } = use(params);
  const [loading, setLoading] = useState(true);
  const [releases, setReleases] = useState<any[]>([]);

  useEffect(() => {
    const fetchData = async () => {
      setLoading(true);
      try {
        const user = await authService.getCurrentUser();
        const data = await apiAuth<any[]>(`/v1/repositories/${user.username}/${name}/releases`);
        setReleases(data);
      } catch (error) {
        console.error("Failed to load releases", error);
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, [name]);

  return (
    <AppShell>
      <Page
        eyebrow={name}
        title="Releases"
        description="Versioned software releases."
        actions={<Btn primary>Draft a new release</Btn>}
      >
        {loading ? (
          <Card className="text-center py-8">
            <p className="sub">Loading releases...</p>
          </Card>
        ) : (
          <div className="grid grid1" style={{ gap: "24px" }}>
            {releases.length === 0 ? (
              <Card style={{ gridColumn: "1 / -1" }} className="text-center py-10">
                <Tag size={32} className="dim" style={{ margin: "0 auto 10px auto" }} />
                <h3>No Releases Yet</h3>
                <p className="sub">Create a release to package software, along with release notes and binary assets.</p>
              </Card>
            ) : (
              releases.map(release => (
                <div key={release.id} style={{ display: "flex", gap: "24px", alignItems: "flex-start" }}>
                  <div style={{ width: "200px", textAlign: "right", paddingTop: "10px" }}>
                    <h3 style={{ margin: "0 0 8px 0", fontSize: "1.2rem", display: "flex", alignItems: "center", justifyContent: "flex-end", gap: "8px" }}>
                      <Tag size={16} className="muted" />
                      {release.tag_name}
                    </h3>
                    <div className="sub" style={{ display: "flex", alignItems: "center", justifyContent: "flex-end", gap: "6px", fontSize: "0.85rem" }}>
                      <Clock size={12} />
                      {new Date(release.published_at).toLocaleDateString()}
                    </div>
                  </div>
                  
                  <Card style={{ flex: 1, display: "flex", flexDirection: "column", padding: 0 }}>
                    <div style={{ padding: "20px", borderBottom: "1px solid var(--border-subtle)" }}>
                      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: "16px" }}>
                        <div>
                          <h2 style={{ margin: "0 0 8px 0", fontSize: "1.5rem", display: "flex", alignItems: "center", gap: "8px" }}>
                            {release.name}
                            {release.is_prerelease && <Badge tone="amber">Pre-release</Badge>}
                          </h2>
                          <div className="sub" style={{ fontSize: "0.9rem" }}>
                            Released by <strong>{release.author_id}</strong>
                          </div>
                        </div>
                        <Btn>Edit release</Btn>
                      </div>
                      
                      <div style={{ whiteSpace: "pre-wrap", lineHeight: 1.6, color: "var(--fg)", fontSize: "0.95rem" }}>
                        {release.body}
                      </div>
                    </div>
                    
                    <div style={{ padding: "16px 20px", background: "var(--bg-subtle)" }}>
                      <h4 style={{ margin: "0 0 12px 0", fontSize: "0.9rem", color: "var(--muted)" }}>Assets</h4>
                      <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
                        <div style={{ display: "flex", justifyContent: "space-between", padding: "12px", border: "1px solid var(--border-subtle)", borderRadius: "6px", background: "var(--bg)" }}>
                          <div style={{ display: "flex", alignItems: "center", gap: "8px", fontSize: "0.9rem" }}>
                            <FileArchive size={16} className="dim" />
                            Source code (zip)
                          </div>
                          <Btn>Download</Btn>
                        </div>
                        <div style={{ display: "flex", justifyContent: "space-between", padding: "12px", border: "1px solid var(--border-subtle)", borderRadius: "6px", background: "var(--bg)" }}>
                          <div style={{ display: "flex", alignItems: "center", gap: "8px", fontSize: "0.9rem" }}>
                            <FileArchive size={16} className="dim" />
                            Source code (tar.gz)
                          </div>
                          <Btn>Download</Btn>
                        </div>
                      </div>
                    </div>
                  </Card>
                </div>
              ))
            )}
          </div>
        )}
      </Page>
    </AppShell>
  );
}