import { apiAuth } from "./api";

export interface Organization {
  id: string;
  name: string;
  display_name: string;
  description: string;
  billing_plan: string;
}

export interface OrganizationMember {
  user_id: string;
  username: string;
  role: string;
  joined_at: string;
}

export const organizationService = {
  async listMyOrganizations(): Promise<Organization[]> {
    return apiAuth<Organization[]>("/v1/organizations/mine");
  },

  async getOrganization(orgName: string): Promise<Organization> {
    return apiAuth<Organization>(`/v1/organizations/${orgName}`);
  },

  async getMembers(orgName: string): Promise<OrganizationMember[]> {
    return apiAuth<OrganizationMember[]>(`/v1/organizations/${orgName}/members`);
  }
};
