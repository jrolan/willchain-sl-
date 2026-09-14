import type { ApiError, AuthResponse, Invitation, InvitationDetail, User } from "@/types/auth";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/api/v1";
let accessToken: string | null = null;

export function getAccessToken(): string | null {
  return accessToken;
}

export function setAccessToken(token: string | null): void {
  accessToken = token;
}

function csrfToken(): string | undefined {
  if (typeof document === "undefined") return undefined;
  return document.cookie
    .split("; ")
    .find((cookie) => cookie.startsWith("csrftoken="))
    ?.split("=")[1];
}

async function parseResponse<T>(response: Response): Promise<T> {
  if (response.ok) return response.status === 204 ? (undefined as T) : response.json();
  const raw = (await response.json().catch(() => ({}))) as Record<string, any>;
  let message = raw.error?.message ?? raw.detail ?? raw.message;
  if (!message && typeof raw === "object") {
    const firstKey = Object.keys(raw)[0];
    if (firstKey) {
      const val = raw[firstKey];
      message = Array.isArray(val) ? val.join(" ") : String(val);
    }
  }
  throw new Error(message || "The request could not be completed.");
}

async function request<T>(path: string, init: RequestInit = {}, retry = true): Promise<T> {
  const headers = new Headers(init.headers);
  if (!(init.body instanceof FormData)) headers.set("Content-Type", "application/json");
  if (accessToken) headers.set("Authorization", `Bearer ${accessToken}`);

  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      ...init,
      headers,
      credentials: "include",
    });
  } catch {
    throw new Error(`Unable to reach the WillChain server at ${API_BASE_URL}. Make sure the backend is running.`);
  }

  if (response.status === 401 && retry && !path.includes("/login") && !path.includes("/refresh")) {
    try {
      await refreshAccessToken();
      return request<T>(path, init, false);
    } catch {
      accessToken = null;
      throw new Error("Your session has expired. Please sign in again.");
    }
  }
  return parseResponse<T>(response);
}

export async function register(payload: Record<string, string>): Promise<{ data: User; message: string }> {
  return request("/auth/register/", { method: "POST", body: JSON.stringify(payload) });
}

export async function login(email: string, password: string): Promise<User> {
  const response = await request<AuthResponse>("/auth/login/", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });
  accessToken = response.data.access;
  return response.data.user;
}

export async function refreshAccessToken(): Promise<void> {
  const headers = new Headers();
  const token = csrfToken();
  if (token) headers.set("X-CSRFToken", token);
  const response = await fetch(`${API_BASE_URL}/auth/token/refresh/`, {
    method: "POST",
    headers,
    credentials: "include",
  });
  const result = await parseResponse<{ data: { access: string } }>(response);
  accessToken = result.data.access;
}

export async function logout(): Promise<void> {
  try {
    await request("/auth/logout/", { method: "POST" });
  } finally {
    accessToken = null;
  }
}

function normalizeUserResponse(response: User | { data: User }): { data: User } {
  return "data" in response ? response : { data: response };
}

export async function getProfile(): Promise<{ data: User }> {
  return normalizeUserResponse(await request<User | { data: User }>("/auth/me/"));
}

export async function updateProfile(payload: FormData | Pick<User, "first_name" | "last_name" | "phone_number">): Promise<{ data: User }> {
  return normalizeUserResponse(await request<User | { data: User }>("/auth/me/", {
    method: "PATCH",
    body: payload instanceof FormData ? payload : JSON.stringify(payload),
  }));
}

export async function changePassword(payload: { current_password: string; new_password: string; new_password_confirmation: string }): Promise<{ message: string }> {
  return request("/auth/change-password/", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function forgotPassword(email: string): Promise<{ message: string }> {
  return request("/auth/forgot-password/", {
    method: "POST",
    body: JSON.stringify({ email }),
  });
}

export async function resetPassword(payload: { uid: string; token: string; new_password: string; new_password_confirmation: string }): Promise<{ message: string }> {
  return request("/auth/reset-password/", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function verifyEmail(payload: { uid: string; token: string }): Promise<{ data: User; message: string }> {
  return request("/auth/verify-email/", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function getInvitations(): Promise<{ data: Invitation[] }> {
  return request("/auth/invitations/");
}

export async function sendInvitation(payload: { email: string; first_name?: string; last_name?: string; role: string; message?: string }): Promise<{ data: Invitation; message: string }> {
  return request("/auth/invitations/", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function getInvitationDetail(token: string): Promise<{ data: InvitationDetail }> {
  return request(`/auth/invitations/accept/?token=${encodeURIComponent(token)}`);
}

export async function acceptInvitation(payload: { token: string; first_name?: string; last_name?: string; phone_number?: string; password: string; password_confirmation: string }): Promise<{ data: { access: string; user: User }; message: string }> {
  const result = await request<{ data: { access: string; user: User }; message: string }>("/auth/invitations/accept/", {
    method: "POST",
    body: JSON.stringify(payload),
  });
  accessToken = result.data.access;
  return result;
}
