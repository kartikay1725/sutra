import { apiAuth } from "./api";

export const codeService = {
  async listFiles(repoId: string, path: string = ""): Promise<any[]> {
    return apiAuth<any[]>(`/v1/repositories/${repoId}/tree/${encodeURIComponent(path)}`).catch(() => []);
  },
  async getKnowledgeGraph(username: string, repoId: string): Promise<any> {
    return apiAuth<any>(`/v1/repositories/${username}/${repoId}/graph`).catch(() => null);
  }
};
