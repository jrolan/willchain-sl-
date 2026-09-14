"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useEffect, useState } from "react";
import {
  CheckCircle2,
  CircleUserRound,
  Copy,
  Gavel,
  LogOut,
  Mail,
  Plus,
  Scale,
  ShieldCheck,
  UserCheck,
  UserPlus,
  Users,
} from "lucide-react";

import { useAuth } from "@/lib/auth-context";
import { getInvitations, getProfile, sendInvitation } from "@/services/auth-service";
import type { Invitation, InvitationRole, User } from "@/types/auth";
import { ThemeToggle } from "@/components/common/theme-provider";

const API_ORIGIN = (process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/api/v1").replace(/\/api\/v1\/?$/, "");

function avatarUrl(url: string | null | undefined) {
  if (!url) return "";
  return url.startsWith("http") ? url : `${API_ORIGIN}${url}`;
}

export default function DashboardPage() {
  const router = useRouter();
  const { user, signOut, busy, initialLoading } = useAuth();
  const [profileUser, setProfileUser] = useState<User | null>(user);

  // Invitations state for Testators
  const [invitations, setInvitations] = useState<Invitation[]>([]);
  const [loadingInvitations, setLoadingInvitations] = useState(false);
  const [showInviteModal, setShowInviteModal] = useState(false);
  const [inviteForm, setInviteForm] = useState<{
    email: string;
    first_name: string;
    last_name: string;
    role: InvitationRole;
    message: string;
  }>({
    email: "",
    first_name: "",
    last_name: "",
    role: "WITNESS",
    message: "",
  });
  const [inviteError, setInviteError] = useState("");
  const [inviteSuccess, setInviteSuccess] = useState("");
  const [inviteBusy, setInviteBusy] = useState(false);
  const [copiedToken, setCopiedToken] = useState("");

  // Route protection
  useEffect(() => {
    if (!initialLoading && !user) {
      router.push("/login");
    }
  }, [initialLoading, user, router]);

  useEffect(() => {
    setProfileUser(user);
    getProfile().then(({ data }) => {
      setProfileUser(data);
      if (data.role === "OWNER") {
        loadInvitations();
      }
    }).catch(() => setProfileUser(user));
  }, [user]);

  async function loadInvitations() {
    setLoadingInvitations(true);
    try {
      const response = await getInvitations();
      setInvitations(response.data);
    } catch {
      // Ignored if not authorized
    } finally {
      setLoadingInvitations(false);
    }
  }

  async function handleSendInvite(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setInviteError("");
    setInviteSuccess("");
    setInviteBusy(true);
    try {
      const response = await sendInvitation(inviteForm);
      setInviteSuccess(response.message || "Invitation sent successfully.");
      setInviteForm({ email: "", first_name: "", last_name: "", role: "WITNESS", message: "" });
      await loadInvitations();
      setTimeout(() => setShowInviteModal(false), 2000);
    } catch (err) {
      setInviteError(err instanceof Error ? err.message : "Failed to send invitation.");
    } finally {
      setInviteBusy(false);
    }
  }

  function copyInviteLink(token?: string) {
    if (!token) return;
    const url = `${window.location.origin}/accept-invitation?token=${token}`;
    navigator.clipboard.writeText(url);
    setCopiedToken(token);
    setTimeout(() => setCopiedToken(""), 2500);
  }

  async function exit() {
    await signOut();
    router.push("/login");
  }

  const roleTitleMap: Record<string, string> = {
    OWNER: "Will Owner / Testator",
    WITNESS: "Designated Witness",
    BENEFICIARY: "Designated Beneficiary",
    LAWYER_VERIFIER: "Authorized Legal Verifier",
    ADMINISTRATOR: "System Administrator",
  };

  return (
    <main className="dashboard-page min-h-screen">
      <header className="dashboard-header">
        <div className="mx-auto flex max-w-7xl items-center justify-between px-5 py-5 sm:px-10 lg:px-16">
          <div className="dashboard-brand">
            <span className="dashboard-brand-avatar">
              {avatarUrl(profileUser?.avatar) ? (
                <img src={avatarUrl(profileUser?.avatar)} alt="Profile" />
              ) : (
                <ShieldCheck size={17} />
              )}
            </span>
            WILLCHAIN SL
          </div>
          <div className="dashboard-header-actions">
            <ThemeToggle />
            <Link className="dashboard-profile-link" href="/profile">
              <CircleUserRound size={17} /> Profile
            </Link>
            <button
              className="dashboard-signout inline-flex items-center gap-2 rounded-lg px-3 py-2 text-sm font-bold"
              disabled={busy}
              onClick={exit}
            >
              <LogOut size={16} />
              {busy ? "Signing out..." : "Sign out"}
            </button>
          </div>
        </div>
      </header>

      <section className="mx-auto max-w-7xl px-5 py-12 sm:px-10 lg:px-16">
        <div className="flex flex-wrap items-end justify-between gap-5">
          <div>
            <p className="text-xs font-bold uppercase tracking-wider text-[#aa7d34]">
              {roleTitleMap[profileUser?.role ?? ""] ?? "Protected Workspace"}
            </p>
            <h1 className="mt-3 text-4xl font-semibold sm:text-5xl">
              {profileUser ? `Welcome, ${profileUser.first_name}.` : "Loading workspace..."}
            </h1>
            <p className="mt-3 text-[#60776e]">
              Authenticated as <span className="font-semibold text-[#17372f]">{profileUser?.email}</span> with active court-grade credentials.
            </p>
          </div>
        </div>

        <div className="mt-10 grid gap-4 md:grid-cols-3">
          <div className="rounded-xl border border-[#dce4df] bg-[#fffdf8] p-6 shadow-sm">
            <p className="text-xs font-bold uppercase text-[#809189]">Role</p>
            <p className="mt-3 text-xl font-semibold text-[#17372f]">
              {profileUser?.role ? roleTitleMap[profileUser.role] : "Loading..."}
            </p>
          </div>
          <div className="rounded-xl border border-[#dce4df] bg-[#fffdf8] p-6 shadow-sm">
            <p className="text-xs font-bold uppercase text-[#809189]">Account status</p>
            <p className="mt-3 text-xl font-semibold text-[#176b5b]">
              {profileUser?.account_status ?? "Unknown"}
            </p>
          </div>
          <div className="rounded-xl border border-[#dce4df] bg-[#fffdf8] p-6 shadow-sm">
            <p className="text-xs font-bold uppercase text-[#809189]">Identity Verification</p>
            <p className="mt-3 text-base font-medium text-[#17372f]">
              {profileUser?.email_verified ? "Email & Identity Verified" : "Pending Verification"}
            </p>
          </div>
        </div>

        {/* --- ROLE-SPECIFIC WORKSPACE CONTENT --- */}
        {profileUser?.role === "OWNER" && (
          <div className="mt-12">
            <div className="flex items-center justify-between">
              <div>
                <h2 className="text-2xl font-semibold text-[#17372f]">Estate Collaborators & Invitations</h2>
                <p className="mt-1 text-sm text-[#60776e]">
                  Witnesses, Beneficiaries, and Legal Verifiers are invited directly by you to collaborate on your digital estate.
                </p>
              </div>
              <button
                type="button"
                onClick={() => { setShowInviteModal(true); setInviteError(""); setInviteSuccess(""); }}
                className="inline-flex items-center gap-2 rounded-lg bg-[#176b5b] px-4 py-2.5 text-sm font-semibold text-white shadow-sm hover:bg-[#0f5548]"
              >
                <UserPlus size={16} /> Invite Collaborator
              </button>
            </div>

            {/* Invitations list */}
            <div className="mt-6 overflow-hidden rounded-xl border border-[#dce4df] bg-white shadow-sm">
              {loadingInvitations ? (
                <div className="p-8 text-center text-sm text-[#809189]">Loading invitations...</div>
              ) : invitations.length === 0 ? (
                <div className="p-8 text-center">
                  <UserPlus className="mx-auto text-[#809189]" size={36} />
                  <p className="mt-3 font-semibold text-[#17372f]">No collaborators invited yet</p>
                  <p className="mt-1 text-xs text-[#809189]">
                    Invite your Witnesses, Beneficiaries, or Lawyer so their secure identities are ready for your will.
                  </p>
                </div>
              ) : (
                <div className="divide-y divide-[#edf1ee]">
                  {invitations.map((inv) => (
                    <div key={inv.id} className="flex flex-wrap items-center justify-between p-5 hover:bg-[#fafaf8]">
                      <div>
                        <div className="flex items-center gap-3">
                          <span className="font-semibold text-[#17372f]">
                            {inv.first_name || inv.last_name ? `${inv.first_name} ${inv.last_name}` : inv.email}
                          </span>
                          <span className="rounded-full bg-[#f3dfae]/40 px-2.5 py-0.5 text-xs font-bold text-[#8c5e15]">
                            {roleTitleMap[inv.role] ?? inv.role}
                          </span>
                          <span className={`rounded-full px-2.5 py-0.5 text-xs font-bold ${inv.status === "ACCEPTED" ? "bg-[#d8f0e5] text-[#0f5548]" : "bg-[#f3f4f6] text-[#4b5563]"}`}>
                            {inv.status}
                          </span>
                        </div>
                        <p className="mt-1 text-xs text-[#809189]">
                          <Mail size={12} className="inline mr-1" /> {inv.email} · Invited on {new Date(inv.created_at).toLocaleDateString()}
                        </p>
                      </div>
                      {inv.status === "PENDING" && inv.token && (
                        <button
                          type="button"
                          onClick={() => copyInviteLink(inv.token)}
                          className="mt-2 inline-flex items-center gap-1.5 rounded-md border border-[#dce4df] px-3 py-1.5 text-xs font-semibold text-[#176b5b] hover:bg-[#f5f7f6] sm:mt-0"
                        >
                          <Copy size={13} /> {copiedToken === inv.token ? "Copied!" : "Copy acceptance link"}
                        </button>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        )}

        {profileUser?.role === "LAWYER_VERIFIER" && (
          <div className="mt-10 rounded-xl border border-[#dce4df] bg-white p-8 shadow-sm">
            <div className="flex items-center gap-3">
              <Gavel className="text-[#176b5b]" size={28} />
              <div>
                <h2 className="text-xl font-semibold text-[#17372f]">Legal Verifier Portal</h2>
                <p className="text-sm text-[#60776e]">
                  Authorized by Testator invitations. Verification cases and certificate reviews will appear here once assigned in Module 5.
                </p>
              </div>
            </div>
          </div>
        )}

        {profileUser?.role === "WITNESS" && (
          <div className="mt-10 rounded-xl border border-[#dce4df] bg-white p-8 shadow-sm">
            <div className="flex items-center gap-3">
              <UserCheck className="text-[#176b5b]" size={28} />
              <div>
                <h2 className="text-xl font-semibold text-[#17372f]">Witness Registry Workspace</h2>
                <p className="text-sm text-[#60776e]">
                  Your witness identity is securely registered. Will attestation requests will be dispatched to this account in Module 3.
                </p>
              </div>
            </div>
          </div>
        )}

        {profileUser?.role === "BENEFICIARY" && (
          <div className="mt-10 rounded-xl border border-[#dce4df] bg-white p-8 shadow-sm">
            <div className="flex items-center gap-3">
              <Users className="text-[#176b5b]" size={28} />
              <div>
                <h2 className="text-xl font-semibold text-[#17372f]">Beneficiary Registry Workspace</h2>
                <p className="text-sm text-[#60776e]">
                  Your identity is recorded for controlled future allocation release following legal probate verification in Module 6.
                </p>
              </div>
            </div>
          </div>
        )}

        <div className="mt-12 rounded-xl border border-[#c7a86b]/40 bg-[#fffaf0] p-5 text-sm leading-6 text-[#6d572c]">
          WillChain protects private will information through identity, relationship, explicit permission, and workflow state. No private will contents are exposed without verified authorization.
        </div>
      </section>

      {/* Invite Collaborator Dialog */}
      {showInviteModal && (
        <div className="fixed inset-0 z-50 grid place-items-center bg-black/40 p-4" role="dialog" aria-modal="true">
          <div className="w-full max-w-lg rounded-2xl bg-white p-6 shadow-xl sm:p-8">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-xl font-semibold text-[#17372f]">Invite an Estate Collaborator</h3>
                <p className="mt-1 text-xs text-[#60776e]">Send an invitation to a Witness, Beneficiary, or Lawyer.</p>
              </div>
              <button
                type="button"
                onClick={() => setShowInviteModal(false)}
                className="rounded-lg p-1 text-[#809189] hover:bg-gray-100"
              >
                ✕
              </button>
            </div>

            {inviteError && <div className="mt-4 rounded-lg bg-[#fff3ed] p-3 text-xs text-[#8c422c]">{inviteError}</div>}
            {inviteSuccess && <div className="mt-4 rounded-lg bg-[#d8f0e5] p-3 text-xs text-[#0f5548]" role="status">{inviteSuccess}</div>}

            <form className="mt-6 space-y-4" onSubmit={handleSendInvite}>
              <div>
                <label className="block text-xs font-semibold text-[#17372f]">Collaborator Role</label>
                <select
                  value={inviteForm.role}
                  onChange={(e) => setInviteForm({ ...inviteForm, role: e.target.value as InvitationRole })}
                  className="mt-1.5 w-full rounded-lg border border-[#dce4df] bg-white p-2.5 text-sm"
                >
                  <option value="WITNESS">Witness (To attest and sign your will)</option>
                  <option value="BENEFICIARY">Beneficiary (Named in your will)</option>
                  <option value="LAWYER_VERIFIER">Lawyer / Legal Verifier (Authorized practitioner)</option>
                </select>
              </div>

              <div>
                <label className="block text-xs font-semibold text-[#17372f]">Email Address</label>
                <input
                  type="email"
                  required
                  placeholder="collaborator@example.com"
                  value={inviteForm.email}
                  onChange={(e) => setInviteForm({ ...inviteForm, email: e.target.value })}
                  className="mt-1.5 w-full rounded-lg border border-[#dce4df] p-2.5 text-sm"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-semibold text-[#17372f]">First Name (Optional)</label>
                  <input
                    type="text"
                    value={inviteForm.first_name}
                    onChange={(e) => setInviteForm({ ...inviteForm, first_name: e.target.value })}
                    className="mt-1.5 w-full rounded-lg border border-[#dce4df] p-2.5 text-sm"
                  />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-[#17372f]">Last Name (Optional)</label>
                  <input
                    type="text"
                    value={inviteForm.last_name}
                    onChange={(e) => setInviteForm({ ...inviteForm, last_name: e.target.value })}
                    className="mt-1.5 w-full rounded-lg border border-[#dce4df] p-2.5 text-sm"
                  />
                </div>
              </div>

              <div>
                <label className="block text-xs font-semibold text-[#17372f]">Personal Message (Optional)</label>
                <textarea
                  rows={3}
                  placeholder="e.g. Please join WillChain to confirm attestation on my estate."
                  value={inviteForm.message}
                  onChange={(e) => setInviteForm({ ...inviteForm, message: e.target.value })}
                  className="mt-1.5 w-full rounded-lg border border-[#dce4df] p-2.5 text-sm"
                />
              </div>

              <div className="flex justify-end gap-3 pt-3">
                <button
                  type="button"
                  onClick={() => setShowInviteModal(false)}
                  className="rounded-lg px-4 py-2 text-sm font-semibold text-[#60776e] hover:bg-gray-100"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={inviteBusy}
                  className="rounded-lg bg-[#176b5b] px-5 py-2 text-sm font-semibold text-white hover:bg-[#0f5548] disabled:opacity-60"
                >
                  {inviteBusy ? "Sending..." : "Send Invitation"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </main>
  );
}
