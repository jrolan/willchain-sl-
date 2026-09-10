"use client";

import Link from "next/link";
import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";

import { useAuth } from "@/lib/auth-context";
import { AuthShell, Field } from "@/components/auth/auth-shell";

export default function RegisterPage() {
  const router = useRouter();
  const { signUp, busy } = useAuth();
  const [form, setForm] = useState({ email: "", first_name: "", last_name: "", phone_number: "", password: "", password_confirmation: "" });
  const [error, setError] = useState("");

  function update(field: keyof typeof form, value: string) {
    setForm((current) => ({ ...current, [field]: value }));
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    try {
      await signUp(form);
      router.push("/login?registered=1");
    } catch (submissionError) {
      setError(submissionError instanceof Error ? submissionError.message : "Registration failed.");
    }
  }

  return <AuthShell eyebrow="New owner account" title="Start with a protected identity." description="Create your WillChain owner account. Email verification is required before sign in, and privileged roles are assigned only through controlled workflows.">
    {error && <div role="alert" className="mb-5 rounded-lg border border-[#d9b8a9] bg-[#fff3ed] px-4 py-3 text-sm leading-6 text-[#8c422c]">{error}</div>}
    <form className="grid gap-5" onSubmit={submit}>
      <div className="grid gap-5 sm:grid-cols-2"><Field label="First name" required autoComplete="given-name" value={form.first_name} onChange={(event) => update("first_name", event.target.value)} /><Field label="Last name" required autoComplete="family-name" value={form.last_name} onChange={(event) => update("last_name", event.target.value)} /></div>
      <Field label="Email address" required type="email" autoComplete="email" placeholder="name@example.com" value={form.email} onChange={(event) => update("email", event.target.value)} />
      <Field label="Phone number" type="tel" autoComplete="tel" placeholder="Optional" value={form.phone_number} onChange={(event) => update("phone_number", event.target.value)} />
      <div className="grid gap-5 sm:grid-cols-2"><Field label="Password" required type="password" autoComplete="new-password" value={form.password} onChange={(event) => update("password", event.target.value)} /><Field label="Confirm password" required type="password" autoComplete="new-password" value={form.password_confirmation} onChange={(event) => update("password_confirmation", event.target.value)} /></div>
      <div className="flex items-center justify-between gap-4 pt-1"><p className="m-0 max-w-xs text-xs leading-5 text-[#809189]">By continuing, you agree to identity verification and the platform’s access controls.</p><button className="inline-flex h-12 shrink-0 items-center justify-center rounded-lg bg-[#176b5b] px-5 text-sm font-bold text-white shadow-[0_8px_20px_rgba(23,107,91,0.18)] transition hover:bg-[#0f5548] focus:outline-none focus:ring-4 focus:ring-[#176b5b]/20 disabled:cursor-wait disabled:opacity-60" disabled={busy} type="submit">{busy ? "Creating..." : "Create account"}</button></div>
    </form>
    <div className="mt-8 border-t border-[#dce4df] pt-6 text-sm text-[#60776e]">Already registered? <Link className="font-bold text-[#176b5b] hover:underline" href="/login">Sign in instead</Link></div>
  </AuthShell>;
}
