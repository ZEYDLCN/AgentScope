// AgentGuard FastAPI backend'ine sunucu tarafı istemci.
//
// `X-API-Key` YALNIZCA burada, sunucuda (Route Handler içinde) eklenir —
// tarayıcıya asla gönderilmez. Bu nedenle bu modül yalnızca
// `app/api/**/route.ts` dosyalarından, ya da diğer sunucu bileşenlerinden
// import edilmelidir; `"use client"` bileşenlerinden değil.

const BACKEND_URL = process.env.AGENTGUARD_API_URL ?? "http://localhost:8000";
const API_KEY = process.env.AGENTGUARD_API_KEY ?? "dev-local-key";

export class BackendError extends Error {
  status: number;
  body: unknown;

  constructor(status: number, body: unknown) {
    super(`AgentGuard API ${status}`);
    this.status = status;
    this.body = body;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${BACKEND_URL}${path}`, {
    ...init,
    headers: {
      "X-API-Key": API_KEY,
      ...(init?.body ? { "Content-Type": "application/json" } : {}),
      ...init?.headers,
    },
    cache: "no-store",
  });

  if (!response.ok) {
    let body: unknown = null;
    try {
      body = await response.json();
    } catch {
      // problem+json olmayan bir gövde olabilir
    }
    throw new BackendError(response.status, body);
  }

  if (response.status === 204) {
    return undefined as T;
  }
  return (await response.json()) as T;
}

export const backend = {
  get: <T>(path: string) => request<T>(path),
  post: <T>(path: string, body?: unknown) =>
    request<T>(path, { method: "POST", body: body ? JSON.stringify(body) : undefined }),
};

export function backendBaseUrl(): string {
  return BACKEND_URL;
}
