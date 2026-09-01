import { apiAuth, apiPublic } from "./api";

export interface Branch {
  name: string;
  commit: string;
}

export interface TreeEntry {
  type: "blob" | "tree";
  name: string;
  path: string;
  size?: number;
}

export interface TreeResponse {
  entries: TreeEntry[];
  ref: string;
  path: string;
}

export interface FileResponse {
  path: string;
  content: string;
  size: number;
  ref: string;
}

export interface Commit {
  sha: string;
  message: string;
  author_name: string;
  author_email: string;
  timestamp: string;
}

export const browserService = {
  async getBranches(owner: string, repo: string): Promise<{ repository_id: string; default_branch: string; branches: Branch[] }> {
    return apiAuth(`/v1/repositories/${owner}/${repo}/branches`, { method: "GET" });
  },

  async getTree(owner: string, repo: string, ref?: string, path: string = ""): Promise<TreeResponse> {
    const params = new URLSearchParams();
    if (ref) params.append("ref", ref);
    if (path) params.append("path", path);
    return apiAuth(`/v1/repositories/${owner}/${repo}/tree?${params.toString()}`, { method: "GET" });
  },

  async getFile(owner: string, repo: string, path: string, ref?: string): Promise<FileResponse> {
    const params = new URLSearchParams();
    params.append("path", path);
    if (ref) params.append("ref", ref);
    return apiAuth(`/v1/repositories/${owner}/${repo}/file?${params.toString()}`, { method: "GET" });
  },

  async getCommits(owner: string, repo: string, ref?: string, limit: number = 30): Promise<Commit[]> {
    const params = new URLSearchParams();
    if (ref) params.append("ref", ref);
    params.append("limit", limit.toString());
    return apiAuth(`/v1/repositories/${owner}/${repo}/commits?${params.toString()}`, { method: "GET" });
  }
};
