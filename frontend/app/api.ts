import "server-only";

const apiBase = process.env.API_BASE_URL ?? "http://127.0.0.1:8000";

export const sessionCookie = "metalflow_session";
export const sessionLifetime = 30 * 60;
export const sessionPattern = /^[a-f0-9-]{36}\.[A-Za-z0-9_-]{43}$/;

type Endpoint = "/auth/login" | "/auth/logout" | "/me" | "/tenant" | "/users" | "/audit-logs";

async function request(
  path: string,
  method: string,
  token?: string,
  body?: string | ArrayBuffer,
  contentType?: string,
) {
  try {
    return await fetch(new URL(`/api/v1${path}`, apiBase), {
      method,
      headers: {
        ...(token ? { authorization: `Bearer ${token}` } : {}),
        ...(contentType ? { "content-type": contentType } : {}),
      },
      body,
      cache: "no-store",
      redirect: "error",
      signal: AbortSignal.timeout(5000),
    });
  } catch {
    return null;
  }
}

export function apiRequest(path: Endpoint, token?: string, body?: object) {
  return request(
    path, path.startsWith("/auth/") ? "POST" : "GET", token,
    body ? JSON.stringify(body) : undefined,
    body ? "application/json" : undefined,
  );
}

type CrmEndpoint = "/customers" | `/customers/${string}` | `/customers?${string}`;

export const xlsxContentType = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet";

export function crmRequest(
  path: CrmEndpoint,
  token: string,
  method: "GET" | "POST" | "PATCH" = "GET",
  body?: object | ArrayBuffer,
) {
  return request(
    path,
    method,
    token,
    body instanceof ArrayBuffer ? body : body ? JSON.stringify(body) : undefined,
    body instanceof ArrayBuffer ? xlsxContentType : body ? "application/json" : undefined,
  );
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
