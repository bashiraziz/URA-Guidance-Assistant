"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { chatApi, type ProviderInfo } from "@/services/chat-api";

const PROVIDERS = [
  { value: "gemini", label: "Gemini" },
  { value: "anthropic", label: "Anthropic" },
  { value: "openai", label: "OpenAI" },
] as const;

export default function SettingsPage() {
  const [accessMode, setAccessMode] = useState<"guest" | "user" | null>(null);
  const [providers, setProviders] = useState<ProviderInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  // Form state
  const [selectedProvider, setSelectedProvider] = useState("gemini");
  const [apiKey, setApiKey] = useState("");
  const [modelName, setModelName] = useState("");
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState<string | null>(null);

  useEffect(() => {
    const init = async () => {
      try {
        const mode = await chatApi.getAccessMode();
        setAccessMode(mode);
        if (mode === "user") {
          const list = await chatApi.getProviders();
          setProviders(list);
        }
      } catch {
        setError("Failed to load settings.");
      } finally {
        setLoading(false);
      }
    };
    void init();
  }, []);

  async function handleSave() {
    if (!apiKey.trim()) {
      setError("API key is required.");
      return;
    }
    setSaving(true);
    setError("");
    setSuccess("");
    try {
      await chatApi.saveProvider(selectedProvider, apiKey.trim(), modelName.trim() || undefined);
      setApiKey("");
      setModelName("");
      const list = await chatApi.getProviders();
      setProviders(list);
      setSuccess(`${selectedProvider} key saved.`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save.");
    } finally {
      setSaving(false);
    }
  }

  async function handleTest(name: string) {
    setTesting(name);
    setError("");
    setSuccess("");
    try {
      const result = await chatApi.testProvider(name);
      if (result.ok) {
        setSuccess(result.detail);
      } else {
        setError(result.detail);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Test failed.");
    } finally {
      setTesting(null);
    }
  }

  async function handleDelete(name: string) {
    setError("");
    setSuccess("");
    try {
      await chatApi.deleteProvider(name);
      const list = await chatApi.getProviders();
      setProviders(list);
      setSuccess(`${name} key removed.`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to delete.");
    }
  }

  if (loading) {
    return (
      <main className="settings-shell">
        <p>Loading...</p>
      </main>
    );
  }

  if (accessMode !== "user") {
    return (
      <main className="settings-shell">
        <h1>Settings</h1>
        <p>You must be signed in to configure LLM providers.</p>
        <Link href="/signin">Sign in</Link>
      </main>
    );
  }

  return (
    <main className="settings-shell">
      <div className="settings-header">
        <Link href="/" className="settings-back">&larr; Back</Link>
        <h1>LLM Provider Settings</h1>
        <p className="settings-muted">
          Bring your own API key for Gemini, Anthropic, or OpenAI.
          Using your own key unlocks 5x higher quotas (125 daily requests).
        </p>
      </div>

      {error && <div className="settings-error">{error}</div>}
      {success && <div className="settings-success">{success}</div>}

      {/* Existing providers */}
      {providers.length > 0 && (
        <section className="settings-section">
          <h2>Active Providers</h2>
          <div className="settings-provider-list">
            {providers.map((p) => (
              <div key={p.provider} className="settings-provider-card">
                <div className="settings-provider-info">
                  <strong>{p.provider}</strong>
                  <code>{p.masked_key}</code>
                  {p.model_name && <span className="settings-model">{p.model_name}</span>}
                </div>
                <div className="settings-provider-actions">
                  <button
                    type="button"
                    onClick={() => handleTest(p.provider)}
                    disabled={testing === p.provider}
                    className="settings-btn settings-btn-secondary"
                  >
                    {testing === p.provider ? "Testing..." : "Test"}
                  </button>
                  <button
                    type="button"
                    onClick={() => handleDelete(p.provider)}
                    className="settings-btn settings-btn-danger"
                  >
                    Delete
                  </button>
                </div>
              </div>
            ))}
          </div>
        </section>
      )}

      {/* Add/update provider form */}
      <section className="settings-section">
        <h2>{providers.length > 0 ? "Add or Update Provider" : "Add a Provider"}</h2>
        <div className="settings-form">
          <label>
            Provider
            <select value={selectedProvider} onChange={(e) => setSelectedProvider(e.target.value)}>
              {PROVIDERS.map((p) => (
                <option key={p.value} value={p.value}>{p.label}</option>
              ))}
            </select>
          </label>
          <label>
            API Key
            <input
              type="password"
              value={apiKey}
              onChange={(e) => setApiKey(e.target.value)}
              placeholder="Enter your API key"
              autoComplete="off"
            />
          </label>
          <label>
            Model Name (optional)
            <input
              type="text"
              value={modelName}
              onChange={(e) => setModelName(e.target.value)}
              placeholder={
                selectedProvider === "gemini" ? "gemini-1.5-flash" :
                selectedProvider === "anthropic" ? "claude-sonnet-4-5-20250929" :
                "gpt-4o-mini"
              }
            />
          </label>
          <button
            type="button"
            onClick={handleSave}
            disabled={saving || !apiKey.trim()}
            className="settings-btn settings-btn-primary"
          >
            {saving ? "Saving..." : "Save Key"}
          </button>
        </div>
      </section>
    </main>
  );
}
