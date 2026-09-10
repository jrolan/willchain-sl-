import type { ApiError, AuthResponse, User } from "@/types/auth";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/api/v1";
let accessToken: string | null = null;

function csrfToken(): string | undefined {
  if (typeof document === "undefined") return undefined;
  return document.cookie
    .split("; ")
    .find((cookie) => cookie.startsWith("csrftoken="))
    ?.split("=")[1];
}

async function parseResponse<T>(response: Response): Promise<T> {
  if (response.ok) return response.status === 204 ? (undefined as T) : response.json();
  const error = (await response.json().catch(() => ({}))) as ApiError;
  throw new Error(error.error?.message ?? error.detail ?? "The request could not be completed.");
}

async function request<T>(path: string, init: RequestInit = {}, retry = true): Promise<T> {
  const headers = new Headers(init.headers);
  headers.set("Content-Type", "application/json");
  if (accessToken) headers.set("Authorization", `Bearer ${accessToken}`);

  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers,
    credentials: "include",
  });

  if (response.status === 401 && retry && !path.includes("/login") && !path.includes("/refresh")) {
    await refreshAccessToken();
    return request<T>(path, init, false);
  }
  return parseResponse<T>(response);
}

export async function register(payload: Record<string, string>): Promise<{ data: User }> {
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
  await request("/auth/logout/", { method: "POST" });
  accessToken = null;
}

export function getProfile(): Promise<{ data: User }> {
  return request("/auth/me/");
}

export function updateProfile(payload: Pick<User, "first_name" | "last_name" | "phone_number">): Promise<{ data: User }> {
  return request("/auth/me/", { method: "PATCH", body: JSON.stringify(payload) });
}
