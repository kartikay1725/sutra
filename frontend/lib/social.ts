import { apiAuth } from "./api";

export async function starRepository(owner: string, repo: string): Promise<void> {
  return apiAuth<void>(`/v1/repositories/${owner}/${repo}/star`, {
    method: "POST"
  });
}

export async function unstarRepository(owner: string, repo: string): Promise<void> {
  return apiAuth<void>(`/v1/repositories/${owner}/${repo}/star`, {
    method: "DELETE"
  });
}

export async function followUser(username: string): Promise<void> {
  return apiAuth<void>(`/v1/users/${username}/follow`, {
    method: "POST"
  });
}

export async function unfollowUser(username: string): Promise<void> {
  return apiAuth<void>(`/v1/users/${username}/follow`, {
    method: "DELETE"
  });
}
