"use client";

import Link from "next/link";
import { FormEvent, useState } from "react";

import { AuthShell, Field } from "@/components/auth/auth-shell";
import { forgotPassword } from "@/services/auth-service";

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [sent, setSent] = useState(false);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setBusy(true);
    try {
      await forgotPassword(email);
      setSent(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to request reset.");
    } finally {
      setBusy(false);
    }
  }

  return <AuthShell eyebrow="Account recovery" title="Reset your password." description="Enter the email connected to your WillChain identity and we will send instructions if the account exists.">
    <div className="recovery-card">
      {error && <div role="alert" className="mb-4 rounded-lg bg-[#fff3ed] p-3 text-xs text-[#8c422c]">{error}</div>}
      {sent ? <div className="recovery-success" role="status">If the account exists, reset instructions have been sent.</div> : <form className="recovery-form" onSubmit={submit}>
        <Field label="Email address" required type="email" autoComplete="email" placeholder="name@example.com" value={email} onChange={(event) => setEmail(event.target.value)} />
        <button className="recovery-submit" type="submit" disabled={busy}>{busy ? "Sending..." : "Request reset"}</button>
      </form>}
      <Link className="recovery-link" href="/login">Return to sign in</Link>
    </div>
  </AuthShell>;
}
