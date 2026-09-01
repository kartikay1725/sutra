"use client";
import { AppShell } from "@/components/shell";

import { useState, useEffect } from "react";
import Link from "next/link";
import { Page, Card, Badge } from "@/components/ui";
import { Rocket, Server, Clock, CheckCircle2, XCircle, Loader2 } from "lucide-react";
import { apiAuth } from "@/lib/api";

export default function DeploymentsRoute({ params }: { params: Promise<{ name: string }> }) {
  const [name, setName] = useState<string>("");
  const [environments, setEnvironments] = useState<any[]>([]);
  const [deployments, setDeployments] = useState<Record<string, any[]>>({});
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    params.then(p => setName(p.name));
  }, [params]);

  useEffect(() => {
    if (!name) return;

    const fetchData = async () => {
      try {
        const user = await import("@/lib/auth").then(m => m.authService.getCurrentUser());
        const owner = user.username;
        const envs = await apiAuth<any[]>(`/v1/repositories/${owner}/${name}/environments`);
        setEnvironments(envs);

        // Fetch deployments for each environment
        const depsMap: Record<string, any[]> = {};
        await Promise.all(envs.map(async (env) => {
          try {
            const deps = await apiAuth<any[]>(`/v1/repositories/${owner}/${name}/environments/${env.name}/deployments`);
            depsMap[env.name] = deps;
          } catch (e) {
            depsMap[env.name] = [];
          }
        }));
        setDeployments(depsMap);
      } catch (e) {
        console.error(e);
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, [name]);

  const getStatusIcon = (status: string) => {
    switch (status) {
      case "success": return <CheckCircle2 size={16} className="green" />;
      case "failed": return <XCircle size={16} className="red" />;
      case "running": return <Loader2 size={16} className="cyan spin" />;
      default: return <Clock size={16} className="dim" />;
    }
  };

  const getStatusTone = (status: string) => {
    switch (status) {
      case "success": return "green";
      case "failed": return "red";
      case "running": return "cyan";
      default: return "dim";
    }
  };

  if (!name) return null;

  return (
    <AppShell><Page eyebrow={name} title="Deployments" description="Manage environments and deployment history.">
      {loading ? (
        <Card className="text-center py-8">
          <p className="sub">Loading environments...</p>
        </Card>
      ) : environments.length > 0 ? (
        <div className="grid grid2" style={{ gap: "25px" }}>
          {environments.map((env) => (
            <div key={env.id} style={{ display: "flex", flexDirection: "column", gap: "15px" }}>
              <div className="sectionhead" style={{ marginBottom: 0 }}>
                <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                  <Server size={18} className="cyan" />
                  <h2>{env.name}</h2>
                </div>
                {env.url && (
                  <a href={env.url} target="_blank" rel="noreferrer" className="sub no-underline hover-underline" style={{ fontSize: "0.85rem" }}>
                    {env.url}
                  </a>
                )}
              </div>
              
              <Card style={{ padding: "0" }}>
                <div style={{ padding: "15px", borderBottom: "1px solid var(--border-subtle)", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                  <span className="sub">Deployment History</span>
                  <Badge tone={env.is_production ? "purple" : "dim"}>
                    {env.is_production ? "Production" : "Staging"}
                  </Badge>
                </div>
                
                <div style={{ display: "flex", flexDirection: "column" }}>
                  {(deployments[env.name] || []).length > 0 ? (
                    deployments[env.name].map((dep: any, idx: number) => (
                      <div key={dep.id} style={{ 
                        padding: "15px", 
                        borderBottom: idx < deployments[env.name].length - 1 ? "1px solid var(--border-subtle)" : "none",
                        display: "flex",
                        justifyContent: "space-between",
                        alignItems: "center"
                      }}>
                        <div style={{ display: "flex", alignItems: "flex-start", gap: "12px" }}>
                          <div style={{ marginTop: "2px" }}>
                            {getStatusIcon(dep.status)}
                          </div>
                          <div>
                            <div style={{ fontWeight: 500 }}>
                              Deployment #{dep.id.slice(0, 6)}
                            </div>
                            <div className="sub" style={{ fontSize: "0.85rem", marginTop: "2px" }}>
                              Triggered by Artifact: <code>{dep.artifact_id?.slice(0,8) || "unknown"}</code>
                            </div>
                          </div>
                        </div>
                        <Badge tone={getStatusTone(dep.status)}>{dep.status}</Badge>
                      </div>
                    ))
                  ) : (
                    <div style={{ padding: "20px", textAlign: "center" }}>
                      <p className="sub">No deployments recorded.</p>
                    </div>
                  )}
                </div>
              </Card>
            </div>
          ))}
        </div>
      ) : (
        <Card className="text-center py-10">
          <Rocket size={32} className="dim" style={{ margin: "0 auto 10px auto" }} />
          <h3>No Environments Configured</h3>
          <p className="sub">Create environments to track deployments for this repository.</p>
        </Card>
      )}
    </Page>
    </AppShell>
  );
}