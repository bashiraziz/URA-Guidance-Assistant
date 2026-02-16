"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import rehypeSanitize from "rehype-sanitize";
import remarkGfm from "remark-gfm";

import { chatApi, type ApiMessage, type Citation, type Usage } from "@/services/chat-api";
import ReadAloudButton from "@/components/read-aloud-button";

type Message = {
  id: string;
  role: "user" | "assistant";
  content: string;
  citations?: Citation[];
  created_at?: string;
};

const STORAGE_KEY = "ura_conversation_id";

export default function ChatWidget() {
  const [open, setOpen] = useState(false);
  const [minimized, setMinimized] = useState(false);
  const [initialized, setInitialized] = useState(false);
  const [accessMode, setAccessMode] = useState<"guest" | "user">("guest");
  const [question, setQuestion] = useState("");
  const [conversationId, setConversationId] = useState<string>();
  const [messages, setMessages] = useState<Message[]>([]);
  const [usage, setUsage] = useState<Usage | null>(null);
  const [lang, setLang] = useState<"en" | "lg">("en");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [listening, setListening] = useState(false);
  const [micSupported, setMicSupported] = useState(false);
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const recognitionRef = useRef<any>(null);
  const apiBase = useMemo(() => process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000", []); // surfaced for support debugging

  useEffect(() => {
    if (!open) {
      setInitialized(false);
    }
  }, [open]);

  useEffect(() => {
    if (!open || initialized) {
      return;
    }
    const run = async () => {
      let mode: "guest" | "user" = "guest";
      try {
        mode = await chatApi.getAccessMode();
      } catch {
        mode = "guest";
      }
      setAccessMode(mode);

      if (mode === "guest") {
        setInitialized(true);
        return;
      }

      const savedConversationId = localStorage.getItem(STORAGE_KEY);
      if (!savedConversationId) {
        setInitialized(true);
        return;
      }
      try {
        const history = await chatApi.getConversationMessages(savedConversationId);
        const mapped = history
          .filter((m) => m.role === "user" || m.role === "assistant")
          .map((m: ApiMessage) => ({
            id: m.id,
            role: m.role as "user" | "assistant",
            content: m.content_md,
            created_at: m.created_at
          }));
        setConversationId(savedConversationId);
        setMessages(mapped);
      } catch {
        localStorage.removeItem(STORAGE_KEY);
      } finally {
        setInitialized(true);
      }
    };
    void run();
  }, [initialized, open]);

  // Detect SpeechRecognition support
  useEffect(() => {
    const SR = typeof window !== "undefined"
      ? (window as unknown as Record<string, unknown>).SpeechRecognition || (window as unknown as Record<string, unknown>).webkitSpeechRecognition
      : null;
    setMicSupported(!!SR);
  }, []);

  // Cleanup recognition on unmount
  useEffect(() => {
    return () => {
      recognitionRef.current?.abort();
    };
  }, []);

  function toggleMic() {
    if (listening && recognitionRef.current) {
      recognitionRef.current.stop();
      setListening(false);
      return;
    }
    const SR = (window as unknown as Record<string, unknown>).SpeechRecognition || (window as unknown as Record<string, unknown>).webkitSpeechRecognition;
    if (!SR) return;
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const recognition = new (SR as any)();
    recognition.lang = "en-US";
    recognition.interimResults = false;
    recognition.maxAlternatives = 1;
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    recognition.onresult = (event: any) => {
      const transcript = event.results?.[0]?.[0]?.transcript;
      if (transcript) {
        setQuestion((prev) => (prev ? prev + " " + transcript : transcript));
      }
    };
    recognition.onend = () => setListening(false);
    recognition.onerror = () => setListening(false);
    recognitionRef.current = recognition;
    recognition.start();
    setListening(true);
  }

  async function ask() {
    const q = question.trim();
    if (!q || busy) {
      return;
    }
    setQuestion("");
    setError("");
    setBusy(true);
    const localUserMessage: Message = {
      id: typeof crypto !== "undefined" && "randomUUID" in crypto ? crypto.randomUUID() : `${Date.now()}-user`,
      role: "user",
      content: q,
      created_at: new Date().toISOString()
    };
    setMessages((prev) => [...prev, localUserMessage]);
    try {
      const data = await chatApi.sendMessage({
        conversation_id: accessMode === "user" ? conversationId : undefined,
        language_code: lang,
        question: q
      });
      if (accessMode === "user") {
        setConversationId(data.conversation_id);
        localStorage.setItem(STORAGE_KEY, data.conversation_id);
      } else {
        setConversationId(undefined);
      }
      setUsage(data.usage);
      setMessages((prev) => [
        ...prev,
        {
          id: typeof crypto !== "undefined" && "randomUUID" in crypto ? crypto.randomUUID() : `${Date.now()}-assistant`,
          role: "assistant",
          content: data.answer_md || "No answer generated.",
          citations: data.citations || [],
          created_at: new Date().toISOString()
        }
      ]);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error");
    } finally {
      setBusy(false);
    }
  }

  function clearConversation() {
    setConversationId(undefined);
    setMessages([]);
    setUsage(null);
    setError("");
    localStorage.removeItem(STORAGE_KEY);
  }

  return (
    <div className="chat-widget-root" data-api-base={apiBase}>
      <button className="chat-fab" type="button" onClick={() => setOpen((v) => !v)}>
        Ask URA Tax
      </button>
      {open ? (
        <section className={`chat-drawer ${minimized ? "chat-drawer-minimized" : ""}`}>
          <header className="chat-header">
            <div>
              <strong>Ask URA Tax</strong>
              <p style={{ margin: "0.2rem 0 0", color: "var(--muted)", fontSize: "0.86rem" }}>
                {accessMode === "guest"
                  ? "Guest mode: lower quotas and no conversation history."
                  : "Evidence-backed answers with citations."}
              </p>
            </div>
            <div className="chat-header-actions">
              <button
                type="button"
                className="chat-lang-btn"
                onClick={() => setLang((v) => (v === "en" ? "lg" : "en"))}
                title={lang === "en" ? "Switch to Luganda" : "Switch to English"}
              >
                <span className="chat-lang-active">{lang === "en" ? "EN" : "LG"}</span>
                <span className="chat-lang-separator">/</span>
                <span className="chat-lang-inactive">{lang === "en" ? "LG" : "EN"}</span>
              </button>
              {accessMode === "user" && (
                <a href="/settings" className="chat-icon-btn" title="LLM Provider Settings" style={{ textDecoration: "none" }}>
                  Settings
                </a>
              )}
              <button type="button" className="chat-icon-btn" onClick={() => setMinimized((v) => !v)} title="Minimize">
                {minimized ? "Expand" : "Minimize"}
              </button>
              <button type="button" className="chat-icon-btn" onClick={clearConversation} title="New conversation">
                New
              </button>
            </div>
          </header>
          {!minimized && (
            <div className="chat-messages">
              {messages.map((m, i) => (
                <article key={m.id || i} className={`chat-message ${m.role}`}>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                    <strong>{m.role === "user" ? "You" : "Assistant"}</strong>
                    {m.role === "assistant" && <ReadAloudButton text={m.content} />}
                  </div>
                  <div style={{ marginTop: 6 }}>
                    <ReactMarkdown remarkPlugins={[remarkGfm]} rehypePlugins={[rehypeSanitize]}>
                      {m.content}
                    </ReactMarkdown>
                  </div>
                  {m.citations?.length ? (
                    <details style={{ marginTop: 8 }}>
                      <summary>Sources</summary>
                      {m.citations.map((c, idx) => (
                        <div key={`${c.doc_path}-${idx}`} style={{ marginTop: 6, fontSize: "0.9rem" }}>
                          <div>
                            <strong>{c.title}</strong> {c.section_ref ? `(${c.section_ref})` : ""}
                          </div>
                          <code>{c.doc_path}</code>
                          <p style={{ margin: "4px 0 0", color: "var(--muted)" }}>{c.snippet}</p>
                        </div>
                      ))}
                    </details>
                  ) : null}
                </article>
              ))}
              {busy ? (
                <div className="chat-loading">
                  <div className="chat-loading-dots">
                    <span />
                    <span />
                    <span />
                  </div>
                </div>
              ) : null}
              {error ? <p className="chat-error">{error}</p> : null}
            </div>
          )}
          {!minimized && (
            <div className={`chat-input${micSupported && lang === "en" ? " has-mic" : ""}`}>
              <textarea
                placeholder={lang === "en" ? "Ask about VAT, PAYE, filing, exemptions..." : "Buuza ku VAT, PAYE, okufayilo, ebitagobererwa..."}
                value={question}
                onChange={(e) => setQuestion(e.target.value)}
                rows={3}
                disabled={busy}
              />
              {micSupported && lang === "en" && (
                <button
                  type="button"
                  className={`chat-mic-btn${listening ? " listening" : ""}`}
                  onClick={toggleMic}
                  title={listening ? "Stop listening" : "Voice input"}
                  disabled={busy}
                >
                  🎤
                </button>
              )}
              <button type="button" onClick={ask} disabled={busy}>
                {busy ? "Sending..." : "Send"}
              </button>
            </div>
          )}
          {!minimized && usage ? (
            <footer style={{ borderTop: "1px solid var(--surface-border)", padding: "0.5rem 0.75rem" }}>
              <div className="quota">
                {accessMode === "guest" ? "Guest limits. Sign in for higher quotas. | " : ""}
                Daily requests left: {usage.daily_requests_remaining} | Minute requests left: {usage.minute_requests_remaining}
                {" | "}Output tokens left: {usage.daily_output_tokens_remaining}
              </div>
            </footer>
          ) : null}
        </section>
      ) : null}
    </div>
  );
}
