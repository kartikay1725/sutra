"use client";

import { Page, Card, Badge } from "@/components/ui";
import { AppShell } from "@/components/shell";
import { Shield, Activity, Users, Settings, Search, RefreshCw, Key, ShieldCheck } from "lucide-react";
import { useState, useEffect } from "react";
import { apiAuth, formatErrorMessage } from "@/lib/api";
import { organizationService, type Organization } from "@/lib/organizations";

type GovernancePolicy = {
  enforce_branch_protection: boolean;
  minimum_pr_approvals: number;
  restrict_public_repositories: boolean;
  require_signed_commits: boolean;
  organization_id: string;
};

export default function EnterpriseDashboard() {
  const [activeTab, setActiveTab] = useState<"audit" | "governance" | "sso">("audit");
  const [loading, setLoading] = useState(true);
  
  const [auditLogs, setAuditLogs] = useState<any[]>([]);
  const [ssoProviders, setSsoProviders] = useState<any[]>([]);
  const [policies, setPolicies] = useState<GovernancePolicy | null>(null);
  const [organization, setOrganization] = useState<Organization | null>(null);
  const [savingPolicies, setSavingPolicies] = useState(false);
  const [policyMessage, setPolicyMessage] = useState<string | null>(null);
  const [policyError, setPolicyError] = useState<string | null>(null);

  useEffect(() => {
    const fetchData = async () => {
      setLoading(true);
      try {
        const organizations = await organizationService.listMyOrganizations();
        const org = organizations[0];
        if (!org) {
          throw new Error("No organization is available for your account.");
        }
        setOrganization(org);
        const [logs, sso, pol] = await Promise.all([
          apiAuth<any[]>(`/v1/organizations/${org.id}/audit-logs`),
          apiAuth<any[]>(`/v1/organizations/${org.id}/sso/providers`),
          apiAuth<GovernancePolicy>(`/v1/organizations/${org.id}/policies`)
        ]);
        setAuditLogs(logs);
        setSsoProviders(sso);
        setPolicies(pol);
      } catch (error) {
        setPolicyError(formatErrorMessage(error));
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, []);

  const formatDate = (dateStr: string) => {
    const d = new Date(dateStr);
    return `${d.toLocaleDateString()} ${d.toLocaleTimeString()}`;
  };

  const savePolicies = async () => {
    if (!organization || !policies) return;
    setSavingPolicies(true);
    setPolicyMessage(null);
    setPolicyError(null);
    try {
      const saved = await apiAuth<GovernancePolicy>(`/v1/organizations/${organization.id}/policies`, {
        method: "PUT",
        body: JSON.stringify({
          enforce_branch_protection: policies.enforce_branch_protection,
          minimum_pr_approvals: policies.minimum_pr_approvals,
          restrict_public_repositories: policies.restrict_public_repositories,
          require_signed_commits: policies.require_signed_commits,
        }),
      });
      setPolicies(saved);
      setPolicyMessage("Governance policy saved.");
    } catch (error) {
      setPolicyError(formatErrorMessage(error));
    } finally {
      setSavingPolicies(false);
    }
  };

  return (
    <AppShell isPublic>
      <Page
        eyebrow="Organization Settings"
        title="Enterprise Controls"
        description={organization ? `Manage compliance, security policies, and identity access for ${organization.display_name || organization.name}.` : "Manage compliance, security policies, and identity access."}
      >
      <div style={{ display: "flex", gap: "20px", marginBottom: "20px" }}>
        <button 
          onClick={() => setActiveTab("audit")}
          className="btn"
          style={{ background: activeTab === "audit" ? "var(--bg-subtle)" : "transparent", border: activeTab === "audit" ? "1px solid var(--border)" : "1px solid transparent" }}
        >
          <Activity size={14} /> Audit Logs
        </button>
        <button 
          onClick={() => setActiveTab("governance")}
          className="btn"
          style={{ background: activeTab === "governance" ? "var(--bg-subtle)" : "transparent", border: activeTab === "governance" ? "1px solid var(--border)" : "1px solid transparent" }}
        >
          <ShieldCheck size={14} /> Governance
        </button>
        <button 
          onClick={() => setActiveTab("sso")}
          className="btn"
          style={{ background: activeTab === "sso" ? "var(--bg-subtle)" : "transparent", border: activeTab === "sso" ? "1px solid var(--border)" : "1px solid transparent" }}
        >
          <Key size={14} /> Single Sign-On
        </button>
      </div>

      {loading ? (
        <Card className="text-center py-8">
          <p className="sub">Loading enterprise configuration...</p>
        </Card>
      ) : (
        <>
          {activeTab === "audit" && (
            <Card style={{ padding: 0 }}>
              <div style={{ padding: "15px", borderBottom: "1px solid var(--border-subtle)", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <h3 style={{ margin: 0 }}>Immutable Audit Feed</h3>
                <div style={{ position: "relative" }}>
                  <Search size={14} style={{ position: "absolute", left: "10px", top: "50%", transform: "translateY(-50%)", color: "var(--fg-muted)" }} />
                  <input type="text" placeholder="Filter logs..." style={{ paddingLeft: "32px", fontSize: "0.85rem" }} className="btn" />
                </div>
              </div>
              <table style={{ width: "100%", borderCollapse: "collapse", textAlign: "left", fontSize: "0.9rem" }}>
                <thead>
                  <tr style={{ borderBottom: "1px solid var(--border-subtle)", background: "var(--bg-subtle)" }}>
                    <th style={{ padding: "12px 15px", fontWeight: 500 }} className="sub">Timestamp</th>
                    <th style={{ padding: "12px 15px", fontWeight: 500 }} className="sub">Actor</th>
                    <th style={{ padding: "12px 15px", fontWeight: 500 }} className="sub">Action</th>
                    <th style={{ padding: "12px 15px", fontWeight: 500 }} className="sub">Resource</th>
                    <th style={{ padding: "12px 15px", fontWeight: 500 }} className="sub">IP Address</th>
                  </tr>
                </thead>
                <tbody>
                  {auditLogs.length === 0 ? (
                    <tr>
                      <td colSpan={5} style={{ padding: "30px", textAlign: "center" }} className="dim">No audit logs found.</td>
                    </tr>
                  ) : (
                    auditLogs.map((log) => (
                      <tr key={log.id} style={{ borderBottom: "1px solid var(--border-subtle)" }}>
                        <td style={{ padding: "12px 15px", fontFamily: "monospace" }}>{formatDate(log.timestamp)}</td>
                        <td style={{ padding: "12px 15px", display: "flex", alignItems: "center", gap: "8px" }}>
                          <div style={{ width: "20px", height: "20px", borderRadius: "10px", background: "var(--bg-subtle)", display: "flex", alignItems: "center", justifyContent: "center" }}>
                            {log.actor_name[0].toUpperCase()}
                          </div>
                          {log.actor_name}
                        </td>
                        <td style={{ padding: "12px 15px" }}><Badge tone="dim">{log.action}</Badge></td>
                        <td style={{ padding: "12px 15px" }}>{log.resource_name}</td>
                        <td style={{ padding: "12px 15px", fontFamily: "monospace", color: "var(--fg-muted)" }}>{log.ip_address}</td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </Card>
          )}

          {activeTab === "governance" && policies && (
            <div className="grid grid2" style={{ gap: "20px" }}>
              <Card>
                <div className="sectionhead">
                  <Shield size={18} className="purple" />
                  <h3>Global Branch Protection</h3>
                </div>
                  <p className="sub" style={{ marginBottom: "20px" }}>Set the organization default. Repository-specific branch protection rules can still be stricter.</p>
                
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "12px", background: "var(--bg-subtle)", borderRadius: "6px" }}>
                  <span>Enforce Branch Protection</span>
                  <label style={{ display: "flex", alignItems: "center", cursor: "pointer" }}>
                    <input type="checkbox" checked={policies.enforce_branch_protection} onChange={(event) => setPolicies({ ...policies, enforce_branch_protection: event.target.checked })} style={{ transform: "scale(1.2)" }} />
                  </label>
                </div>
              </Card>

              <Card>
                <div className="sectionhead">
                  <Users size={18} className="cyan" />
                  <h3>Pull Request Approvals</h3>
                </div>
                <p className="sub" style={{ marginBottom: "20px" }}>Mandate a minimum number of approvals for a Pull Request to be mergable.</p>
                
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "12px", background: "var(--bg-subtle)", borderRadius: "6px" }}>
                  <span>Required Approvals</span>
                  <select className="select" value={policies.minimum_pr_approvals} onChange={(event) => setPolicies({ ...policies, minimum_pr_approvals: Number(event.target.value) })}>
                    <option value="0">0 (No approvals)</option>
                    <option value="1">1 Approval</option>
                    <option value="2">2 Approvals</option>
                    <option value="3">3 Approvals</option>
                  </select>
                </div>
              </Card>
              <div style={{ gridColumn: "1 / -1" }}>
                {policyError && <p className="statusline red" role="alert">{policyError}</p>}
                {policyMessage && <p className="statusline green" role="status">{policyMessage}</p>}
                <button className="btn primary" onClick={savePolicies} disabled={savingPolicies}>
                  {savingPolicies ? "Saving..." : "Save governance policy"}
                </button>
              </div>
            </div>
          )}

          {activeTab === "sso" && (
            <Card style={{ padding: 0 }}>
              <div style={{ padding: "20px", borderBottom: "1px solid var(--border-subtle)" }}>
                <h3 style={{ margin: "0 0 5px 0" }}>Identity Providers</h3>
                <p className="sub" style={{ margin: 0 }}>Manage external IdPs (SAML/OIDC) for single sign-on access to the workspace.</p>
              </div>
              
              <div style={{ padding: "20px", display: "flex", flexDirection: "column", gap: "15px" }}>
                {ssoProviders.map(provider => (
                  <div key={provider.id} style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "15px", border: "1px solid var(--border)", borderRadius: "8px" }}>
                    <div style={{ display: "flex", alignItems: "center", gap: "15px" }}>
                      <div style={{ width: "40px", height: "40px", borderRadius: "8px", background: "var(--bg-subtle)", display: "flex", alignItems: "center", justifyContent: "center" }}>
                        <Key size={20} className="dim" />
                      </div>
                      <div>
                        <h4 style={{ margin: "0 0 2px 0" }}>{provider.name}</h4>
                        <div className="sub" style={{ fontSize: "0.85rem" }}>
                          {provider.type.toUpperCase()} &middot; {provider.domain}
                        </div>
                      </div>
                    </div>
                    <div style={{ display: "flex", alignItems: "center", gap: "15px" }}>
                      <Badge tone={provider.is_active ? "green" : "dim"}>
                        {provider.is_active ? "Active" : "Inactive"}
                      </Badge>
                      <button className="btn">Configure</button>
                    </div>
                  </div>
                ))}
              </div>
            </Card>
          )}
        </>
      )}
      </Page>
    </AppShell>
  );
}
