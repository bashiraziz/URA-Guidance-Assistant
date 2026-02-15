"use client";

export type Citation = {
  source_id?: string | null;
  doc_path: string;
  title: string;
  section_ref?: string | null;
  page_ref?: string | null;
  snippet: string;
};

export type Usage = {
  daily_requests_used: number;
  daily_requests_remaining: number;
  minute_requests_used: number;
  minute_requests_remaining: number;
  daily_output_tokens_used: number;
  daily_output_tokens_remaining: number;
};

export type ChatResponse = {
  conversation_id: string;
  answer_md: string;
  citations: Citation[];
  calculation?: {
    type: string;
    inputs: Record<string, unknown>;
    outputs: Record<string, unknown>;
    explanation: string;
  } | null;
  usage: Usage;
};

export type ApiMessage = {
  id: string;
  role: "user" | "assistant" | "system" | "tool";
  content_md: string;
  created_at: string;
};

export type SendMessageRequest = {
  conversation_id?: string;
  language_code?: string;
  question: string;
};

function formatSeconds(seconds: number): string {
  if (seconds >= 3600) {
    const h = Math.round(seconds / 3600);
    return `${h} hour${h === 1 ? "" : "s"}`;
  }
  if (seconds >= 60) {
    const m = Math.round(seconds / 60);
    return `${m} minute${m === 1 ? "" : "s"}`;
  }
  return `${seconds} second${seconds === 1 ? "" : "s"}`;
}

function formatApiError(body: string, status: number): string {
  try {
    const parsed = JSON.parse(body);
    const detail = parsed?.detail;
    if (detail && typeof detail === "object") {
      const msg = detail.message || "Something went wrong.";
      const retry = detail.retry_after_seconds;
      if (typeof retry === "number" && retry > 0) {
        return `${msg} Please try again in ${formatSeconds(retry)}.`;
      }
      return msg;
    }
    if (typeof detail === "string") return detail;
  } catch {
    // not JSON
  }
  if (status === 429) return "Too many requests. Please wait a moment and try again.";
  return body || `Request failed (${status})`;
}

class ChatApi {
  private apiBaseUrl: string;

  constructor() {
    this.apiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";
  }

  private async getApiAccess(): Promise<{ token: string; mode: "guest" | "user" }> {
    const response = await fetch("/api/tax/token", { method: "GET" });
    if (!response.ok) {
      throw new Error("Could not mint API token.");
    }
    const payload = (await response.json()) as { token: string; mode?: "guest" | "user" };
    return { token: payload.token, mode: payload.mode || "guest" };
  }

  async getAccessMode(): Promise<"guest" | "user"> {
    const access = await this.getApiAccess();
    return access.mode;
  }

  private async authedFetch(path: string, init?: RequestInit): Promise<Response> {
    const access = await this.getApiAccess();
    const headers = new Headers(init?.headers || {});
    headers.set("authorization", `Bearer ${access.token}`);
    if (!headers.get("content-type") && init?.body) {
      headers.set("content-type", "application/json");
    }
    return fetch(`${this.apiBaseUrl}${path}`, { ...init, headers });
  }

  async sendMessage(request: SendMessageRequest): Promise<ChatResponse> {
    const response = await this.authedFetch("/v1/chat", {
      method: "POST",
      body: JSON.stringify({
        conversation_id: request.conversation_id,
        language_code: request.language_code || "en",
        question: request.question
      })
    });
    if (!response.ok) {
      const body = await response.text();
      throw new Error(formatApiError(body, response.status));
    }
    return (await response.json()) as ChatResponse;
  }

  async getConversationMessages(conversationId: string): Promise<ApiMessage[]> {
    const response = await this.authedFetch(`/v1/conversations/${conversationId}`, { method: "GET" });
    if (!response.ok) {
      const body = await response.text();
      throw new Error(body || `Failed to load conversation (${response.status})`);
    }
    return (await response.json()) as ApiMessage[];
  }
}

export const chatApi = new ChatApi();
