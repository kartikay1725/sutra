import { Building, Users, FolderGit2 } from "lucide-react";
import { Page, Card, Badge } from "@/components/ui";
import { apiPublic } from "@/lib/api";
import Link from "next/link";
import { notFound } from "next/navigation";

async function getOrganization(orgName: string) {
  try {
    return await apiPublic<any>(`/v1/organizations/${orgName}`);
  } catch (e) {
    return null;
  }
}

async function getOrganizationMembers(orgName: string) {
  try {
    return await apiPublic<any[]>(`/v1/organizations/${orgName}/members`);
  } catch (e) {
    return [];
  }
}

async function getOrganizationRepositories(orgName: string) {
  try {
    return await apiPublic<any[]>(`/v1/repositories/${orgName}`);
  } catch (e) {
    return [];
  }
}

export default async function OrganizationPage({ params }: { params: { org_name: string } }) {
  const [org, members, repositories] = await Promise.all([
    getOrganization(params.org_name),
    getOrganizationMembers(params.org_name),
    getOrganizationRepositories(params.org_name)
  ]);

  if (!org) {
    notFound();
  }

  return (
    <Page 
      eyebrow="Organization" 
      title={org.display_name || org.name} 
      description={org.description || "No description provided."}
    >
      <div className="grid" style={{ gridTemplateColumns: "1fr 300px", gap: "20px" }}>
        <div style={{ display: "flex", flexDirection: "column", gap: "20px" }}>
          <Card className="section">
            <div className="sectionhead" style={{ marginBottom: "15px" }}>
              <FolderGit2 size={20} className="cyan" />
              <h2 style={{ display: "inline-block", marginLeft: "10px" }}>Repositories</h2>
            </div>
            
            {repositories.length > 0 ? (
              <div className="grid grid1" style={{ gap: "10px" }}>
                {repositories.map((repo: any) => (
                  <Link key={repo.id} href={`/${repo.owner_username || org.name}/${repo.name}`} className="no-underline">
                    <Card className="hover-card transition-all" style={{ padding: "15px" }}>
                      <h3 style={{ margin: "0 0 5px 0", fontSize: "1.1rem" }}>{repo.name}</h3>
                      <div className="sub">{repo.description || "No description"}</div>
                      <div style={{ marginTop: "10px", display: "flex", gap: "10px", alignItems: "center" }}>
                        <Badge tone={repo.visibility === "public" ? "green" : "red"}>
                          {repo.visibility}
                        </Badge>
                      </div>
                    </Card>
                  </Link>
                ))}
              </div>
            ) : (
              <div className="sub text-center py-4">No repositories found.</div>
            )}
          </Card>
        </div>

        <div style={{ display: "flex", flexDirection: "column", gap: "20px" }}>
          <Card>
            <div className="statusline" style={{ marginBottom: "15px" }}>
              <Users size={16} className="purple"/>
              <strong>Members ({members.length})</strong>
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
              {members.map((member: any) => (
                <div key={member.user_id} style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                  <Link href={`/profile/${member.user_id}`} style={{ fontWeight: 500 }}>
                    User {member.user_id.slice(0, 6)}
                  </Link>
                  <Badge tone={member.role === "owner" ? "cyan" : "dim"}>{member.role}</Badge>
                </div>
              ))}
            </div>
          </Card>
        </div>
      </div>
    </Page>
  );
}
