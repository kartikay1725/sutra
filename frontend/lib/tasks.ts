import { apiAuth } from "./api";

export interface Task {
  id: string;
  repository_id: string;
  title: string;
  description: string;
  status: string; // 'todo', 'in_progress', 'done'
  assignee_id: string;
  assigned_agent_id?: string;
  active_session_id?: string;
  issue_id?: string;
  resulting_change_id?: string;
  resulting_pull_request_id?: string;
  started_at?: string;
  completed_at?: string;
  created_at: string;
  updated_at: string;
}

export const taskService = {
  async listAllTasks(): Promise<Task[]> {
    return apiAuth<Task[]>("/v1/tasks");
  },

  async listTasks(username: string, repo: string): Promise<Task[]> {
    return apiAuth<Task[]>(`/v1/repositories/${username}/${repo}/tasks`);
  },
  
  async getTask(taskId: string): Promise<Task> {
    return apiAuth<Task>(`/v1/tasks/${taskId}`);
  },

  async assignTask(taskId: string, agentId: string): Promise<Task> {
    return apiAuth<Task>(`/v1/tasks/${taskId}/assign`, {
      method: "POST",
      body: JSON.stringify({ assigned_agent_id: agentId })
    });
  },

  async createTask(username: string, repo: string, payload: { title: string; description: string; priority?: string; task_type?: string }): Promise<Task> {
    return apiAuth<Task>(`/v1/repositories/${username}/${repo}/tasks`, {
      method: "POST",
      body: JSON.stringify(payload)
    });
  },

  async deleteTask(taskId: string): Promise<void> {
    return apiAuth<void>(`/v1/tasks/${taskId}`, {
      method: "DELETE"
    });
  }
};
