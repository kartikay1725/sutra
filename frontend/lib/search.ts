import { apiAuth } from "./api";

export interface SearchResult {
  type: string; // "repository", "user", "organization"
  name: string;
  description: string | null;
  url: string;
}

export const searchService = {
  async search(query: string): Promise<SearchResult[]> {
    if (!query || query.trim().length === 0) return [];
    return apiAuth<SearchResult[]>(`/v1/search?q=${encodeURIComponent(query)}`);
  }
};
