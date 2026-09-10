"use client";

import Link from "next/link";
import { FormEvent, useEffect, useState } from "react";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/api/v1";

export default function ResetPasswordPage() {
  const [query, setQuery] = useState({ uid: "", token: "" });
  const [password, setPassword] = useState("");
  const [confirmation, setConfirmation] = useState("");
  const [message, setMessage] = useState("");

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    setQuery({ uid: params.get("uid") ?? "", token: params.get("token") ?? "" });
  }, []);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const response = await fetch(`${API_BASE_URL}/auth/reset-password/`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ uid: query.uid, token: query.token, new_password: password, new_password_confirmation: confirmation }),
    });
    setMessage(response.ok ? "Password reset successfully." : "This reset link is invalid or expired.");
  }

  return <main className="shell"><div className="panel"><div className="brand">WillChain SL</div><h2>Choose a new password</h2><p>{message}</p><form className="form" onSubmit={submit}><label>New password<input required type="password" value={password} onChange={(event) => setPassword(event.target.value)} /></label><label>Confirm password<input required type="password" value={confirmation} onChange={(event) => setConfirmation(event.target.value)} /></label><button type="submit">Update password</button></form><div className="inline"><Link href="/login">Return to sign in</Link></div></div></main>;
}
