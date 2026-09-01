import { apiAuth } from "./api";

export interface Thread {
  id: string;
  repository_id: string;
  user_id: string;
  title: string;
}

export interface Message {
  id: string;
  thread_id: string;
  role: string;
  content: string;
}

export const assistantService = {
  async listThreads(username: string, repo: string): Promise<Thread[]> {
    return apiAuth<Thread[]>(`/v1/repositories/${username}/${repo}/assistant/threads`);
  },

  async createThread(username: string, repo: string, title: string): Promise<Thread> {
    return apiAuth<Thread>(`/v1/repositories/${username}/${repo}/assistant/threads`, {
      method: 'POST',
      body: JSON.stringify({ title })
    });
  },

  async listMessages(threadId: string): Promise<Message[]> {
    return apiAuth<Message[]>(`/v1/assistant/threads/${threadId}/messages`);
  },

  async createMessage(threadId: string, content: string): Promise<Message[]> {
    return apiAuth<Message[]>(`/v1/assistant/threads/${threadId}/messages`, {
      method: 'POST',
      body: JSON.stringify({ content })
    });
  }
};
