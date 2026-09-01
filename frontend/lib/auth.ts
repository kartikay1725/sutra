import { apiPublic, apiAuth } from "./api";

export interface User {
  id: string;
  username: string;
  email: string;
  full_name?: string | null;
  bio?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
}

export interface CurrentUser {
  id: string;
  username: string;
  email: string;
  full_name?: string | null;
  bio?: string | null;
  social_links?: Record<string, string>;
  created_at?: string;
}

export interface AuthResponse {
  access_token: string;
  token_type: string;
}

export interface RegisterResponse {
  message: string;
  email: string;
  email_verified: boolean;
}

export interface MessageResponse {
  message: string;
}

export const authService = {
  async register(username: string, email: string, password: string): Promise<RegisterResponse> {
    if (typeof window !== "undefined") {
      localStorage.removeItem("sutra_token");
    }
    return apiPublic<RegisterResponse>("/v1/auth/register", {
      method: "POST",
      body: JSON.stringify({ username, email, password }),
    });
  },

  async verifyEmail(email: string, otp: string): Promise<AuthResponse> {
    const data = await apiPublic<AuthResponse>("/v1/auth/verify-email", {
      method: "POST",
      body: JSON.stringify({ email, otp }),
    });
    if (data.access_token) {
      this.setToken(data.access_token);
    }
    return data;
  },

  async resendOtp(email: string): Promise<MessageResponse> {
    return apiPublic<MessageResponse>("/v1/auth/resend-otp", {
      method: "POST",
      body: JSON.stringify({ email }),
    });
  },

  async forgotPassword(email: string): Promise<MessageResponse> {
    return apiPublic<MessageResponse>("/v1/auth/forgot-password", {
      method: "POST",
      body: JSON.stringify({ email }),
    });
  },

  async resetPassword(token: string, email: string, newPassword: string): Promise<MessageResponse> {
    return apiPublic<MessageResponse>("/v1/auth/reset-password", {
      method: "POST",
      body: JSON.stringify({ token, email, new_password: newPassword }),
    });
  },

  async login(username: string, password: string): Promise<AuthResponse> {
    const data = await apiPublic<AuthResponse>("/v1/auth/login", {
      method: "POST",
      body: JSON.stringify({ login: username, password }),
    });
    this.setToken(data.access_token);
    return data;
  },

  async logout(): Promise<void> {
    try {
      await apiAuth("/v1/auth/logout", { method: "POST" });
    } catch (_) {
      // Ignore backend errors; always clear token locally
    } finally {
      if (typeof window !== "undefined") {
        localStorage.removeItem("sutra_token");
      }
    }
  },

  setToken(token: string) {
    if (typeof window !== "undefined") {
      localStorage.setItem("sutra_token", token);
    }
  },

  getToken(): string | null {
    if (typeof window !== "undefined") {
      return localStorage.getItem("sutra_token");
    }
    return null;
  },

  isAuthenticated(): boolean {
    return !!this.getToken();
  },

  async getCurrentUser(): Promise<User> {
    return apiAuth<User>("/v1/auth/me", { method: "GET" });
  },

  async updateProfile(data: { full_name?: string; email?: string; bio?: string }): Promise<User> {
    return apiAuth<User>("/v1/auth/me", {
      method: "PATCH",
      body: JSON.stringify(data),
    });
  },
};
