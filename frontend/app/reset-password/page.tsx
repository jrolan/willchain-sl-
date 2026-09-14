"use client";

import Link from "next/link";
import { FormEvent, useEffect, useState } from "react";

import { AuthShell, Field } from "@/components/auth/auth-shell";
import { resetPassword } from "@/services/auth-service";

export default function ResetPasswordPage() {
  const [query, setQuery] = useState({ uid: "", token: "" });
  const [password, setPassword] = useState("");
  const [confirmation, setConfirmation] = useState("");
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    setQuery({ uid: params.get("uid") ?? "", token: params.get("token") ?? "" });
  }, []);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setMessage("");
    setBusy(true);
    try {
      const response = await resetPassword({
        uid: query.uid,
        token: query.token,
        new_password: password,
        new_password_confirmation: confirmation,
      });
      setMessage(response.message || "Password reset successfully.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "This reset link is invalid or expired.");
    } finally {
      setBusy(false);
    }
  }

  return <AuthShell eyebrow="Account recovery" title="Choose a new password." description="Create a new password for your protected WillChain identity.">
    <div className="recovery-card">
      {error && <div role="alert" className="mb-4 rounded-lg bg-[#fff3ed] p-3 text-xs text-[#8c422c]">{error}</div>}
      {message && <div className="recovery-success" role="status">{message}</div>}
      <form className="recovery-form" onSubmit={submit}>
        <Field label="New password" required type="password" autoComplete="new-password" value={password} onChange={(event) => setPassword(event.target.value)} />
        <Field label="Confirm password" required type="password" autoComplete="new-password" value={confirmation} onChange={(event) => setConfirmation(event.target.value)} />
        <button className="recovery-submit" type="submit" disabled={busy}>{busy ? "Updating..." : "Update password"}</button>
      </form>
      <Link className="recovery-link" href="/login">Return to sign in</Link>
    </div>
  </AuthShell>;
}
