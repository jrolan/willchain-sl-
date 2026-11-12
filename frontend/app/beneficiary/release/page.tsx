"use client";

import Link from "next/link";
import { FormEvent, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { CheckCircle2, LockKeyhole, ShieldCheck } from "lucide-react";

import { AuthShell, Field } from "@/components/auth/auth-shell";
import { useAuth } from "@/lib/auth-context";
import { claimBeneficiaryRelease, registerBeneficiaryRelease, validateBeneficiaryReleaseToken, verifyBeneficiaryReleaseIdentity } from "@/services/beneficiary-service";
import { ApiRequestError } from "@/services/auth-service";

const TOKEN_STORAGE_KEY = "willchain_release_claim_token";

export default function BeneficiaryReleasePage() {
  const router = useRouter();
  const { user, refreshUser } = useAuth();
  const [token, setToken] = useState("");
  const [maskedEmail, setMaskedEmail] = useState("");
  const [validating, setValidating] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [showRegistration, setShowRegistration] = useState(false);
  const [identityChallenge, setIdentityChallenge] = useState(false);
  const [identityCode, setIdentityCode] = useState("");
  const [form, setForm] = useState({ email: "", first_name: "", last_name: "", password: "", password_confirmation: "" });

  useEffect(() => {
    const fragment = new URLSearchParams(window.location.hash.slice(1));
    const incomingToken = fragment.get("token") || localStorage.getItem(TOKEN_STORAGE_KEY) || "";
    if (fragment.has("token")) window.history.replaceState(null, "", window.location.pathname);
    if (incomingToken) localStorage.setItem(TOKEN_STORAGE_KEY, incomingToken);
    setToken(incomingToken);
    if (!incomingToken) {
      setError("This release link is missing or invalid.");
      setValidating(false);
      return;
    }

    let active = true;
    validateBeneficiaryReleaseToken(incomingToken)
      .then(({ data }) => {
        if (active) setMaskedEmail(data.beneficiary_email);
      })
      .catch((requestError: unknown) => {
        if (active) {
          localStorage.removeItem(TOKEN_STORAGE_KEY);
          setError(requestError instanceof Error ? requestError.message : "This release link is invalid or expired.");
        }
      })
      .finally(() => {
        if (active) setValidating(false);
      });
    return () => {
      active = false;
    };
  }, []);

  async function handleClaim() {
    setBusy(true);
    setError("");
    try {
      await claimBeneficiaryRelease(token);
      localStorage.removeItem(TOKEN_STORAGE_KEY);
      await refreshUser();
      router.replace("/dashboard/beneficiary-allocations");
    } catch (requestError) {
      if (requestError instanceof ApiRequestError && requestError.code === "IDENTITY_VERIFICATION_REQUIRED") {
        setIdentityChallenge(true);
        setMessage(requestError.message);
        return;
      }
      setError(requestError instanceof Error ? requestError.message : "Unable to claim this allocation.");
    } finally {
      setBusy(false);
    }
  }

  async function handleIdentityVerification(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      await verifyBeneficiaryReleaseIdentity(token, identityCode);
      await claimBeneficiaryRelease(token);
      localStorage.removeItem(TOKEN_STORAGE_KEY);
      await refreshUser();
      router.replace("/dashboard/beneficiary-allocations");
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Unable to verify your identity.");
    } finally {
      setBusy(false);
    }
  }

  async function handleRegistration(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError("");
    setMessage("");
    try {
      const response = await registerBeneficiaryRelease({ ...form, token });
      setMessage(response.message);
      setShowRegistration(false);
      setForm({ email: "", first_name: "", last_name: "", password: "", password_confirmation: "" });
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Unable to register this account.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <AuthShell eyebrow="Authorized beneficiary release" title="Your allocation is ready." description="Access is limited to the allocation linked to your verified account. The release link does not reveal will details by itself.">
      {validating ? <p className="text-sm text-slate-600">Validating secure release link...</p> : null}
      {maskedEmail && <p className="mb-5 flex items-center gap-2 text-sm text-slate-600"><LockKeyhole size={15} /> Release is assigned to {maskedEmail}</p>}
      {error && <div role="alert" className="mb-5 border-l-4 border-rose-500 bg-rose-50 px-4 py-3 text-sm text-rose-800">{error}</div>}
      {message && <div role="status" className="mb-5 flex items-start gap-2 border-l-4 border-emerald-600 bg-emerald-50 px-4 py-3 text-sm text-emerald-900"><CheckCircle2 size={17} className="mt-0.5 shrink-0" />{message}</div>}

      {!validating && maskedEmail && (!message || identityChallenge) && (
        <div className="space-y-5">
          {user ? (
            <>
              {identityChallenge ? (
                <form onSubmit={handleIdentityVerification} className="space-y-4">
                  <p className="flex items-start gap-3 border-y border-slate-200 py-4 text-sm text-slate-600">
                    <ShieldCheck size={18} className="mt-0.5 shrink-0 text-emerald-700" />
                    <span>Enter the six-digit code sent to the beneficiary email address. It expires in 10 minutes.</span>
                  </p>
                  <Field label="Email verification code" required inputMode="numeric" autoComplete="one-time-code" value={identityCode} onChange={(event) => setIdentityCode(event.target.value.replace(/\D/g, "").slice(0, 6))} />
                  <button type="submit" disabled={busy || identityCode.length !== 6} className="h-12 w-full bg-emerald-800 px-5 text-sm font-bold text-white hover:bg-emerald-900 disabled:opacity-60">{busy ? "Verifying..." : "Verify code and claim allocation"}</button>
                </form>
              ) : (
                <>
                  <div className="flex items-start gap-3 border-y border-slate-200 py-4 text-sm text-slate-600">
                    <ShieldCheck size={18} className="mt-0.5 shrink-0 text-emerald-700" />
                    <p>Signed in as <strong>{user.email}</strong>. The server will confirm that this account matches the release.</p>
                  </div>
                  <button type="button" onClick={handleClaim} disabled={busy} className="h-12 w-full bg-emerald-800 px-5 text-sm font-bold text-white hover:bg-emerald-900 disabled:opacity-60">{busy ? "Claiming..." : "Claim authorized allocation"}</button>
                </>
              )}
            </>
          ) : (
            <>
              <p className="text-sm leading-6 text-slate-600">Sign in with the account registered to this beneficiary relationship. New users can create an account using the same verified email address.</p>
              <div className="grid gap-3 sm:grid-cols-2">
                <Link href="/login?next=%2Fbeneficiary%2Frelease" className="flex h-11 items-center justify-center bg-emerald-800 px-4 text-sm font-bold text-white hover:bg-emerald-900">Sign in to claim</Link>
                <button type="button" onClick={() => setShowRegistration((visible) => !visible)} className="h-11 border border-slate-300 px-4 text-sm font-semibold text-slate-700 hover:bg-slate-50">{showRegistration ? "Cancel registration" : "Create an account"}</button>
              </div>
              {showRegistration && (
                <form onSubmit={handleRegistration} className="grid gap-4 border-t border-slate-200 pt-5">
                  <Field label="Email address" required type="email" autoComplete="email" value={form.email} onChange={(event) => setForm((current) => ({ ...current, email: event.target.value }))} />
                  <div className="grid gap-4 sm:grid-cols-2">
                    <Field label="First name" required autoComplete="given-name" value={form.first_name} onChange={(event) => setForm((current) => ({ ...current, first_name: event.target.value }))} />
                    <Field label="Last name" required autoComplete="family-name" value={form.last_name} onChange={(event) => setForm((current) => ({ ...current, last_name: event.target.value }))} />
                  </div>
                  <Field label="Password" required type="password" autoComplete="new-password" value={form.password} onChange={(event) => setForm((current) => ({ ...current, password: event.target.value }))} />
                  <Field label="Confirm password" required type="password" autoComplete="new-password" value={form.password_confirmation} onChange={(event) => setForm((current) => ({ ...current, password_confirmation: event.target.value }))} />
                  <button type="submit" disabled={busy} className="h-11 bg-emerald-800 px-5 text-sm font-bold text-white hover:bg-emerald-900 disabled:opacity-60">{busy ? "Creating account..." : "Register and verify email"}</button>
                </form>
              )}
            </>
          )}
        </div>
      )}
    </AuthShell>
  );
}
