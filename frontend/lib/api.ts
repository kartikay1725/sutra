const CANONICAL_PRODUCTION_API_URL = "https://api.sutra.sudarshanai.com";

function getApiUrl(): string {
  if (process.env.NEXT_PUBLIC_API_URL && process.env.NEXT_PUBLIC_API_URL.trim()) {
    return process.env.NEXT_PUBLIC_API_URL.replace(/\/+$/, "");
  }

  if (typeof window !== "undefined") {
    return "/api";
  }

  return CANONICAL_PRODUCTION_API_URL;
}

export class SutraAPIError extends Error {
  status: number;
  detail: string | any;

  constructor(status: number, detail: string | any) {
    let cleanMessage = typeof detail === "string" ? detail : (detail?.message || detail?.detail || JSON.stringify(detail));
    super(cleanMessage || `Request failed with status ${status}`);
    this.name = "SutraAPIError";
    this.status = status;
    this.detail = detail;
  }
}

/**
 * Universal error formatter that returns clean, user-friendly messages for any error type.
 */
export function formatErrorMessage(err: unknown): string {
  if (!err) {
    return "An unexpected error occurred. Please try again.";
  }

  if (err instanceof SutraAPIError) {
    if (typeof err.detail === "string" && err.detail.trim().length > 0) {
      return err.detail;
    }
    if (err.status === 401) {
      return "Your session has expired or credentials are invalid. Please sign in again.";
    }
    if (err.status === 403) {
      return typeof err.detail === "string" ? err.detail : "You do not have permission to perform this action.";
    }
    if (err.status === 404) {
      return "The requested resource was not found.";
    }
    if (err.status === 409) {
      return typeof err.detail === "string" ? err.detail : "A conflict occurred with the current state.";
    }
    if (err.status === 429) {
      return "Too many requests. Please wait a moment before trying again.";
    }
    if (err.status >= 500) {
      return "A server error occurred. Our team has been notified. Please try again shortly.";
    }
    return err.message;
  }

  if (err instanceof TypeError && err.message.toLowerCase().includes("fetch")) {
    return "Unable to connect to SUTRA. Please check your internet connection or server status.";
  }

  if (err instanceof Error && err.message) {
    return err.message;
  }

  return "An unexpected error occurred. Please try again.";
}

async function fetchWithHandler<T>(path: string, init?: RequestInit): Promise<T> {
  const baseUrl = getApiUrl();
  const url = `${baseUrl}${path}`;

  let response: Response;
  try {
    response = await fetch(url, {
      ...init,
      headers: {
        "Content-Type": "application/json",
        ...(init?.headers || {})
      }
    });
  } catch (e: any) {
    throw new SutraAPIError(0, "Unable to reach server. Please check your network connection.");
  }

  if (!response.ok) {
    let detail = response.statusText;
    try {
      const errorData = await response.json();
      detail = errorData.detail || errorData.message || errorData;
    } catch (e) {
      // JSON parse fallback
    }
    throw new SutraAPIError(response.status, detail);
  }

  if (response.status === 204) {
    return {} as T;
  }

  try {
    return await response.json();
  } catch (e) {
    return {} as T;
  }
}

export async function apiPublic<T>(path: string, init?: RequestInit): Promise<T> {
  return fetchWithHandler<T>(path, init);
}

export async function apiAuth<T>(path: string, init?: RequestInit): Promise<T> {
  let token = null;

  if (typeof window !== "undefined") {
    token = localStorage.getItem("sutra_token");
  }

  const headers: Record<string, string> = {
    ...(init?.headers as Record<string, string> || {})
  };

  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  return fetchWithHandler<T>(path, { ...init, headers });
}

export const API_URL = process.env.NEXT_PUBLIC_API_URL || CANONICAL_PRODUCTION_API_URL;
export { getApiUrl };
