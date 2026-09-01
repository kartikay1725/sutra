"use client";
import { AppShell } from "@/components/shell";

import { Page, Card, Badge } from "@/components/ui";
import { Package, Download, Clock, Box, Layers, Terminal } from "lucide-react";
import { useState, useEffect } from "react";
import { use } from "react";
import { apiAuth } from "@/lib/api";

export default function PackagesRoute({ params }: { params: Promise<{ name: string }> }) {
  const { name } = use(params);
  const [loading, setLoading] = useState(true);
  const [packages, setPackages] = useState<any[]>([]);

  useEffect(() => {
    const fetchData = async () => {
      setLoading(true);
      try {
        const user = await import("@/lib/auth").then(m => m.authService.getCurrentUser());
        const owner = user.username;
        const pkgs = await apiAuth<any[]>(`/v1/repositories/${owner}/${name}/packages`);
        setPackages(pkgs);
      } catch (error) {
        console.error("Failed to load packages", error);
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, [name]);

  const getPackageIcon = (type: string) => {
    switch(type) {
      case "npm": return <Box size={24} className="purple" />;
      case "docker": return <Layers size={24} className="cyan" />;
      default: return <Package size={24} className="dim" />;
    }
  };

  const getInstallCommand = (pkg: any) => {
    switch(pkg.type) {
      case "npm": return `npm install ${pkg.name}`;
      case "docker": return `docker pull sutra.io/${pkg.name}:${pkg.latest_version}`;
      case "pypi": return `pip install ${pkg.name}`;
      default: return `install ${pkg.name}`;
    }
  };

  return (
    <AppShell><Page
      eyebrow={name}
      title="Packages & Registry"
      description="Manage published artifacts, containers, and modules for this repository."
    >
      {loading ? (
        <Card className="text-center py-8">
          <p className="sub">Loading registry artifacts...</p>
        </Card>
      ) : (
        <div className="grid grid2" style={{ gap: "20px" }}>
          {packages.length === 0 ? (
            <Card style={{ gridColumn: "1 / -1" }} className="text-center py-10">
              <Package size={32} className="dim" style={{ margin: "0 auto 10px auto" }} />
              <h3>No Packages Published</h3>
              <p className="sub">Set up a CI pipeline to publish artifacts to the SUTRA registry.</p>
            </Card>
          ) : (
            packages.map(pkg => (
              <Card key={pkg.id} style={{ display: "flex", flexDirection: "column", gap: "15px", padding: 0, overflow: "hidden" }} className="hover-card transition-all">
                
                <div style={{ padding: "20px", display: "flex", justifyContent: "space-between", alignItems: "flex-start", background: "var(--bg-subtle)", borderBottom: "1px solid var(--border-subtle)" }}>
                  <div style={{ display: "flex", alignItems: "flex-start", gap: "15px" }}>
                    <div style={{ width: "48px", height: "48px", borderRadius: "10px", background: "var(--bg)", display: "flex", alignItems: "center", justifyContent: "center", border: "1px solid var(--border-subtle)" }}>
                      {getPackageIcon(pkg.type)}
                    </div>
                    <div>
                      <h3 style={{ margin: "0 0 5px 0", fontSize: "1.2rem" }}>{pkg.name}</h3>
                      <div className="sub" style={{ fontSize: "0.9rem", display: "flex", alignItems: "center", gap: "6px" }}>
                        <Badge tone="dim">{pkg.latest_version}</Badge>
                        &middot; {pkg.type.toUpperCase()}
                      </div>
                    </div>
                  </div>
                </div>

                <div style={{ padding: "20px" }}>
                  <p className="sub" style={{ margin: "0 0 20px 0" }}>{pkg.description}</p>
                  
                  <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "15px" }}>
                    <div style={{ display: "flex", alignItems: "center", gap: "6px" }} className="sub">
                      <Download size={14} />
                      <strong style={{ color: "var(--fg)" }}>{pkg.downloads_last_30d.toLocaleString()}</strong> 
                      <span>downloads / mo</span>
                    </div>
                    <div style={{ display: "flex", alignItems: "center", gap: "6px" }} className="sub">
                      <Clock size={14} />
                      <span>{new Date(pkg.published_at).toLocaleDateString()}</span>
                    </div>
                  </div>

                  <div className="sectionhead" style={{ marginTop: "10px", marginBottom: "8px" }}>
                    <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
                      <Terminal size={14} className="dim" /> 
                      <h4 style={{ margin: 0, fontSize: "0.85rem", color: "var(--fg-muted)" }}>Install</h4>
                    </div>
                  </div>
                  <div style={{ padding: "10px 15px", background: "var(--bg-subtle)", borderRadius: "6px", border: "1px solid var(--border-subtle)", fontFamily: "monospace", fontSize: "0.85rem", color: "var(--cyan)", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                    {getInstallCommand(pkg)}
                    <button className="btn" style={{ padding: "4px 8px", fontSize: "0.75rem" }}>Copy</button>
                  </div>
                </div>

              </Card>
            ))
          )}
        </div>
      )}
    </Page>
    </AppShell>
  );
}
