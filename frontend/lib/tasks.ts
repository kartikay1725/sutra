import { apiAuth } from "./api";

export interface Task {
  id: string;
  repository_id: string;
  repository_name?: string;
  title: string;
  description: string;
  status: string; // 'todo', 'in_progress', 'done'
  assignee_id: string;
  assigned_agent_id?: string;
  assigned_agent_name?: string;
  active_session_id?: string;
  target_branch?: string;
  issue_id?: string;
  resulting_change_id?: string;
  resulting_pull_request_id?: string;
  source?: string; // 'user' | 'agent'
  created_by?: string;
  claimed_by_session_id?: string;
  lease_expires_at?: string;
  priority?: string;
  task_type?: string;
  execution_summary?: string;
  validation_summary?: string;
  started_at?: string;
  completed_at?: string;
  cancelled_at?: string;
  created_at: string;
  updated_at: string;
}

export const taskService = {
  async listAllTasks(search?: string): Promise<Task[]> {
    const query = search && search.trim() ? `?q=${encodeURIComponent(search.trim())}` : "";
    return apiAuth<Task[]>(`/v1/tasks${query}`);
  },

  async listTasks(username: string, repo: string, search?: string): Promise<Task[]> {
    const query = search && search.trim() ? `?q=${encodeURIComponent(search.trim())}` : "";
    return apiAuth<Task[]>(`/v1/repositories/${username}/${repo}/tasks${query}`);
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
  },

  async terminateTask(taskId: string, reason?: string): Promise<Task> {
    return apiAuth<Task>(`/v1/tasks/${taskId}/cancel`, {
      method: "POST",
      body: reason ? JSON.stringify({ reason }) : undefined,
    });
  }
};
