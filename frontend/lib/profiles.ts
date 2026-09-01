import { apiPublic } from "./api";

export interface ContributionDay {
  date: string;
  count: number;
}

export interface ContributionGraph {
  total_contributions: number;
  days: ContributionDay[];
}

export interface PublicRepository {
  id: string;
  name: string;
  description: string | null;
  visibility: "public" | "private";
  default_branch: string;
  updated_at: string;
}

export interface SocialLinks {
  github?: string;
  linkedin?: string;
  x?: string;
  instagram?: string;
  reddit?: string;
  youtube?: string;
  website?: string;
}

export interface Profile {
  id: string;
  username: string;
  type?: string;

  followers?: number;
  following?: number;

  full_name?: string | null;
  bio?: string | null;

  social_links: SocialLinks;

  created_at?: string;

  repositories: PublicRepository[];

  public_repository_count: number;
  pull_request_count: number;
  issue_count: number;
}

export const profileService = {
  async getProfile(
    username: string,
  ): Promise<Profile> {
    return apiPublic<Profile>(
      `/v1/profiles/${encodeURIComponent(
        username,
      )}`,
    );
  },

  async getContributions(
    username: string,
  ): Promise<ContributionGraph> {
    return apiPublic<ContributionGraph>(
      `/v1/profiles/${encodeURIComponent(
        username,
      )}/contributions`,
    );
  },
};