"use client";

import { FormEvent, useState } from "react";
import Link from "next/link";

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [submitted, setSubmitted] = useState(false);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setLoading(true);
    setError("");
    try {
      const res = await fetch("/api/auth/request-password-reset", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ email, redirectTo: "/reset-password" }),
      });
      if (!res.ok) {
        const body = await res.text();
        setError(body || "Something went wrong. Please try again.");
        setLoading(false);
        return;
      }
      setSubmitted(true);
    } catch {
      setError("Network error. Please try again.");
    }
    setLoading(false);
  }

  return (
    <main style={{ minHeight: "100vh", display: "grid", placeItems: "center", padding: "1rem" }}>
      <div style={{ width: "100%", maxWidth: 420 }}>
        <Link href="/signin" style={{ color: "var(--muted)", textDecoration: "none", fontSize: "0.9rem" }}>
          &larr; Back to sign in
        </Link>
        <div
          style={{
            marginTop: 12,
            border: "1px solid var(--surface-border)",
            borderRadius: 16,
            padding: "1rem",
            background: "var(--surface)",
          }}
        >
          <h1 style={{ marginTop: 0 }}>Reset Password</h1>
          {submitted ? (
            <div>
              <p style={{ color: "var(--brand)" }}>
                If an account with that email exists, we've sent a password reset link. Please check your inbox.
              </p>
              <Link href="/signin" style={{ color: "var(--brand)", fontSize: "0.9rem" }}>
                Return to sign in
              </Link>
            </div>
          ) : (
            <form onSubmit={submit}>
              <p style={{ color: "var(--muted)", marginTop: 0 }}>
                Enter your email address and we'll send you a link to reset your password.
              </p>
              <input
                type="email"
                placeholder="Email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                style={{ width: "100%", marginBottom: 8, padding: 10 }}
              />
              {error ? <p className="error">{error}</p> : null}
              <button type="submit" disabled={loading} style={{ width: "100%", padding: 10 }}>
                {loading ? "Sending..." : "Send Reset Link"}
              </button>
            </form>
          )}
        </div>
      </div>
    </main>
  );
}
