"use client";

import Link from "next/link";
import { FormEvent, useEffect, useState } from "react";

import { AuthShell, Field } from "@/components/auth/auth-shell";
import { useAuth } from "@/lib/auth-context";
import {
  acceptBeneficiaryInvitation,
  declineBeneficiaryInvitation,
  getBeneficiaryInvitationPreview,
  registerFromBeneficiaryInvitation,
} from "@/services/beneficiary-service";
import type { BeneficiaryInvitationPreview } from "@/types/beneficiaries";

export default function BeneficiaryInvitationPage() {
  const { user, signIn, signOut, initialLoading, busy } = useAuth();
  const [token, setToken] = useState("");
  const [mode, setMode] = useState<"login" | "register">("login");
  const [preview, setPreview] = useState<BeneficiaryInvitationPreview | null>(null);
  const [loadingPreview, setLoadingPreview] = useState(false);
  const [working, setWorking] = useState(false);
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");
  const [loginForm, setLoginForm] = useState({ email: "", password: "" });
  const [registrationForm, setRegistrationForm] = useState({
    email: "",
    first_name: "",
    last_name: "",
    phone_number: "",
    password: "",
    password_confirmation: "",
  });

  useEffect(() => {
    setToken(new URLSearchParams(window.location.search).get("token") ?? "");
  }, []);

  useEffect(() => {
    if (!token || initialLoading || !user) return;
    let active = true;
    setLoadingPreview(true);
    setError("");
    getBeneficiaryInvitationPreview(token)
      .then((result) => {
        if (active) setPreview(result);
      })
      .catch((previewError) => {
        if (active) setError(previewError instanceof Error ? previewError.message : "Invitation is invalid or unavailable.");
      })
      .finally(() => {
        if (active) setLoadingPreview(false);
      });
    return () => {
      active = false;
    };
  }, [token, user, initialLoading]);

  async function signInAndLoad(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setWorking(true);
    try {
      await signIn(loginForm.email, loginForm.password);
    } catch (loginError) {
      setError(loginError instanceof Error ? loginError.message : "Could not sign in or load this invitation.");
    } finally {
      setWorking(false);
    }
  }

  async function registerInvitee(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setNotice("");
    setWorking(true);
    try {
      const result = await registerFromBeneficiaryInvitation({ ...registrationForm, invitation_token: token });
      setNotice(`${result.message} Reopen this invitation link after signing in to accept.`);
    } catch (registrationError) {
      setError(registrationError instanceof Error ? registrationError.message : "Could not create the account.");
    } finally {
      setWorking(false);
    }
  }

  async function respond(accept: boolean) {
    setError("");
    setNotice("");
    setWorking(true);
    try {
      const result = accept
        ? await acceptBeneficiaryInvitation(token)
        : await declineBeneficiaryInvitation(token);
      setNotice(accept
        ? "Invitation accepted. Your beneficiary relationship is active; this does not grant access to the will."
        : result.message);
      setPreview(null);
    } catch (responseError) {
      setError(responseError instanceof Error ? responseError.message : "Could not process this invitation.");
    } finally {
      setWorking(false);
    }
  }

  if (!token) {
    return <main className="shell"><div className="panel"><h2>Invitation unavailable</h2><p role="alert">The invitation token is missing.</p><Link href="/login">Sign in</Link></div></main>;
  }

  return (
    <AuthShell
      eyebrow="Beneficiary invitation"
      title="Review your invitation."
      description="Your account is independent. Accepting this invitation creates a beneficiary relationship and does not provide access to the will."
    >
      {error && <div role="alert" className="mb-5 rounded-lg border border-[#d9b8a9] bg-[#fff3ed] px-4 py-3 text-sm leading-6 text-[#8c422c]">{error}</div>}
      {notice && <div role="status" className="mb-5 rounded-lg border border-[#b8d9ca] bg-[#effaf4] px-4 py-3 text-sm leading-6 text-[#176b5b]">{notice}</div>}
      {(initialLoading || loadingPreview) && <p role="status">Checking your account and invitation...</p>}
      {preview && user && (
        <div className="grid gap-5">
          <div className="rounded-xl border border-[#dce4df] bg-white p-4 text-sm leading-6 text-[#60776e]">
            Invitation for <strong>{preview.recipient_email}</strong>. Expires {new Date(preview.expires_at).toLocaleString()}.
          </div>
          <div className="flex flex-wrap gap-3">
            <button className="rounded-lg bg-[#176b5b] px-5 py-3 text-sm font-bold text-white disabled:opacity-60" disabled={working} onClick={() => respond(true)} type="button">{working ? "Processing..." : "Accept invitation"}</button>
            <button className="rounded-lg border border-[#cbd8d1] px-5 py-3 text-sm font-bold text-[#17372f] disabled:opacity-60" disabled={working} onClick={() => respond(false)} type="button">Decline</button>
          </div>
        </div>
      )}
      {!initialLoading && !user && !notice && (
        <div className="mb-6 flex gap-3 border-b border-[#dce4df] pb-3 text-sm">
          <button className={mode === "login" ? "font-bold text-[#176b5b]" : "text-[#60776e]"} onClick={() => { setMode("login"); setError(""); }} type="button">I have an account</button>
          <button className={mode === "register" ? "font-bold text-[#176b5b]" : "text-[#60776e]"} onClick={() => { setMode("register"); setError(""); }} type="button">Create an account</button>
        </div>
      )}
      {!initialLoading && !user && !notice && mode === "login" && (
        <form className="grid gap-5" onSubmit={signInAndLoad}>
          <Field label="Email address" required type="email" autoComplete="email" value={loginForm.email} onChange={(event) => setLoginForm({ ...loginForm, email: event.target.value })} />
          <Field label="Password" required type="password" autoComplete="current-password" value={loginForm.password} onChange={(event) => setLoginForm({ ...loginForm, password: event.target.value })} />
          <button className="rounded-lg bg-[#176b5b] px-5 py-3 text-sm font-bold text-white disabled:opacity-60" disabled={working || busy}>{working || busy ? "Signing in..." : "Sign in to review"}</button>
        </form>
      )}
      {!initialLoading && !user && !notice && mode === "register" && (
        <form className="grid gap-5" onSubmit={registerInvitee}>
          <Field label="Email address" required type="email" autoComplete="email" value={registrationForm.email} onChange={(event) => setRegistrationForm({ ...registrationForm, email: event.target.value })} />
          <div className="grid gap-5 sm:grid-cols-2">
            <Field label="First name" required autoComplete="given-name" value={registrationForm.first_name} onChange={(event) => setRegistrationForm({ ...registrationForm, first_name: event.target.value })} />
            <Field label="Last name" required autoComplete="family-name" value={registrationForm.last_name} onChange={(event) => setRegistrationForm({ ...registrationForm, last_name: event.target.value })} />
          </div>
          <Field label="Phone number" type="tel" autoComplete="tel" value={registrationForm.phone_number} onChange={(event) => setRegistrationForm({ ...registrationForm, phone_number: event.target.value })} />
          <Field label="Password" required type="password" autoComplete="new-password" value={registrationForm.password} onChange={(event) => setRegistrationForm({ ...registrationForm, password: event.target.value })} />
          <Field label="Confirm password" required type="password" autoComplete="new-password" value={registrationForm.password_confirmation} onChange={(event) => setRegistrationForm({ ...registrationForm, password_confirmation: event.target.value })} />
          <p className="m-0 text-xs leading-5 text-[#60776e]">Your account will remain pending until you verify your email. Registration does not accept the invitation or grant will access.</p>
          <button className="rounded-lg bg-[#176b5b] px-5 py-3 text-sm font-bold text-white disabled:opacity-60" disabled={working || busy}>{working || busy ? "Creating account..." : "Create and verify account"}</button>
        </form>
      )}
      {user && !preview && !loadingPreview && !notice && (
        <div className="grid gap-4">
          <p className="text-sm leading-6 text-[#60776e]">Sign in with the email address the invitation was sent to. If this account is not the intended recipient, switch accounts.</p>
          <button className="w-fit rounded-lg border border-[#cbd8d1] px-5 py-3 text-sm font-bold text-[#17372f]" onClick={() => signOut()} type="button">Sign out and switch accounts</button>
        </div>
      )}
      {notice && <p className="mt-5 text-sm leading-6 text-[#60776e]">Need to sign in? <Link className="font-bold text-[#176b5b] hover:underline" href="/login">Go to sign in</Link>, then reopen this invitation link.</p>}
    </AuthShell>
  );
}
