"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useEffect, useState } from "react";
import { Gavel, ShieldCheck, UserCheck } from "lucide-react";

import { AuthShell, Field } from "@/components/auth/auth-shell";
import { useAuth } from "@/lib/auth-context";
import { acceptInvitation, getInvitationDetail } from "@/services/auth-service";
import type { InvitationDetail } from "@/types/auth";

export default function AcceptInvitationPage() {
  const router = useRouter();
  const { user, signIn, signOut, initialLoading, busy: authBusy } = useAuth();

  const [token, setToken] = useState("");
  const [loading, setLoading] = useState(true);
  const [invitation, setInvitation] = useState<InvitationDetail | null>(null);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);
  const [mode, setMode] = useState<"register" | "login">("register");

  const [form, setForm] = useState({
    email: "",
    first_name: "",
    last_name: "",
    phone_number: "",
    password: "",
    password_confirmation: "",
  });

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const t = params.get("token") ?? "";
    setToken(t);
    if (!t) {
      setError("Invitation token is missing from the URL.");
      setLoading(false);
      return;
    }

    getInvitationDetail(t)
      .then((res) => {
        setInvitation(res.data);
        setForm((prev) => ({
          ...prev,
          first_name: res.data.first_name || "",
          last_name: res.data.last_name || "",
        }));
      })
      .catch((err) => {
        setError(err instanceof Error ? err.message : "Failed to load invitation.");
      })
      .finally(() => {
        setLoading(false);
      });
  }, []);

  async function register(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setNotice("");
    setBusy(true);
    try {
      const response = await acceptInvitation({
        token,
        email: form.email,
        first_name: form.first_name,
        last_name: form.last_name,
        phone_number: form.phone_number,
        password: form.password,
        password_confirmation: form.password_confirmation,
      });
      setNotice(response.message);
    } catch (submitErr) {
      setError(submitErr instanceof Error ? submitErr.message : "Failed to complete registration.");
    } finally {
      setBusy(false);
    }
  }

  async function signInToAccept(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setBusy(true);
    try {
      await signIn(form.email, form.password);
      setNotice("Signed in. Review and accept the invitation below.");
    } catch (submitErr) {
      setError(submitErr instanceof Error ? submitErr.message : "Could not sign in.");
    } finally {
      setBusy(false);
    }
  }

  async function acceptForSignedInUser() {
    setError("");
    setNotice("");
    setBusy(true);
    try {
      const response = await acceptInvitation({ token });
      setNotice(response.message);
      router.push("/dashboard");
    } catch (submitErr) {
      setError(submitErr instanceof Error ? submitErr.message : "Could not accept the invitation.");
    } finally {
      setBusy(false);
    }
  }

  function getRoleIcon(role?: string) {
    switch (role) {
      case "LAWYER_VERIFIER":
        return <Gavel size={22} className="text-[#176b5b]" />;
      case "WITNESS":
        return <UserCheck size={22} className="text-[#176b5b]" />;
      default:
        return <ShieldCheck size={22} className="text-[#176b5b]" />;
    }
  }

  if (loading) {
    return (
      <main className="shell">
        <div className="panel text-center">
          <div className="brand">WILLCHAIN SL</div>
          <h2>Verifying invitation...</h2>
          <p className="text-[#809189]">Checking estate invitation credentials...</p>
        </div>
      </main>
    );
  }

  if (error && !invitation) {
    return (
      <main className="shell">
        <div className="panel">
          <div className="brand">WILLCHAIN SL</div>
          <h2>Invitation Notice</h2>
          <div role="alert" className="notice mb-4">
            {error}
          </div>
          <p className="text-sm text-[#809189]">
            This invitation link may have expired or was already accepted. Contact the Will Owner who sent the invite.
          </p>
          <div className="inline mt-6">
            <Link href="/login">Return to Sign In</Link>
          </div>
        </div>
      </main>
    );
  }

  return (
    <AuthShell
      eyebrow="Estate Collaborator Invitation"
      title="Join WillChain SL."
      description={`You have been invited by ${invitation?.inviter_name} as an authorized ${invitation?.role_display}. Your invitation does not grant access to a will.`}
    >
      <div className="mb-6 flex items-center gap-3 rounded-xl border border-[#c7a86b]/40 bg-[#fffaf0] p-4">
        {getRoleIcon(invitation?.role)}
        <div>
          <p className="text-xs font-bold uppercase tracking-wider text-[#8c5e15]">Assigned Role</p>
          <p className="font-semibold text-[#17372f]">{invitation?.role_display}</p>
        </div>
      </div>

      {error && (
        <div role="alert" className="mb-5 rounded-lg border border-[#d9b8a9] bg-[#fff3ed] px-4 py-3 text-sm leading-6 text-[#8c422c]">
          {error}
        </div>
      )}
      {notice && <p role="status" className="mb-5 rounded-lg border border-[#b8d9ca] bg-[#effaf4] px-4 py-3 text-sm leading-6 text-[#176b5b]">{notice}</p>}
      {invitation && <p className="mb-5 text-sm text-[#60776e]">Invitation sent to {invitation.email}.</p>}

      {user ? (
        <div className="grid gap-4">
          <p className="text-sm text-[#60776e]">Signed in as {user.email}. Accepting this invitation will not change your account role or grant access to any will.</p>
          <div className="flex flex-wrap gap-3">
            <button type="button" disabled={busy || initialLoading || authBusy} onClick={acceptForSignedInUser} className="rounded-lg bg-[#176b5b] px-5 py-3 text-sm font-bold text-white disabled:opacity-60">{busy ? "Accepting..." : "Accept invitation"}</button>
            <button type="button" disabled={busy} onClick={() => signOut()} className="rounded-lg border border-[#cbd8d1] px-5 py-3 text-sm font-bold text-[#17372f]">Switch account</button>
          </div>
        </div>
      ) : notice ? (
        <p className="text-sm text-[#60776e]">After verifying your email, sign in and reopen this invitation link to accept it. <Link className="font-bold text-[#176b5b]" href="/login">Sign in</Link></p>
      ) : (
        <>
          <div className="mb-6 flex gap-4 border-b border-[#dce4df] pb-3 text-sm">
            <button type="button" onClick={() => { setMode("register"); setError(""); }} className={mode === "register" ? "font-bold text-[#176b5b]" : "text-[#60776e]"}>Create account</button>
            <button type="button" onClick={() => { setMode("login"); setError(""); }} className={mode === "login" ? "font-bold text-[#176b5b]" : "text-[#60776e]"}>I have an account</button>
          </div>
          <form className="register-form" onSubmit={mode === "register" ? register : signInToAccept}>
            <Field label="Email address" required type="email" autoComplete="email" value={form.email} onChange={(event) => setForm({ ...form, email: event.target.value })} />
            {mode === "register" && <div className="register-row">
              <Field label="First name" required value={form.first_name} onChange={(event) => setForm({ ...form, first_name: event.target.value })} />
              <Field label="Last name" required value={form.last_name} onChange={(event) => setForm({ ...form, last_name: event.target.value })} />
            </div>}
            {mode === "register" && <Field label="Phone number" type="tel" placeholder="Optional" value={form.phone_number} onChange={(event) => setForm({ ...form, phone_number: event.target.value })} />}
            <Field label="Password" required type="password" autoComplete={mode === "register" ? "new-password" : "current-password"} value={form.password} onChange={(event) => setForm({ ...form, password: event.target.value })} />
            {mode === "register" && <Field label="Confirm password" required type="password" autoComplete="new-password" value={form.password_confirmation} onChange={(event) => setForm({ ...form, password_confirmation: event.target.value })} />}
            {mode === "register" && <p className="m-0 text-xs leading-5 text-[#809189]">Your account remains pending until you verify your email. Registration does not accept this invitation.</p>}
            <button className="inline-flex h-12 w-fit items-center justify-center rounded-lg bg-[#176b5b] px-5 text-sm font-bold text-white disabled:opacity-60" disabled={busy || initialLoading || authBusy} type="submit">{busy || authBusy ? "Please wait..." : mode === "register" ? "Create account and verify email" : "Sign in"}</button>
          </form>
        </>
      )}
    </AuthShell>
  );
}
