"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useEffect, useState } from "react";
import { CheckCircle2, Gavel, Scale, ShieldCheck, UserCheck, Users } from "lucide-react";

import { AuthShell, Field } from "@/components/auth/auth-shell";
import { useAuth } from "@/lib/auth-context";
import { acceptInvitation, getInvitationDetail } from "@/services/auth-service";
import type { InvitationDetail } from "@/types/auth";

export default function AcceptInvitationPage() {
  const router = useRouter();
  const { setUser } = useAuth();

  const [token, setToken] = useState("");
  const [loading, setLoading] = useState(true);
  const [invitation, setInvitation] = useState<InvitationDetail | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const [form, setForm] = useState({
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

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setBusy(true);
    try {
      const response = await acceptInvitation({
        token,
        first_name: form.first_name,
        last_name: form.last_name,
        phone_number: form.phone_number,
        password: form.password,
        password_confirmation: form.password_confirmation,
      });
      setUser(response.data.user);
      router.push("/dashboard");
    } catch (submitErr) {
      setError(submitErr instanceof Error ? submitErr.message : "Failed to complete registration.");
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
      case "BENEFICIARY":
        return <Users size={22} className="text-[#176b5b]" />;
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
      description={`You have been invited by ${invitation?.inviter_name} to join as an authorized ${invitation?.role_display}. Complete your secure credentials below to activate your account.`}
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

      <form className="register-form" onSubmit={submit}>
        <div className="register-row">
          <Field label="First name" required value={form.first_name} onChange={(e) => setForm({ ...form, first_name: e.target.value })} />
          <Field label="Last name" required value={form.last_name} onChange={(e) => setForm({ ...form, last_name: e.target.value })} />
        </div>
        <div className="register-row">
          <Field label="Email address" disabled value={invitation?.email ?? ""} />
          <Field label="Phone number" type="tel" placeholder="Optional" value={form.phone_number} onChange={(e) => setForm({ ...form, phone_number: e.target.value })} />
        </div>
        <div className="register-row">
          <Field label="Password" required type="password" autoComplete="new-password" value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} />
          <Field label="Confirm password" required type="password" autoComplete="new-password" value={form.password_confirmation} onChange={(e) => setForm({ ...form, password_confirmation: e.target.value })} />
        </div>
        <div className="flex items-center justify-between gap-4 pt-2">
          <p className="m-0 max-w-xs text-xs leading-5 text-[#809189]">
            Accepting this invitation registers your role and enables court-grade authentication.
          </p>
          <button
            className="inline-flex h-12 shrink-0 items-center justify-center rounded-lg bg-[#176b5b] px-5 text-sm font-bold text-white shadow-[0_8px_20px_rgba(23,107,91,0.18)] transition hover:bg-[#0f5548] disabled:opacity-60"
            disabled={busy}
            type="submit"
          >
            {busy ? "Activating..." : "Accept & Enter Workspace"}
          </button>
        </div>
      </form>

      <div className="mt-8 border-t border-[#dce4df] pt-6 text-sm text-[#60776e]">
        Already have an account? <Link className="font-bold text-[#176b5b] hover:underline" href="/login">Sign in</Link>
      </div>
    </AuthShell>
  );
}
