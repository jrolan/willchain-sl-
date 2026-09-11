"use client";

import Link from "next/link";
import { FormEvent, useState } from "react";

import { AuthShell, Field } from "@/components/auth/auth-shell";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/api/v1";

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [sent, setSent] = useState(false);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    await fetch(`${API_BASE_URL}/auth/forgot-password/`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "include",
      body: JSON.stringify({ email }),
    });
    setSent(true);
  }

  return <AuthShell eyebrow="Account recovery" title="Reset your password." description="Enter the email connected to your WillChain identity and we will send instructions if the account exists.">
    <div className="recovery-card">
      {sent ? <div className="recovery-success" role="status">If the account exists, reset instructions have been sent.</div> : <form className="recovery-form" onSubmit={submit}>
        <Field label="Email address" required type="email" autoComplete="email" placeholder="name@example.com" value={email} onChange={(event) => setEmail(event.target.value)} />
        <button className="recovery-submit" type="submit">Request reset</button>
      </form>}
      <Link className="recovery-link" href="/login">Return to sign in</Link>
    </div>
  </AuthShell>;
}
