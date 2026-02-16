"use client";

import { FormEvent, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense } from "react";

function ResetPasswordForm() {
  const router = useRouter();
  const search = useSearchParams();
  const token = search.get("token") || "";
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [success, setSuccess] = useState(false);

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (password !== confirm) {
      setError("Passwords do not match.");
      return;
    }
    if (password.length < 8) {
      setError("Password must be at least 8 characters.");
      return;
    }
    setLoading(true);
    setError("");
    try {
      const res = await fetch("/api/auth/reset-password", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ newPassword: password, token }),
      });
      if (!res.ok) {
        const body = await res.text();
        setError(body || "Failed to reset password. The link may have expired.");
        setLoading(false);
        return;
      }
      setSuccess(true);
    } catch {
      setError("Network error. Please try again.");
    }
    setLoading(false);
  }

  if (!token) {
    return (
      <div style={{ border: "1px solid var(--surface-border)", borderRadius: 16, padding: "1rem", background: "var(--surface)", maxWidth: 420, width: "100%" }}>
        <h1 style={{ marginTop: 0 }}>Invalid Link</h1>
        <p style={{ color: "var(--muted)" }}>This password reset link is invalid or has expired.</p>
        <Link href="/forgot-password" style={{ color: "var(--brand)" }}>Request a new reset link</Link>
      </div>
    );
  }

  return (
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
        <h1 style={{ marginTop: 0 }}>Set New Password</h1>
        {success ? (
          <div>
            <p style={{ color: "var(--brand)" }}>Your password has been reset successfully.</p>
            <button
              type="button"
              onClick={() => router.push("/signin")}
              style={{ width: "100%", padding: 10 }}
            >
              Sign in with new password
            </button>
          </div>
        ) : (
          <form onSubmit={submit}>
            <input
              type="password"
              placeholder="New password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              minLength={8}
              style={{ width: "100%", marginBottom: 8, padding: 10 }}
            />
            <input
              type="password"
              placeholder="Confirm new password"
              value={confirm}
              onChange={(e) => setConfirm(e.target.value)}
              required
              minLength={8}
              style={{ width: "100%", marginBottom: 8, padding: 10 }}
            />
            {error ? <p className="error">{error}</p> : null}
            <button type="submit" disabled={loading} style={{ width: "100%", padding: 10 }}>
              {loading ? "Resetting..." : "Reset Password"}
            </button>
          </form>
        )}
      </div>
    </div>
  );
}

export default function ResetPasswordPage() {
  return (
    <main style={{ minHeight: "100vh", display: "grid", placeItems: "center", padding: "1rem" }}>
      <Suspense>
        <ResetPasswordForm />
      </Suspense>
    </main>
  );
}
