"use client";

import { FormEvent, Suspense, useState } from "react";
import type { Route } from "next";
import { useRouter, useSearchParams } from "next/navigation";

function SignUpForm() {
  const router = useRouter();
  const search = useSearchParams();
  const next = search.get("next") || "/docs";
  const safeNext = next.startsWith("/") && !next.startsWith("//") ? next : "/docs";
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [name, setName] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setLoading(true);
    setError("");
    const endpoint = "/api/auth/sign-up/email";
    const payload = {
      name: name || email.split("@")[0],
      email,
      password
    };
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
    <form
      onSubmit={submit}
      style={{
        width: "100%",
        maxWidth: 420,
        border: "1px solid var(--surface-border)",
        borderRadius: 16,
        padding: "1rem",
        background: "var(--surface)"
      }}
    >
      <h1 style={{ marginTop: 0 }}>URA Guidance Assistant</h1>
      <p style={{ color: "var(--muted)", marginTop: 0 }}>Create your account for higher quotas and saved history.</p>
      <input
        placeholder="Name"
        value={name}
        onChange={(e) => setName(e.target.value)}
        style={{ width: "100%", marginBottom: 8, padding: 10 }}
      />
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
        {loading ? "Please wait..." : "Create Account"}
      </button>
      <button
        type="button"
        onClick={() => router.push((`/signin?next=${encodeURIComponent(safeNext)}` as Route))}
        style={{ width: "100%", marginTop: 8, padding: 10, background: "transparent" }}
      >
        Already have an account? Sign in
      </button>
    </form>
  );
}

export default function SignUpPage() {
  return (
    <main style={{ minHeight: "100vh", display: "grid", placeItems: "center", padding: "1rem" }}>
      <Suspense>
        <SignUpForm />
      </Suspense>
    </main>
  );
}
