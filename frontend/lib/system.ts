import { apiAuth } from "./api";

export const systemService = {
  async getAuditLogs(orgId: string): Promise<any[]> {
    return apiAuth<any[]>(`/v1/organizations/${orgId}/audit-logs`).catch(() => []);
  },
  async getGovernancePolicies(orgId: string): Promise<any[]> {
    return apiAuth<any[]>(`/v1/organizations/${orgId}/policies`).catch(() => []);
  },
  async listMarketplacePlugins(): Promise<any[]> {
    return apiAuth<any[]>("/v1/marketplace/plugins").catch(() => []);
  }
};
