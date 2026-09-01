import { apiAuth } from "./api";

export interface NotificationItem {
  id: string;
  title: string;
  message: string | null;
  type: string;
  link: string | null;
  is_read: boolean;
  created_at: string;
}

export const notificationService = {
  async getNotifications(): Promise<NotificationItem[]> {
    return apiAuth<NotificationItem[]>("/v1/notifications");
  },

  async markAsRead(id: string): Promise<void> {
    return apiAuth<void>(`/v1/notifications/${id}/read`, { method: "POST" });
  },

  async markAllAsRead(): Promise<void> {
    return apiAuth<void>("/v1/notifications/read-all", { method: "POST" });
  }
};
