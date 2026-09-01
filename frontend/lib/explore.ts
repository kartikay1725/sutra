import { apiPublic } from "./api";

export interface TrendingRepository {
  id: string;
  owner: string;
  name: string;
  description: string | null;
  stars: number;
  language: string | null;
}

export interface SearchResult {
  type: string;
  name: string;
  description: string | null;
  url: string;
}

export async function getTrendingRepositories(since: "daily" | "weekly" | "monthly" = "daily"): Promise<TrendingRepository[]> {
  return apiPublic<TrendingRepository[]>(`/v1/explore/trending/repositories?since=${since}`);
}

export async function search(query: string): Promise<SearchResult[]> {
  return apiPublic<SearchResult[]>(`/v1/search?q=${encodeURIComponent(query)}`);
}

export interface TrendingDiscussion {
  id: string;
  title: string;
  repo_name: string;
  author: string;
  comments_count: number;
}

export interface TrendingAgent {
  id: string;
  name: string;
  description: string;
  runs: number;
}

export async function getTrendingDiscussions(): Promise<TrendingDiscussion[]> {
  return apiPublic<TrendingDiscussion[]>("/v1/explore/trending/discussions");
}

export async function getTrendingAgents(): Promise<TrendingAgent[]> {
  return apiPublic<TrendingAgent[]>("/v1/explore/trending/agents");
}

export const exploreService = {
  getTrendingRepositories,
  getTrendingDiscussions,
  getTrendingAgents,
  search
};
