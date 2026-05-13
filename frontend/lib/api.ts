type RequestOptions = {
  method?: string;
  body?: unknown;
  token?: string;
};

async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const response = await fetch(path, {
    method: options.method || "GET",
    headers: {
      "Content-Type": "application/json",
      ...(options.token ? { Authorization: `Bearer ${options.token}` } : {})
    },
    body: options.body ? JSON.stringify(options.body) : undefined,
    cache: "no-store"
  });

  if (!response.ok) {
    let message = "Request failed";
    try {
      const data = await response.json();
      message = data.detail || message;
    } catch {
      message = response.statusText || message;
    }
    throw new Error(message);
  }

  return response.json() as Promise<T>;
}

export type Citation = {
  title: string;
  excerpt: string;
};

export type ChatResponse = {
  answer: string;
  citations: Citation[];
  mode: string;
};

export type DocumentItem = {
  id: number;
  title: string;
  content: string;
  tags: string[];
  source: string;
  updated_at: string;
};

export type StatsResponse = {
  documents: number;
  chunks: number;
  ai_provider: string;
  provider_ready: boolean;
  anthropic_configured: boolean;
  ollama_configured: boolean;
};

export async function sendChat(message: string): Promise<ChatResponse> {
  return request<ChatResponse>("/api/chat", {
    method: "POST",
    body: { message }
  });
}

export async function login(email: string, password: string): Promise<{ token: string; email: string }> {
  return request<{ token: string; email: string }>("/api/auth/login", {
    method: "POST",
    body: { email, password }
  });
}

export async function fetchDocuments(token: string): Promise<DocumentItem[]> {
  return request<DocumentItem[]>("/api/admin/documents", { token });
}

export async function createDocument(
  token: string,
  payload: { title: string; content: string; tags: string[]; source?: string }
): Promise<DocumentItem> {
  return request<DocumentItem>("/api/admin/documents", {
    method: "POST",
    token,
    body: payload
  });
}

export async function fetchStats(token: string): Promise<StatsResponse> {
  return request<StatsResponse>("/api/admin/stats", { token });
}
