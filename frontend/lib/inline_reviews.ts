import { apiAuth } from "./api";

export interface InlineComment {
  id: string;
  pull_request_id: string;
  author_id: string;
  parent_id?: string;
  path?: string;
  diff_side?: string;
  line_number?: number;
  body: string;
  status: string; // 'active', 'resolved'
  created_at: string;
}

export interface DiffHunk {
  old_start: number;
  old_count: number;
  new_start: number;
  new_count: number;
  lines: string[];
}

export interface DiffFile {
  old_path: string;
  new_path: string;
  path: string;
  is_binary: boolean;
  hunks: DiffHunk[];
}

export const inlineReviewService = {
  async getComments(prId: string): Promise<InlineComment[]> {
    const res = await apiAuth<{ comments: InlineComment[] }>(`/v1/pull-requests/${prId}/comments`);
    return res.comments;
  },

  async getDiff(prId: string): Promise<{ files: DiffFile[] }> {
    return apiAuth<{ files: DiffFile[] }>(`/v1/pull-requests/${prId}/diff`);
  },

  async getFiles(prId: string): Promise<{ files: any[] }> {
    return apiAuth<{ files: any[] }>(`/v1/pull-requests/${prId}/files`);
  }
};
