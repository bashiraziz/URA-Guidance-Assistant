"use client";

import { FormEvent, Suspense, useState } from "react";
import type { Route } from "next";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";

function SignInForm() {
  const router = useRouter();
  const search = useSearchParams();
  const next = search.get("next") || "/docs";
  const safeNext = next.startsWith("/") && !next.startsWith("//") ? next : "/docs";
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setLoading(true);
    setError("");
    const endpoint = "/api/auth/sign-in/email";
    const payload = { email, password };
    const res = await fetch(endpoint, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(payload)
    });
    setLoading(false);
    if (!res.ok) {
      const body = await res.text();
      setError(body || "Authentication failed.");
      return;
    }
    router.push(safeNext as Route);
    router.refresh();
  }

  return (
    <div style={{ width: "100%", maxWidth: 420 }}>
      <Link href="/" style={{ color: "var(--muted)", textDecoration: "none", fontSize: "0.9rem" }}>
        &larr; Back to home
      </Link>
      <form
        onSubmit={submit}
        style={{
          marginTop: 12,
          border: "1px solid var(--surface-border)",
          borderRadius: 16,
          padding: "1rem",
          background: "var(--surface)"
        }}
      >
        <h1 style={{ marginTop: 0 }}>URA Guidance Assistant</h1>
        <p style={{ color: "var(--muted)", marginTop: 0 }}>Sign in for higher quotas and conversation history.</p>
        <input
          type="email"
          placeholder="Email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          required
          style={{ width: "100%", marginBottom: 8, padding: 10 }}
        />
        <input
          type="password"
          placeholder="Password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          required
          style={{ width: "100%", marginBottom: 8, padding: 10 }}
        />
        {error ? <p className="error">{error}</p> : null}
        <button type="submit" disabled={loading} style={{ width: "100%", padding: 10 }}>
          {loading ? "Please wait..." : "Sign In"}
        </button>
        <div style={{ display: "flex", justifyContent: "space-between", marginTop: 12, fontSize: "0.85rem" }}>
          <Link href={`/forgot-password`} style={{ color: "var(--brand)" }}>
            Forgot password?
          </Link>
          <Link href={`/signup?next=${encodeURIComponent(safeNext)}`} style={{ color: "var(--brand)" }}>
            Create an account
          </Link>
        </div>
      </form>
    </div>
  );
}

export default function SignInPage() {
  return (
    <main style={{ minHeight: "100vh", display: "grid", placeItems: "center", padding: "1rem" }}>
      <Suspense>
        <SignInForm />
      </Suspense>
    </main>
  );
}
