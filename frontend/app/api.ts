import "server-only";

const apiBase = process.env.API_BASE_URL ?? "http://127.0.0.1:8000";

export const sessionCookie = "metalflow_session";
export const sessionLifetime = 30 * 60;
export const sessionPattern = /^[a-f0-9-]{36}\.[A-Za-z0-9_-]{43}$/;

type Endpoint = "/auth/login" | "/auth/logout" | "/me" | "/tenant" | "/users" | "/audit-logs";

export async function apiRequest(path: Endpoint, token?: string, body?: object) {
  try {
    return await fetch(new URL(`/api/v1${path}`, apiBase), {
      method: path.startsWith("/auth/") ? "POST" : "GET",
      headers: {
        ...(token ? { authorization: `Bearer ${token}` } : {}),
        ...(body ? { "content-type": "application/json" } : {}),
      },
      body: body ? JSON.stringify(body) : undefined,
      cache: "no-store",
      redirect: "error",
      signal: AbortSignal.timeout(5000),
    });
  } catch {
    return null;
  }
}

export async function readResponse<T>(
  response: Response | null,
  accepts: (value: unknown) => value is T,
): Promise<T | null> {
  if (!response?.ok) return null;
  const data: unknown = await response.json().catch(() => null);
  return accepts(data) ? data : null;
}

export function record(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}
