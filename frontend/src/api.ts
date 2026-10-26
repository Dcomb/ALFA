import type {
  ApplicationDocument,
  Client,
  ClientBrief,
  CreditApplication,
  Need,
  Recommendation,
} from "./types";

const API = "/api";

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const response = await fetch(`${API}${path}`, options);
  if (!response.ok) {
    let message = `Ошибка API: ${response.status}`;
    try {
      const body = await response.json();
      message = body.detail || body.error || message;
      if (body.missing?.length) message += `: ${body.missing.join(", ")}`;
    } catch {
      // Keep the HTTP fallback when the response is not JSON.
    }
    throw new Error(message);
  }
  return response.json() as Promise<T>;
}

const json = (body?: unknown): RequestInit => ({
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: body === undefined ? undefined : JSON.stringify(body),
});

const clientHeaders = (clientId: string) => ({ "X-Client-Id": clientId });

export const api = {
  products: () => request<Array<{ id: string; name: string }>>("/ranking/products"),

  clients: () => request<ClientBrief[]>("/clients"),

  profile: (clientId: string) =>
    request<Client>("/me", { headers: clientHeaders(clientId) }),

  register: (body: Record<string, string>) =>
    request<Client>("/clients/register", json(body)),

  applications: (clientId: string) =>
    request<CreditApplication[]>("/applications", {
      headers: clientHeaders(clientId),
    }),

  application: (clientId: string, applicationId: number) =>
    request<CreditApplication>(`/applications/${applicationId}`, {
      headers: clientHeaders(clientId),
    }),

  recommend: async (clientId: string, need: Need) => {
    const data = await request<{ recommendations: Recommendation[] }>(
      "/ranking/recommend",
      json({
        client_id: clientId,
        need: {
          purpose: need.purpose,
          amount: need.amount,
          term_months: need.term_months,
        },
        top_k: 3,
      }),
    );
    return data.recommendations;
  },

  createApplication: (clientId: string, body: Record<string, unknown>) =>
    request<CreditApplication>("/applications", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...clientHeaders(clientId),
      },
      body: JSON.stringify(body),
    }),

  updateApplication: (
    clientId: string,
    applicationId: number,
    body: Record<string, unknown>,
  ) =>
    request<CreditApplication>(`/applications/${applicationId}`, {
      method: "PATCH",
      headers: {
        "Content-Type": "application/json",
        ...clientHeaders(clientId),
      },
      body: JSON.stringify(body),
    }),

  submit: (clientId: string, applicationId: number) =>
    request<CreditApplication>(`/applications/${applicationId}/submit`, {
      ...json(),
      headers: clientHeaders(clientId),
    }),

  accept: (clientId: string, applicationId: number, option = 0) =>
    request<CreditApplication>(`/applications/${applicationId}/accept`, {
      ...json({ option }),
      headers: {
        "Content-Type": "application/json",
        ...clientHeaders(clientId),
      },
    }),

  finalize: (clientId: string, applicationId: number) =>
    request<CreditApplication>(`/applications/${applicationId}/finalize`, {
      ...json(),
      headers: clientHeaders(clientId),
    }),

  uploadDocument: async (
    clientId: string,
    applicationId: number,
    kind: string,
    file: File,
  ) => {
    const body = new FormData();
    body.append("file", file);
    return request<ApplicationDocument>(
      `/applications/${applicationId}/documents/${kind}`,
      {
        method: "POST",
        headers: clientHeaders(clientId),
        body,
      },
    );
  },

  chat: (clientId: string, threadId: string, message: string) =>
    request<{ response: string }>("/chat", {
      ...json({ client_id: clientId, thread_id: threadId, message }),
      headers: { "Content-Type": "application/json" },
    }),
};
