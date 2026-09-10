"use client";

import Link from "next/link";
import { FormEvent, useState } from "react";

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

  return (
    <main className="shell"><div className="panel">
      <div className="brand">WillChain SL</div><h2>Reset password</h2>
      <p>{sent ? "If the account exists, reset instructions have been sent." : "Enter your email to request reset instructions."}</p>
      {!sent && <form className="form" onSubmit={submit}><label>Email<input required type="email" value={email} onChange={(event) => setEmail(event.target.value)} /></label><button type="submit">Request reset</button></form>}
      <div className="inline"><Link href="/login">Return to sign in</Link></div>
    </div></main>
  );
}
