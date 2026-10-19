"use client";

import Link from "next/link";
import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";

import { useAuth } from "@/lib/auth-context";
import { AuthShell, Field } from "@/components/auth/auth-shell";

export default function LoginPage() {
  const router = useRouter();
  const { signIn, busy } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    try {
      await signIn(email, password);
      router.push("/dashboard");
    } catch (submissionError) {
      setError(submissionError instanceof Error ? submissionError.message : "Sign in failed.");
    }
  }

  return (
    <AuthShell eyebrow="Secure sign in" title="Welcome back." description="Sign in to continue to your protected WillChain workspace. Every request is checked against your identity and permissions.">
      {error && <div role="alert" className="mb-5 rounded-lg border border-[#d9b8a9] bg-[#fff3ed] px-4 py-3 text-sm leading-6 text-[#8c422c]">{error}</div>}
      <form className="grid gap-5" onSubmit={submit}>
        <Field label="Email address" required type="email" autoComplete="email" placeholder="name@example.com" value={email} onChange={(event) => setEmail(event.target.value)} />
        <div className="grid gap-2"><div className="flex items-center justify-between"><label className="text-sm font-semibold" htmlFor="login-password">Password</label><Link className="text-xs font-semibold text-[#176b5b] hover:underline" href="/forgot-password">Forgot password?</Link></div><input id="login-password" required type="password" autoComplete="current-password" placeholder="Enter your password" value={password} onChange={(event) => setPassword(event.target.value)} className="theme-field-input rounded-lg border border-[#d7e0ec] bg-white px-3 text-sm text-[#22324a] outline-none focus:border-[#3875f6] focus:ring-4 focus:ring-[#3875f6]/10" /></div>
        <button className="inline-flex h-12 w-full items-center justify-center gap-2 rounded-lg bg-[#176b5b] px-6 text-sm font-bold text-white shadow-[0_8px_20px_rgba(23,107,91,0.18)] transition hover:bg-[#0f5548] focus:outline-none focus:ring-4 focus:ring-[#176b5b]/20 disabled:cursor-wait disabled:opacity-60" disabled={busy} type="submit">{busy ? "Signing in..." : "Sign in to Workspace"}<span aria-hidden="true">→</span></button>
      </form>
      <div className="mt-8 border-t border-[#dce4df] pt-6 text-sm text-[#60776e]">Need an account? <Link className="font-bold text-[#176b5b] hover:underline" href="/register">Create an owner account</Link></div>
    </AuthShell>
  );
}
