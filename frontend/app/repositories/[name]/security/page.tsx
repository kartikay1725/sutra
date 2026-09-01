"use client";
import { AppShell } from "@/components/shell";
import { Page, Card, Badge, Btn } from "@/components/ui";
import { AlertTriangle, CheckCircle, ShieldAlert } from "lucide-react";
import { useState, useEffect } from "react";
import { use } from "react";
import { apiAuth } from "@/lib/api";
import { authService } from "@/lib/auth";

export default function SecurityRoute({ params }: { params: Promise<{ name: string }> }) {
  const { name } = use(params);
  const [loading, setLoading] = useState(true);
  const [findings, setFindings] = useState<any[]>([]);

  useEffect(() => {
    const fetchData = async () => {
      setLoading(true);
      try {
        const user = await authService.getCurrentUser();
        const data = await apiAuth<any[]>(`/v1/repositories/${user.username}/${name}/security`);
        setFindings(data);
      } catch (error) {
        console.error("Failed to load security findings", error);
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
        title="Security"
        description="Security posture and findings."
        actions={<Btn primary>Run Scan</Btn>}
      >
        {loading ? (
          <Card className="text-center py-8">
            <p className="sub">Loading security findings...</p>
          </Card>
        ) : (
          <div className="grid grid1" style={{ gap: "16px" }}>
            {findings.length === 0 ? (
              <Card style={{ gridColumn: "1 / -1" }} className="text-center py-10">
                <CheckCircle size={32} className="green" style={{ margin: "0 auto 10px auto" }} />
                <h3>No Security Findings</h3>
                <p className="sub">Your repository is secure. No vulnerabilities found.</p>
              </Card>
            ) : (
              findings.map(finding => (
                <Card key={finding.id} style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
                    <div style={{ display: "flex", alignItems: "flex-start", gap: "12px" }}>
                      <AlertTriangle 
                        size={20} 
                        style={{ color: finding.severity === "critical" || finding.severity === "high" ? "var(--red)" : "var(--amber)", marginTop: "2px" }} 
                      />
                      <div>
                        <h3 style={{ margin: "0 0 4px 0", fontSize: "1.1rem", display: "flex", alignItems: "center", gap: "8px" }}>
                          {finding.title}
                          <Badge tone={finding.severity === "high" || finding.severity === "critical" ? "red" : "amber"}>
                            {finding.severity.toUpperCase()}
                          </Badge>
                          {finding.status === "resolved" && <Badge tone="green">RESOLVED</Badge>}
                        </h3>
                        <p className="sub" style={{ margin: 0, fontSize: "0.9rem" }}>{finding.description}</p>
                      </div>
                    </div>
                    <Btn>View details</Btn>
                  </div>
                  <div style={{ padding: "12px", background: "var(--bg-subtle)", borderRadius: "6px", fontFamily: "monospace", fontSize: "0.85rem", border: "1px solid var(--border-subtle)" }}>
                    <span style={{ color: "var(--muted)" }}>Location: </span>
                    <span style={{ color: "var(--cyan)" }}>{finding.file_path}:{finding.line_number}</span>
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