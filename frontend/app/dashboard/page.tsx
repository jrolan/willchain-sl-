"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useEffect, useState } from "react";
import {
  Activity,
  ArrowUpRight,
  Bell,
  Check,
  CheckCircle2,
  ChevronRight,
  Download,
  FilePlus2,
  Gavel,
  KeyRound,
  LockKeyhole,
  Mail,
  Plus,
  ShieldCheck,
  UserCheck,
  UserRound,
  UserPlus,
  Users,
  Zap,
  type LucideIcon,
} from "lucide-react";

import { DashboardShell } from "@/components/layout/dashboard-shell";
import { getMyBeneficiaryAllocations, getMyBeneficiaryRelationships, getWillBeneficiaries } from "@/services/beneficiary-service";
import { useAuth } from "@/lib/auth-context";
import { getMyActivity } from "@/services/dashboard-service";
import { getInvitations, getMyCollaborations, getMyWitnessAssignments, getProfile, getWills, recordWitnessAttestation, sendInvitation } from "@/services/auth-service";
import type { DashboardActivity } from "@/types/dashboard";
import type { BeneficiaryAllocationAccess, BeneficiaryRelationship, BeneficiarySelfRelationship } from "@/types/beneficiaries";
import type { Invitation, InvitationRole, User, UserRole } from "@/types/auth";
import { getCases } from "@/services/verification-service";
import type { VerificationCase } from "@/types/verification";
import type { Will } from "@/types/wills";
import type { WitnessAssignment } from "@/services/auth-service";

const API_ORIGIN = (process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/api/v1").replace(/\/api\/v1\/?$/, "");

function avatarUrl(url: string | null | undefined) {
  if (!url) return "";
  return /^https?:\/\//i.test(url) ? url : `${API_ORIGIN}${url}`;
}

function PersonAvatar({ name, image }: { name: string; image: string | null | undefined }) {
  const initials = name.split(/\s+/).filter(Boolean).slice(0, 2).map((part) => part[0]).join("").toUpperCase() || "?";
  const url = avatarUrl(image);
  return <span className="dashboard-person-avatar">{url ? <img src={url} alt="" /> : initials}</span>;
}

function DashboardMetricCard({ label, value, note, icon: Icon, tone = "green" }: {
  label: string;
  value: string;
  note: string;
  icon: LucideIcon;
  tone?: string;
}) {
  return (
    <div className="rounded-xl border border-[#dce4df] bg-[#fffdf8] p-5 shadow-sm">
      <p className="dashboard-status-label"><span className={`dashboard-status-icon ${tone}`}><Icon size={18} /></span>{label}</p>
      <p className="mt-3 text-lg font-semibold text-[#17372f]">{value}</p>
      <p className="mt-1 text-xs text-[#60776e]">{note}</p>
    </div>
  );
}

function BeneficiaryRelationshipList({ relationships, loading }: { relationships: BeneficiarySelfRelationship[]; loading: boolean }) {
  return (
    <div className="dashboard-relationship-list">
      <h3>Active relationships</h3>
      {loading ? <p>Loading your relationship records...</p> : relationships.length === 0 ? <p>No active beneficiary relationships are linked to this account.</p> : (
        <ul>
          {relationships.map((relationship) => (
            <li key={relationship.id}>
              <span><strong>{relationship.full_name || relationship.recipient_email}</strong><small>{relationship.relationship_type} · Active · Identity {relationship.identity_verification_status.toLowerCase()}</small></span>
              <CheckCircle2 size={16} aria-label="Active relationship" />
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

const roleCapabilities: Record<UserRole, Array<{ title: string; description: string; href: string }>> = {
  OWNER: [
    { title: "Manage Profile", description: "View and update your personal information", href: "/profile" },
    { title: "Create Will", description: "Draft your digital will", href: "/dashboard/wills" },
    { title: "Recent Activity", description: "Review recent account events", href: "/dashboard#activity" },
    { title: "Manage Relationships", description: "Manage people linked to your wills", href: "/dashboard/wills" },
  ],
  MEMBER: [
    { title: "Manage Profile", description: "View and update your personal information", href: "/profile" },
    { title: "Create Will", description: "Manage your own digital will", href: "/dashboard/wills" },
    { title: "Recent Activity", description: "Review recent account events", href: "/dashboard#activity" },
    { title: "Manage Relationships", description: "Manage relationships on your own wills", href: "/dashboard/wills" },
  ],
  BENEFICIARY: [
    { title: "Manage Profile", description: "View and update your personal information", href: "/profile" },
    { title: "View Relationships", description: "Review active beneficiary relationships", href: "/dashboard#role-workspace" },
    { title: "Recent Activity", description: "Review recent account events", href: "/dashboard#activity" },
    { title: "Privacy & Access", description: "Review your role's access limits", href: "/dashboard#security" },
  ],
  WITNESS: [
    { title: "Manage Profile", description: "View and update your personal information", href: "/profile" },
    { title: "Account Verification", description: "Check your email verification status", href: "/dashboard#verification" },
    { title: "Recent Activity", description: "Review recent account events", href: "/dashboard#activity" },
    { title: "Attestation Status", description: "Review the current attestation workspace", href: "/dashboard#role-workspace" },
  ],
  LAWYER_VERIFIER: [
    { title: "Manage Profile", description: "View and update your personal information", href: "/profile" },
    { title: "Verification Readiness", description: "Review legal verification workspace status", href: "/dashboard#role-workspace" },
    { title: "Recent Activity", description: "Review recent account events", href: "/dashboard#activity" },
    { title: "Privacy & Access", description: "Review your role's access limits", href: "/dashboard#security" },
  ],
  ADMINISTRATOR: [
    { title: "Manage Profile", description: "View and update your personal information", href: "/profile" },
    { title: "Integrity Operations", description: "Monitor pending and failed blockchain anchors", href: "/dashboard/integrity" },
    { title: "Account Verification", description: "Check your email verification status", href: "/dashboard#verification" },
    { title: "Recent Activity", description: "Review recent account events", href: "/dashboard#activity" },
    { title: "Security", description: "Review account security settings", href: "/dashboard#security" },
  ],
};

export default function DashboardPage() {
  const router = useRouter();
  const { user, initialLoading } = useAuth();
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
    will: number | "";
  }>({
    email: "",
    first_name: "",
    last_name: "",
    role: "WITNESS",
    message: "",
    will: "",
  });
  const [inviteError, setInviteError] = useState("");
  const [inviteSuccess, setInviteSuccess] = useState("");
  const [inviteBusy, setInviteBusy] = useState(false);
  const [wills, setWills] = useState<Will[]>([]);
  const [collaborations, setCollaborations] = useState<Invitation[]>([]);
  const [collaborationError, setCollaborationError] = useState("");
  const [witnessAssignments, setWitnessAssignments] = useState<WitnessAssignment[]>([]);
  const [loadingWitnessAssignments, setLoadingWitnessAssignments] = useState(false);
  const [witnessError, setWitnessError] = useState("");
  const [witnessBusyId, setWitnessBusyId] = useState<number | null>(null);
  const [witnessConfirmationId, setWitnessConfirmationId] = useState<number | null>(null);
  const [willBeneficiaries, setWillBeneficiaries] = useState<Array<BeneficiaryRelationship & { will_title: string }>>([]);
  const [expandedPersonKey, setExpandedPersonKey] = useState<string | null>(null);
  const [beneficiaryRelationships, setBeneficiaryRelationships] = useState<BeneficiarySelfRelationship[]>([]);
  const [beneficiaryRelationshipError, setBeneficiaryRelationshipError] = useState("");
  const [loadingRelationships, setLoadingRelationships] = useState(false);
  const [beneficiaryAllocations, setBeneficiaryAllocations] = useState<BeneficiaryAllocationAccess[]>([]);
  const [loadingBeneficiaryAllocations, setLoadingBeneficiaryAllocations] = useState(false);
  const [beneficiaryAllocationError, setBeneficiaryAllocationError] = useState("");
  const [beneficiaryCases, setBeneficiaryCases] = useState<VerificationCase[]>([]);
  const [loadingBeneficiaryCases, setLoadingBeneficiaryCases] = useState(false);
  const [beneficiaryCaseError, setBeneficiaryCaseError] = useState("");
  const [lawyerCases, setLawyerCases] = useState<VerificationCase[]>([]);
  const [loadingLawyerCases, setLoadingLawyerCases] = useState(false);
  const [lawyerCaseError, setLawyerCaseError] = useState("");
  const [activity, setActivity] = useState<DashboardActivity[]>([]);
  const [loadingActivity, setLoadingActivity] = useState(true);
  const [showAllActivity, setShowAllActivity] = useState(false);
  const [exportBusy, setExportBusy] = useState(false);
  const [exportMessage, setExportMessage] = useState("");
  const [willError, setWillError] = useState("");

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
      if (data.role === "OWNER" || data.role === "MEMBER") {
        loadWills();
      }
      if (data.role === "OWNER") loadInvitations();
      loadBeneficiaryRelationships();
      loadBeneficiaryAllocations();
      loadBeneficiaryCases();
      loadLawyerCases();
      loadCollaborations();
      loadWitnessAssignments();
      loadActivity();
    }).catch(() => setProfileUser(user));
  }, [user]);

  async function loadCollaborations() {
    setCollaborationError("");
    try {
      const response = await getMyCollaborations();
      setCollaborations(response.data);
    } catch (err) {
      setCollaborationError(err instanceof Error ? err.message : "Unable to load your accepted collaborations.");
    }
  }

  async function loadWitnessAssignments() {
    setLoadingWitnessAssignments(true);
    setWitnessError("");
    try {
      const response = await getMyWitnessAssignments();
      setWitnessAssignments(response.data);
    } catch (err) {
      setWitnessError(err instanceof Error ? err.message : "Unable to load your witness assignments.");
    } finally {
      setLoadingWitnessAssignments(false);
    }
  }

  async function handleWitnessResponse(assignment: WitnessAssignment, decision: "ATTESTED" | "DECLINED") {
    if (decision === "ATTESTED" && witnessConfirmationId !== assignment.invitation_id) return;
    setWitnessBusyId(assignment.invitation_id);
    setWitnessError("");
    try {
      await recordWitnessAttestation(assignment.invitation_id, decision, decision === "ATTESTED");
      setWitnessConfirmationId(null);
      await loadWitnessAssignments();
    } catch (err) {
      setWitnessError(err instanceof Error ? err.message : "Unable to record your witness response.");
    } finally {
      setWitnessBusyId(null);
    }
  }

  async function loadActivity() {
    setLoadingActivity(true);
    try {
      const response = await getMyActivity();
      setActivity(response.data);
    } catch {
      setActivity([]);
    } finally {
      setLoadingActivity(false);
    }
  }

  async function loadBeneficiaryRelationships() {
    setLoadingRelationships(true);
    setBeneficiaryRelationshipError("");
    try {
      const response = await getMyBeneficiaryRelationships();
      setBeneficiaryRelationships(response.data);
    } catch (err) {
      setBeneficiaryRelationshipError(err instanceof Error ? err.message : "Unable to load beneficiary relationships.");
    } finally {
      setLoadingRelationships(false);
    }
  }

  async function loadBeneficiaryAllocations() {
    setLoadingBeneficiaryAllocations(true);
    setBeneficiaryAllocationError("");
    try {
      const response = await getMyBeneficiaryAllocations();
      setBeneficiaryAllocations(response.data);
    } catch (err) {
      setBeneficiaryAllocationError(err instanceof Error ? err.message : "Unable to load your released allocations.");
    } finally {
      setLoadingBeneficiaryAllocations(false);
    }
  }

  async function loadBeneficiaryCases() {
    setLoadingBeneficiaryCases(true);
    setBeneficiaryCaseError("");
    try {
      const response = await getCases();
      setBeneficiaryCases(response.data);
    } catch (err) {
      setBeneficiaryCaseError(err instanceof Error ? err.message : "Unable to load your verification cases.");
    } finally {
      setLoadingBeneficiaryCases(false);
    }
  }

  async function loadLawyerCases() {
    setLoadingLawyerCases(true);
    setLawyerCaseError("");
    try {
      const response = await getCases();
      setLawyerCases(response.data);
    } catch (err) {
      setLawyerCaseError(err instanceof Error ? err.message : "Unable to load assigned verification cases.");
    } finally {
      setLoadingLawyerCases(false);
    }
  }

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

  async function loadWills() {
    setLoadingRelationships(true);
    try {
      const response = await getWills();
      setWills(response.data);
      const relationshipGroups = await Promise.all(response.data.map(async (will) => {
        try {
          const beneficiaryResponse = await getWillBeneficiaries(will.id);
          return beneficiaryResponse.data.map((relationship) => ({ ...relationship, will_title: will.title }));
        } catch {
          return [];
        }
      }));
      setWillBeneficiaries(relationshipGroups.flat());
    } catch {
      setWillError("Unable to load your wills.");
    } finally {
      setLoadingRelationships(false);
    }
  }

  async function handleSendInvite(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setInviteError("");
    setInviteSuccess("");
    setInviteBusy(true);
    try {
      if (!inviteForm.will) {
        setInviteError("Select the will this collaborator is being invited to.");
        return;
      }
      const response = await sendInvitation({ ...inviteForm, will: Number(inviteForm.will) });
      setInviteSuccess(response.message || "Invitation sent successfully.");
      setInviteForm({ email: "", first_name: "", last_name: "", role: "WITNESS", message: "", will: "" });
      await loadInvitations();
      setTimeout(() => setShowInviteModal(false), 2000);
    } catch (err) {
      setInviteError(err instanceof Error ? err.message : "Failed to send invitation.");
    } finally {
      setInviteBusy(false);
    }
  }

  async function downloadAccountData() {
    setExportBusy(true);
    setExportMessage("");
    try {
      const profileResponse = await getProfile();
      const isWillOwner = profileResponse.data.role === "OWNER" || profileResponse.data.role === "MEMBER";
      const hasRelationships = profileResponse.data.role === "MEMBER" || profileResponse.data.role === "BENEFICIARY";
      const [willResponse, relationshipResponse, activityResponse] = await Promise.all([
        isWillOwner ? getWills() : Promise.resolve({ data: [] as Will[] }),
        hasRelationships ? getMyBeneficiaryRelationships() : Promise.resolve({ data: [] as BeneficiarySelfRelationship[] }),
        getMyActivity(),
      ]);
      const contents = JSON.stringify({
        exported_at: new Date().toISOString(),
        profile: profileResponse.data,
        wills: willResponse.data,
        beneficiary_relationships: relationshipResponse.data,
        activity: activityResponse.data,
      }, null, 2);
      const objectUrl = URL.createObjectURL(new Blob([contents], { type: "application/json" }));
      const downloadLink = document.createElement("a");
      downloadLink.href = objectUrl;
      downloadLink.download = `willchain-account-data-${new Date().toISOString().slice(0, 10)}.json`;
      downloadLink.click();
      window.setTimeout(() => URL.revokeObjectURL(objectUrl), 1000);
      setExportMessage("Your account data download has started.");
    } catch (err) {
      setExportMessage(err instanceof Error ? err.message : "Unable to export account data.");
    } finally {
      setExportBusy(false);
    }
  }

  const roleTitleMap: Record<string, string> = {
    OWNER: "Will Owner / Testator",
    MEMBER: "WillChain Member",
    WITNESS: "Designated Witness",
    BENEFICIARY: "Designated Beneficiary",
    LAWYER_VERIFIER: "Authorized Legal Verifier",
    ADMINISTRATOR: "System Administrator",
  };
  const visibleActivity = showAllActivity ? activity : activity.slice(0, 5);
  const capabilities = roleCapabilities[profileUser?.role ?? "MEMBER"];
  const visibleInvitations = invitations;
  const hasWitnessWorkspace = profileUser?.role === "WITNESS" || collaborations.some((item) => item.role === "WITNESS");
  const hasLawyerWorkspace = profileUser?.role === "LAWYER_VERIFIER" || collaborations.some((item) => item.role === "LAWYER_VERIFIER");
  const hasBeneficiaryWorkspace = profileUser?.role === "BENEFICIARY" || beneficiaryRelationships.length > 0 || beneficiaryAllocations.length > 0 || Boolean(beneficiaryRelationshipError || beneficiaryAllocationError || beneficiaryCaseError);
  const visibleBeneficiaries = willBeneficiaries;
  const assignedLawyerCases = lawyerCases.filter((item) => item.assigned_lawyer_id === profileUser?.id);
  const openLawyerCases = assignedLawyerCases.filter((item) => !["APPROVED", "REJECTED", "WITHDRAWN"].includes(item.status));
  const beneficiaryClaimCases = beneficiaryCases.filter((item) => item.submission_type === "BENEFICIARY_CLAIM");
  const latestBeneficiaryCase = [...beneficiaryClaimCases].sort((left, right) => Date.parse(right.created_at) - Date.parse(left.created_at))[0];
  const verifiedBeneficiaryRelationships = beneficiaryRelationships.filter((item) => item.identity_verification_status === "VERIFIED").length;
  const workspaceIntro = profileUser?.role === "LAWYER_VERIFIER"
    ? "Review assigned legal verification matters with read-only access to authorized will content."
    : profileUser?.role === "WITNESS"
      ? "Review will-specific witness requests and record your response to a finalized signing attestation."
      : profileUser?.role === "BENEFICIARY"
        ? "Review the allocations and relationship records authorized for your account."
        : collaborations.length
          ? "Manage your will and review any role-specific collaborator responsibilities assigned to this account."
        : "Your digital will, your legacy, in your control.";

  return (
    <DashboardShell profileUser={profileUser}>
      <div className="dashboard-page">
      <section className="dashboard-overview">
        <div className="dashboard-welcome-banner">
          <div className="dashboard-welcome-copy">
            <p className="dashboard-welcome-role">{roleTitleMap[profileUser?.role ?? ""] ?? "Protected Workspace"}</p>
            <h1 className="dashboard-welcome-title">Welcome back, {profileUser?.first_name || "WillChain member"}</h1>
            <p>{workspaceIntro}</p>
            {collaborationError && <p role="alert" className="mt-3 text-sm text-[#8c422c]">{collaborationError}</p>}
            {(beneficiaryRelationshipError || beneficiaryAllocationError || beneficiaryCaseError) && <p role="alert" className="mt-3 text-sm text-[#8c422c]">Some beneficiary workspace data could not be loaded: {beneficiaryRelationshipError || beneficiaryAllocationError || beneficiaryCaseError}</p>}
            <div className="dashboard-welcome-badges">
              <span><CheckCircle2 size={13} /> Role: {profileUser?.role ?? "Loading"}</span>
              <span><CheckCircle2 size={13} /> Account: {profileUser?.account_status ?? "Loading"}</span>
              <span><ShieldCheck size={13} /> Email: {profileUser?.email_verified ? "Verified" : "Pending"}</span>
            </div>
          </div>
          <blockquote className="dashboard-welcome-quote">“A well-prepared will isn’t just about what you leave behind—it’s about peace of mind for those you love.”</blockquote>
        </div>

        {profileUser?.role === "LAWYER_VERIFIER" ? (
          <div className="dashboard-status-grid">
            <DashboardMetricCard label="Assigned matters" value={loadingLawyerCases ? "Loading" : String(assignedLawyerCases.length)} note="Cases assigned to your verifier account" icon={Gavel} />
            <DashboardMetricCard label="Open matters" value={loadingLawyerCases ? "Loading" : String(openLawyerCases.length)} note="Cases that still need a workflow decision" icon={Activity} tone="purple" />
            <DashboardMetricCard label="Approved cases" value={loadingLawyerCases ? "Loading" : String(assignedLawyerCases.filter((item) => item.status === "APPROVED").length)} note="Cases with an approved review outcome" icon={CheckCircle2} tone="cyan" />
            <DashboardMetricCard label="Will access" value="Read-only" note="Will contents remain unchanged by legal review" icon={LockKeyhole} tone="purple" />
          </div>
        ) : profileUser?.role === "BENEFICIARY" ? (
          <div className="dashboard-status-grid">
            <DashboardMetricCard label="Claim status" value={loadingBeneficiaryCases ? "Loading" : latestBeneficiaryCase ? latestBeneficiaryCase.status.replaceAll("_", " ") : beneficiaryAllocations.length ? "Active" : beneficiaryRelationships.length ? "Awaiting release" : "No active claim"} note="Latest verification case or authorized allocation" icon={CheckCircle2} />
            <DashboardMetricCard label="Identity verification" value={loadingRelationships ? "Loading" : beneficiaryRelationships.length && verifiedBeneficiaryRelationships === beneficiaryRelationships.length ? "Verified" : beneficiaryRelationships.length ? "Pending" : "Not started"} note="Email challenge is required before a release claim" icon={ShieldCheck} tone="purple" />
            <DashboardMetricCard label="Released allocations" value={loadingBeneficiaryAllocations ? "Loading" : String(beneficiaryAllocations.length)} note="Individually authorized for this account" icon={Users} tone="cyan" />
            <DashboardMetricCard label="Private access" value="Restricted" note="No access to the full will or other beneficiaries' shares" icon={LockKeyhole} tone="purple" />
          </div>
        ) : profileUser?.role === "WITNESS" ? (
          <div className="dashboard-status-grid">
            <DashboardMetricCard label="Account status" value={profileUser.account_status} note="WillChain account standing" icon={CheckCircle2} />
            <DashboardMetricCard label="Email verification" value={profileUser.email_verified ? "Verified" : "Pending"} note="Account email verification" icon={ShieldCheck} tone="purple" />
            <DashboardMetricCard label="Attestation requests" value={loadingWitnessAssignments ? "Loading" : String(witnessAssignments.filter((item) => item.attestation_status === "PENDING").length)} note="Pending responses for finalized wills" icon={UserCheck} tone="cyan" />
            <DashboardMetricCard label="Will access" value="Restricted" note="A witness role does not grant will-content access" icon={LockKeyhole} tone="purple" />
          </div>
        ) : (
        <div className="dashboard-status-grid">
          <div className="rounded-xl border border-[#dce4df] bg-[#fffdf8] p-6 shadow-sm">
            <p className="dashboard-status-label"><span className="dashboard-status-icon green"><CheckCircle2 size={18} /></span>Account status</p>
            <p className="mt-3 text-xl font-semibold text-[#176b5b]">
              {profileUser?.account_status ?? "Loading..."}
            </p>
          </div>
          <div className="rounded-xl border border-[#dce4df] bg-[#fffdf8] p-6 shadow-sm">
            <p id="verification" className="dashboard-status-label"><span className="dashboard-status-icon purple"><ShieldCheck size={18} /></span>Verification status</p>
            <p className="mt-3 text-base font-medium text-[#17372f]">
              {profileUser?.email_verified ? "Verified" : "Pending"}
            </p>
          </div>
          <div className="rounded-xl border border-[#dce4df] bg-[#fffdf8] p-6 shadow-sm">
            <p className="dashboard-status-label"><span className="dashboard-status-icon"><UserRound size={18} /></span>Role</p>
            <p className="mt-3 text-xl font-semibold text-[#17372f]">
              {profileUser?.role ? roleTitleMap[profileUser.role] : "Loading..."}
            </p>
          </div>
          <div className="rounded-xl border border-[#dce4df] bg-[#fffdf8] p-6 shadow-sm">
            <p className="dashboard-status-label"><span className="dashboard-status-icon cyan"><LockKeyhole size={18} /></span>Private access</p>
            <p className="mt-3 text-base font-medium text-[#17372f]">Role-scoped</p>
            <p className="mt-1 text-xs text-[#60776e]">Your available workspace follows your account permissions.</p>
          </div>
        </div>
        )}

        <div className={`dashboard-template-grid ${profileUser?.role === "OWNER" ? "dashboard-template-grid-owner" : ""}`}>
          <div className="dashboard-template-primary">
        {/* --- ROLE-SPECIFIC WORKSPACE CONTENT --- */}
        {profileUser?.role === "OWNER" && (
          <div className="dashboard-owner-workspace">
            <div className="rounded-xl border border-[#dce4df] bg-white p-6 shadow-sm">
              <div className="flex flex-wrap items-start justify-between gap-4">
                <div>
                  <h2 className="text-2xl font-semibold text-[#17372f]">My Will</h2>
                  <p className="mt-1 text-sm text-[#60776e]">Draft, review, and finalize your private digital will.</p>
                </div>
                <button type="button" onClick={() => router.push("/dashboard/wills?new=1")} className="inline-flex items-center gap-2 rounded-lg bg-[#176b5b] px-4 py-2.5 text-sm font-semibold text-white hover:bg-[#0f5548]">
                  <Plus size={16} /> New will
                </button>
              </div>

              {willError && <div className="mt-4 rounded-lg bg-[#fff3ed] p-3 text-sm text-[#8c422c]" role="alert">{willError}</div>}

              {wills.length === 0 ? (
                <div className="dashboard-will-empty">
                  <span className="dashboard-will-empty-icon"><FilePlus2 size={23} /></span>
                  <strong>No Will created yet</strong>
                  <p>Start creating your digital will to secure your legacy and protect your loved ones.</p>
                  <Link href="/dashboard/wills" className="dashboard-create-will">Create My Will</Link>
                </div>
              ) : <div className="dashboard-will-card-grid">
                {wills.map((will) => (
                  <article key={will.id} className="dashboard-will-card">
                    <div className="dashboard-will-card-copy">
                      <p>{will.title}</p>
                      <small>Version {will.version} · Updated {new Date(will.updated_at).toLocaleDateString()}</small>
                    </div>
                    <div className="dashboard-will-card-actions">
                      <span className={`dashboard-will-status ${will.status === "FINALIZED" ? "finalized" : "draft"}`}>{will.status}</span>
                      {will.status === "DRAFT" && <button type="button" onClick={() => router.push(`/dashboard/wills?willId=${will.id}&step=0`)} className="dashboard-will-edit">Edit</button>}
                      {will.status === "DRAFT" && <button type="button" title="Review this draft before finalizing" onClick={() => router.push(`/dashboard/wills?willId=${will.id}&step=6`)} className="dashboard-will-review">Review</button>}
                    </div>
                  </article>
                ))}
                <Link href="/dashboard/wills" className="dashboard-view-all">View All <ArrowUpRight size={12} /></Link>
              </div>}
            </div>

            <div id="people" className="dashboard-people-heading">
              <div>
                <h2 className="text-2xl font-semibold text-[#17372f]">Estate Collaborators & Invitations</h2>
                <p className="mt-1 text-sm text-[#60776e]">
                  Invite witnesses and legal verifiers here. Manage beneficiary onboarding from a draft will.
                </p>
              </div>
              <button
                type="button"
                onClick={() => { setShowInviteModal(true); setInviteError(""); setInviteSuccess(""); setInviteForm((current) => ({ ...current, will: current.will || wills.find((will) => will.status === "DRAFT")?.id || wills[0]?.id || "" })); }}
                className="inline-flex items-center gap-2 rounded-lg bg-[#176b5b] px-4 py-2.5 text-sm font-semibold text-white shadow-sm hover:bg-[#0f5548]"
              >
                <UserPlus size={16} /> Invite Collaborator
              </button>
            </div>

            {/* Invitations list */}
            <div className="mt-6">
              <nav className="dashboard-people-filters" aria-label="People directories">
                {([
                  ["/dashboard#people", "Everyone", invitations.length + willBeneficiaries.length],
                  ["/dashboard/people/lawyers", "Lawyers", invitations.filter((invitation) => invitation.role === "LAWYER_VERIFIER").length],
                  ["/dashboard/people/witnesses", "Witnesses", invitations.filter((invitation) => invitation.role === "WITNESS").length],
                  ["/dashboard/people/beneficiaries", "Beneficiaries", willBeneficiaries.length],
                ] as const).map(([href, label, count]) => {
                  return <Link key={href} href={href}>{label}<span>{count}</span></Link>;
                })}
              </nav>

              <div className="dashboard-people-results">
                <section className="dashboard-people-group">
                  <h3>Lawyers and Witnesses</h3>
                  {loadingInvitations ? <p className="dashboard-people-empty">Loading collaborator records...</p> : visibleInvitations.length === 0 ? <p className="dashboard-people-empty">No people in this group yet.</p> : <div className="dashboard-person-grid">
                    {visibleInvitations.map((invitation) => {
                      const displayName = [invitation.accepted_user_profile?.first_name || invitation.first_name, invitation.accepted_user_profile?.last_name || invitation.last_name].filter(Boolean).join(" ") || invitation.email;
                      const personKey = `invitation-${invitation.id}`;
                      const expanded = expandedPersonKey === personKey;
                      return <article className="dashboard-person-card" key={invitation.id}>
                        <button type="button" className="dashboard-person-trigger" aria-expanded={expanded} onClick={() => setExpandedPersonKey(expanded ? null : personKey)}>
                          <PersonAvatar name={displayName} image={invitation.accepted_user_profile?.avatar} />
                          <span className="dashboard-person-copy"><strong>{displayName}</strong><span><Mail size={12} />{invitation.email}</span><small>{roleTitleMap[invitation.role] ?? invitation.role} · {invitation.status}</small></span>
                          <ChevronRight className={expanded ? "dashboard-person-chevron expanded" : "dashboard-person-chevron"} size={16} />
                        </button>
                        {expanded && <div className="dashboard-person-details">
                          <p><strong>Connection:</strong> {roleTitleMap[invitation.role] ?? invitation.role}</p>
                          <p><strong>Invitation:</strong> {invitation.status} · Sent {new Date(invitation.created_at).toLocaleDateString()}</p>
                          {invitation.message && <p><strong>Message:</strong> {invitation.message}</p>}
                          <p><strong>Will:</strong> {invitation.will_title}</p>
                          {invitation.accepted_user_profile && <p><strong>Account:</strong> Invitation accepted</p>}
                        </div>}
                      </article>;
                    })}
                  </div>}
                </section>

                <section className="dashboard-people-group">
                  <h3>Beneficiaries</h3>
                  {loadingRelationships ? <p className="dashboard-people-empty">Loading beneficiary relationships...</p> : visibleBeneficiaries.length === 0 ? <p className="dashboard-people-empty">No beneficiaries have been added to your wills yet.</p> : <div className="dashboard-person-grid">
                    {visibleBeneficiaries.map((relationship) => {
                      const displayName = [relationship.beneficiary_user_profile?.first_name, relationship.beneficiary_user_profile?.last_name].filter(Boolean).join(" ") || relationship.full_name || relationship.recipient_email;
                      const personKey = `beneficiary-${relationship.will}-${relationship.id}`;
                      const expanded = expandedPersonKey === personKey;
                      return <article className="dashboard-person-card" key={`${relationship.will}-${relationship.id}`}>
                        <button type="button" className="dashboard-person-trigger" aria-expanded={expanded} onClick={() => setExpandedPersonKey(expanded ? null : personKey)}>
                          <PersonAvatar name={displayName} image={relationship.beneficiary_user_profile?.avatar} />
                          <span className="dashboard-person-copy"><strong>{displayName}</strong><span><Mail size={12} />{relationship.beneficiary_user_email || relationship.recipient_email}</span><small>{relationship.relationship_type} · {relationship.status} · {relationship.will_title}</small></span>
                          <ChevronRight className={expanded ? "dashboard-person-chevron expanded" : "dashboard-person-chevron"} size={16} />
                        </button>
                        {expanded && <div className="dashboard-person-details">
                          <p><strong>Connection:</strong> {relationship.relationship_type.toLowerCase()} beneficiary</p>
                          <p><strong>Will:</strong> {relationship.will_title}</p>
                          <p><strong>Relationship status:</strong> {relationship.status}</p>
                          {relationship.latest_invitation_status && <p><strong>Invitation:</strong> {relationship.latest_invitation_status}</p>}
                          {relationship.accepted_at && <p><strong>Accepted:</strong> {new Date(relationship.accepted_at).toLocaleDateString()}</p>}
                        </div>}
                      </article>;
                    })}
                  </div>}
                </section>
              </div>
            </div>
          </div>
        )}

        {hasLawyerWorkspace && (
          <div id="role-workspace" className="mt-10 rounded-xl border border-[#dce4df] bg-white p-6 shadow-sm">
            <div className="flex flex-wrap items-start justify-between gap-4">
              <div>
                <h2 className="text-xl font-semibold text-[#17372f]">Assigned verification matters</h2>
                <p className="mt-1 text-sm text-[#60776e]">Review only cases assigned to your account. Authorized will access is read-only.</p>
              </div>
              <Link href="/dashboard/verification" className="inline-flex items-center gap-2 rounded-lg bg-[#176b5b] px-4 py-2.5 text-sm font-semibold text-white">Open review workspace <ArrowUpRight size={14} /></Link>
            </div>
            {lawyerCaseError && <p role="alert" className="mt-4 rounded-lg bg-[#fff3ed] p-3 text-sm text-[#8c422c]">{lawyerCaseError}</p>}
            {loadingLawyerCases ? <p className="mt-5 text-sm text-[#60776e]">Loading assigned cases...</p> : openLawyerCases.length === 0 ? (
              <p className="mt-5 rounded-lg border border-dashed border-[#dce4df] p-5 text-sm text-[#60776e]">No open cases are currently assigned to you.</p>
            ) : (
              <div className="mt-5 divide-y divide-[#e7ece9]">
                {openLawyerCases.slice(0, 5).map((item) => (
                  <article key={item.id} className="flex flex-wrap items-center justify-between gap-3 py-4">
                    <div>
                      <p className="font-semibold text-[#17372f]">Case #{item.id} · {item.case_type.replaceAll("_", " ")}</p>
                      <p className="mt-1 text-xs text-[#60776e]">{item.submission_type.replaceAll("_", " ")} · Updated {new Date(item.updated_at).toLocaleDateString()}</p>
                    </div>
                    <span className="rounded-full bg-[#eef4f1] px-3 py-1 text-xs font-semibold text-[#176b5b]">{item.status.replaceAll("_", " ")}</span>
                  </article>
                ))}
              </div>
            )}
          </div>
        )}

        {hasWitnessWorkspace && (
          <div id="role-workspace" className="mt-10 rounded-xl border border-[#dce4df] bg-white p-6 shadow-sm">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div className="flex items-start gap-3">
                <UserCheck className="mt-1 text-[#176b5b]" size={24} />
                <div>
                <h2 className="text-xl font-semibold text-[#17372f]">Witness workspace</h2>
                <p className="mt-1 text-sm leading-6 text-[#60776e]">Review invitations assigned to this account. A response records your statement only; it is not an electronic signature or legal validation.</p>
                <Link href="/profile" className="mt-4 inline-flex items-center gap-2 text-sm font-semibold text-[#176b5b] hover:underline">Review your witness profile <ArrowUpRight size={13} /></Link>
                </div>
              </div>
              <span className="rounded-full bg-[#eef4f1] px-3 py-1 text-xs font-semibold text-[#176b5b]">{witnessAssignments.filter((item) => item.attestation_status === "PENDING").length} pending response(s)</span>
            </div>
            {collaborationError && <p role="alert" className="mt-4 text-sm text-[#8c422c]">{collaborationError}</p>}
            {witnessError && <p role="alert" className="mt-4 text-sm text-[#8c422c]">{witnessError}</p>}
            {loadingWitnessAssignments ? (
              <p className="mt-5 text-sm text-[#60776e]">Loading your witness assignments...</p>
            ) : witnessAssignments.length === 0 ? (
              <p className="mt-5 rounded-lg border border-dashed border-[#dce4df] p-5 text-sm text-[#60776e]">No accepted will-specific witness assignments are linked to this account yet.</p>
            ) : (
              <div className="mt-5 divide-y divide-[#e7ece9]">
                {witnessAssignments.map((assignment) => (
                  <article key={assignment.invitation_id} className="py-4">
                    <div className="flex flex-wrap items-start justify-between gap-3">
                      <div>
                        <h3 className="font-semibold text-[#17372f]">{assignment.will_title}</h3>
                        <p className="mt-1 text-xs text-[#60776e]">Will version {assignment.will_version} · {assignment.will_status.replaceAll("_", " ")}</p>
                        {assignment.responded_at && <p className="mt-1 text-xs text-[#60776e]">Responded {new Date(assignment.responded_at).toLocaleString()} · version {assignment.attested_version}</p>}
                      </div>
                      <span className="rounded-full bg-[#eef4f1] px-3 py-1 text-xs font-semibold text-[#176b5b]">{assignment.attestation_status.replaceAll("_", " ")}</span>
                    </div>
                    {assignment.attestation_status === "PENDING" && (
                      <div className="mt-4 flex flex-wrap items-center gap-3">
                        <label className="flex items-center gap-2 text-sm text-[#425b52]">
                          <input type="checkbox" checked={witnessConfirmationId === assignment.invitation_id} onChange={(event) => setWitnessConfirmationId(event.target.checked ? assignment.invitation_id : null)} />
                          I personally observed the will owner sign this finalized version.
                        </label>
                        <button type="button" disabled={witnessBusyId === assignment.invitation_id || witnessConfirmationId !== assignment.invitation_id} onClick={() => handleWitnessResponse(assignment, "ATTESTED")} className="rounded-lg bg-[#176b5b] px-3 py-2 text-xs font-semibold text-white disabled:opacity-50">
                          {witnessBusyId === assignment.invitation_id ? "Saving..." : "Confirm observed signing"}
                        </button>
                        <button type="button" disabled={witnessBusyId === assignment.invitation_id} onClick={() => handleWitnessResponse(assignment, "DECLINED")} className="rounded-lg border border-[#dce4df] px-3 py-2 text-xs font-semibold text-[#60776e] disabled:opacity-50">Decline</button>
                      </div>
                    )}
                    {assignment.attestation_status === "NOT_READY" && <p className="mt-3 text-sm text-[#60776e]">The owner has not finalized this will; no attestation response is available.</p>}
                  </article>
                ))}
              </div>
            )}
          </div>
        )}

        {hasBeneficiaryWorkspace && (
          <div id="role-workspace" className="mt-10 rounded-xl border border-[#dce4df] bg-white p-8 shadow-sm">
            <div className="flex items-center gap-3">
              <Users className="text-[#176b5b]" size={28} />
              <div>
                <h2 className="text-xl font-semibold text-[#17372f]">My Beneficiary Relationships</h2>
                <p className="text-sm text-[#60776e]">Review relationship status only. Beneficiary status does not provide access to private will contents.</p>
              </div>
            </div>
            <BeneficiaryRelationshipList relationships={beneficiaryRelationships} loading={loadingRelationships} />
            <section className="mt-6 rounded-xl border border-[#e7ece9] p-5">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <h3 className="font-semibold text-[#17372f]">My verification cases</h3>
                  <p className="mt-1 text-sm text-[#60776e]">Track cases you initiated and their current review status.</p>
                </div>
                <Link href="/dashboard/verification" className="inline-flex items-center gap-2 rounded-lg border border-[#dce4df] px-4 py-2 text-sm font-semibold text-[#176b5b]">Open case workspace <ChevronRight size={14} /></Link>
              </div>
              {beneficiaryCaseError && <p role="alert" className="mt-4 text-sm text-[#8c422c]">{beneficiaryCaseError}</p>}
              {loadingBeneficiaryCases ? <p className="mt-4 text-sm text-[#60776e]">Loading your verification cases...</p> : beneficiaryClaimCases.length === 0 ? (
                <p className="mt-4 text-sm text-[#60776e]">You have not initiated a verification case.</p>
              ) : (
                <ul className="mt-4 divide-y divide-[#e7ece9]">
                  {beneficiaryClaimCases.slice(0, 3).map((item) => (
                    <li key={item.id} className="flex flex-wrap items-center justify-between gap-2 py-3 text-sm">
                      <span><strong className="text-[#17372f]">Case #{item.id}</strong><small className="ml-2 text-[#60776e]">{item.case_type.replaceAll("_", " ")}</small></span>
                      <span className="text-xs font-semibold text-[#176b5b]">{item.status.replaceAll("_", " ")}</span>
                    </li>
                  ))}
                </ul>
              )}
            </section>
            <section className="mt-6 rounded-xl border border-[#e7ece9] p-5">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <h3 className="font-semibold text-[#17372f]">Authorized allocations</h3>
                  <p className="mt-1 text-sm text-[#60776e]">Only individually authorized shares appear in your allocation workspace.</p>
                </div>
                <Link href="/dashboard/beneficiary-allocations" className="inline-flex items-center gap-2 rounded-lg bg-[#176b5b] px-4 py-2 text-sm font-semibold text-white">View allocations <ChevronRight size={14} /></Link>
              </div>
              {beneficiaryAllocationError && <p role="alert" className="mt-4 text-sm text-[#8c422c]">{beneficiaryAllocationError}</p>}
              {loadingBeneficiaryAllocations ? <p className="mt-4 text-sm text-[#60776e]">Loading released allocations...</p> : beneficiaryAllocations.length === 0 ? (
                <p className="mt-4 text-sm text-[#60776e]">No allocation has been authorized for release to your account.</p>
              ) : (
                <ul className="mt-4 divide-y divide-[#e7ece9]">
                  {beneficiaryAllocations.slice(0, 3).map((allocation) => (
                    <li key={allocation.id} className="flex flex-wrap justify-between gap-2 py-3 text-sm">
                      <span><strong className="text-[#17372f]">{allocation.will_title}</strong><small className="ml-2 text-[#60776e]">{allocation.allocation_type.replaceAll("_", " ")}</small></span>
                      <span className="text-xs font-semibold text-[#176b5b]">Authorized</span>
                    </li>
                  ))}
                </ul>
              )}
            </section>
          </div>
        )}

        {profileUser?.role === "MEMBER" && (
          <div id="role-workspace" className="mt-10 rounded-xl border border-[#dce4df] bg-white p-8 shadow-sm">
            <div className="flex items-center gap-3">
              <Users className="text-[#176b5b]" size={28} />
              <div>
                <h2 className="text-xl font-semibold text-[#17372f]">Member Account</h2>
                <p className="text-sm text-[#60776e]">
                  You can manage your own wills and beneficiary relationships. Accepting another person’s invitation does not grant access to their private will.
                </p>
                <Link className="mt-3 inline-block text-sm font-bold text-[#176b5b] hover:underline" href="/dashboard/wills">Manage my wills</Link>
              </div>
            </div>
            <BeneficiaryRelationshipList relationships={beneficiaryRelationships} loading={loadingRelationships} />
          </div>
        )}

            <section className="dashboard-permissions-card">
              <h2><ShieldCheck size={16} /> Your Role & Permissions</h2>
              <div className="dashboard-permission-grid">
                {capabilities.map((capability) => (
                  <Link key={capability.title} href={capability.href} className="dashboard-permission-link">
                    <Check size={13} />
                    <strong>{capability.title}</strong>
                    <small>{capability.description}</small>
                  </Link>
                ))}
              </div>
            </section>
          </div>

          <div className="dashboard-template-middle">
            <section className="dashboard-quick-actions">
              <h2><Zap size={16} /> Quick Actions</h2>
              {hasLawyerWorkspace && <Link href="/dashboard/verification" className="dashboard-quick-action"><span className="dashboard-quick-icon"><Gavel size={16} /></span><span><strong>Review Assigned Cases</strong><small>Open your legal verification workspace</small></span><ChevronRight size={14} /></Link>}
              {hasBeneficiaryWorkspace && <Link href="/dashboard/beneficiary-allocations" className="dashboard-quick-action"><span className="dashboard-quick-icon"><LockKeyhole size={16} /></span><span><strong>View Released Allocations</strong><small>Open only shares authorized for you</small></span><ChevronRight size={14} /></Link>}
              {hasWitnessWorkspace && <Link href="/dashboard#role-workspace" className="dashboard-quick-action"><span className="dashboard-quick-icon"><UserCheck size={16} /></span><span><strong>Witness Workspace</strong><small>Review your will-specific attestation requests</small></span><ChevronRight size={14} /></Link>}
              <Link href="/profile" className="dashboard-quick-action"><span className="dashboard-quick-icon"><UserRound size={16} /></span><span><strong>Update Profile</strong><small>Manage your personal information</small></span><ChevronRight size={14} /></Link>
              <Link href="/profile#change-password" className="dashboard-quick-action"><span className="dashboard-quick-icon"><KeyRound size={16} /></span><span><strong>Change Password</strong><small>Keep your account secure</small></span><ChevronRight size={14} /></Link>
              <Link href="/forgot-password" className="dashboard-quick-action"><span className="dashboard-quick-icon"><LockKeyhole size={16} /></span><span><strong>Password Reset</strong><small>Reset your password if forgotten</small></span><ChevronRight size={14} /></Link>
              <button type="button" onClick={downloadAccountData} disabled={exportBusy} className="dashboard-quick-action dashboard-download-action"><span className="dashboard-quick-icon"><Download size={16} /></span><span><strong>{exportBusy ? "Preparing Download..." : "Download Your Data"}</strong><small>Export your profile, wills, relationships, and activity</small></span><ChevronRight size={14} /></button>
              {exportMessage && <p className="dashboard-export-message" role="status">{exportMessage}</p>}
              <Link href="/dashboard#activity" className="dashboard-quick-action"><span className="dashboard-quick-icon"><Activity size={16} /></span><span><strong>Recent Activity</strong><small>Review recent account events</small></span><ChevronRight size={14} /></Link>
            </section>

            <section id="notifications" className="dashboard-notification-card">
              <h2><Bell size={16} /> Notifications</h2>
              <p className="dashboard-notification-empty">Notifications are not enabled yet. Account activity is available in the Recent Activity panel.</p>
            </section>

            <section id="security" className="dashboard-security-card">
              <h2><LockKeyhole size={16} /> Security & Privacy</h2>
              <p>Your account uses authenticated access and role-scoped permissions. Private will content is not shared through beneficiary relationships.</p>
              <Link href="/profile">Learn more about account security <ArrowUpRight size={12} /></Link>
            </section>
          </div>

          <aside className="dashboard-template-side">
            <section className="dashboard-profile-card">
              <div className="dashboard-profile-card-heading"><h2>My Profile</h2><Link href="/profile">View Profile <ArrowUpRight size={12} /></Link></div>
              <div className="dashboard-profile-summary">
                <span className="dashboard-profile-avatar">{avatarUrl(profileUser?.avatar) ? <img src={avatarUrl(profileUser?.avatar)} alt="" /> : `${profileUser?.first_name?.[0] ?? "W"}${profileUser?.last_name?.[0] ?? "C"}`}</span>
                <span><strong>{`${profileUser?.first_name ?? ""} ${profileUser?.last_name ?? ""}`.trim() || "WillChain member"}</strong><small>{roleTitleMap[profileUser?.role ?? ""] ?? "Protected workspace"}</small></span>
              </div>
              <div className="dashboard-profile-details">
                <span><Mail size={13} />{profileUser?.email ?? "Email unavailable"}</span>
                {profileUser?.phone_number && <span><UserRound size={13} />{profileUser.phone_number}</span>}
                {profileUser?.created_at && <span><Activity size={13} />Member since {new Date(profileUser.created_at).toLocaleDateString()}</span>}
              </div>
              <div className="dashboard-verified-note"><ShieldCheck size={15} />{profileUser?.email_verified ? "Email verified" : "Email verification pending"}</div>
            </section>

            <section id="activity" className="dashboard-activity-card">
              <div className="dashboard-activity-heading"><h2><Activity size={16} /> Recent Activity</h2>{activity.length > 5 && <button type="button" onClick={() => setShowAllActivity((current) => !current)}>{showAllActivity ? "Show less" : "View all"} <ArrowUpRight size={11} /></button>}</div>
              {loadingActivity ? <p className="dashboard-activity-empty">Loading recent activity...</p> : visibleActivity.length === 0 ? <p className="dashboard-activity-empty">Your account activity will appear here when events are recorded.</p> : (
                <div className="dashboard-activity-list">
                  {visibleActivity.map((item) => (
                    <div key={item.id} className="dashboard-activity-item"><span className="dashboard-activity-icon"><Activity size={14} /></span><span><strong>{item.event_label}</strong><small>{new Date(item.created_at).toLocaleString()}</small></span></div>
                  ))}
                </div>
              )}
            </section>

            <section className="dashboard-legacy-card">
              <h2>{profileUser?.role === "OWNER" || profileUser?.role === "MEMBER" ? "Your legacy matters" : "Your WillChain workspace"}</h2>
              <p>{profileUser?.role === "OWNER" || profileUser?.role === "MEMBER" ? "Take the next step in securing your future and protecting what matters most." : "Keep your account details current and review role-specific updates here."}</p>
              <Link href={profileUser?.role === "OWNER" || profileUser?.role === "MEMBER" ? "/dashboard/wills" : "/profile"}>{profileUser?.role === "OWNER" || profileUser?.role === "MEMBER" ? "Create My Will" : "View My Profile"} <ChevronRight size={13} /></Link>
            </section>
          </aside>
        </div>
      </section>

      {/* Invite Collaborator Dialog */}
      {showInviteModal && (
        <div className="fixed inset-0 z-50 grid place-items-center bg-black/40 p-4" role="dialog" aria-modal="true">
          <div className="w-full max-w-lg rounded-2xl bg-white p-6 shadow-xl sm:p-8">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-xl font-semibold text-[#17372f]">Invite an Estate Collaborator</h3>
                <p className="mt-1 text-xs text-[#60776e]">Send an invitation to a Witness or Legal Verifier.</p>
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
                <label className="block text-xs font-semibold text-[#17372f]">Will</label>
                <select
                  required
                  value={inviteForm.will}
                  onChange={(e) => setInviteForm({ ...inviteForm, will: e.target.value ? Number(e.target.value) : "" })}
                  className="mt-1.5 w-full rounded-lg border border-[#dce4df] bg-white p-2.5 text-sm"
                >
                  <option value="">Select a will</option>
                  {wills.map((will) => <option key={will.id} value={will.id}>{will.title} · {will.status}</option>)}
                </select>
                {wills.length === 0 && <p className="mt-2 text-xs text-[#8c422c]">Create a will before inviting a collaborator.</p>}
              </div>
              <div>
                <label className="block text-xs font-semibold text-[#17372f]">Collaborator Role</label>
                <select
                  value={inviteForm.role}
                  onChange={(e) => setInviteForm({ ...inviteForm, role: e.target.value as InvitationRole })}
                  className="mt-1.5 w-full rounded-lg border border-[#dce4df] bg-white p-2.5 text-sm"
                >
                  <option value="WITNESS">Witness (To attest and sign your will)</option>
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
                  disabled={inviteBusy || wills.length === 0}
                  className="rounded-lg bg-[#176b5b] px-5 py-2 text-sm font-semibold text-white hover:bg-[#0f5548] disabled:opacity-60"
                >
                  {inviteBusy ? "Sending..." : "Send Invitation"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
      </div>
    </DashboardShell>
  );
}
