"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { ArrowLeft, ChevronRight, Gavel, Mail, UserCheck, Users } from "lucide-react";

import { DashboardShell } from "@/components/layout/dashboard-shell";
import { useAuth } from "@/lib/auth-context";
import { getWillBeneficiaries } from "@/services/beneficiary-service";
import { getInvitations, getWills } from "@/services/auth-service";
import type { BeneficiaryRelationship } from "@/types/beneficiaries";
import type { Invitation, User } from "@/types/auth";

type PeopleCategory = "lawyers" | "witnesses" | "beneficiaries";
type DirectoryBeneficiary = BeneficiaryRelationship & { will_title: string };

const directoryConfig = {
  lawyers: { title: "Lawyers and Legal Verifiers", description: "Review legal collaborators invited to your estate workspace.", icon: Gavel },
  witnesses: { title: "Witnesses", description: "Review people invited to witness your estate process.", icon: UserCheck },
  beneficiaries: { title: "Beneficiaries", description: "Review beneficiary relationships recorded across your wills.", icon: Users },
} satisfies Record<PeopleCategory, { title: string; description: string; icon: typeof Gavel }>;

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

function RoleInvitationCard({ invitation }: { invitation: Invitation }) {
  const [expanded, setExpanded] = useState(false);
  const name = [invitation.accepted_user_profile?.first_name || invitation.first_name, invitation.accepted_user_profile?.last_name || invitation.last_name].filter(Boolean).join(" ") || invitation.email;
  const role = invitation.role === "WITNESS" ? "Witness" : "Lawyer / Legal Verifier";

  return <article className="dashboard-person-card">
    <button type="button" className="dashboard-person-trigger" aria-expanded={expanded} onClick={() => setExpanded((current) => !current)}>
      <PersonAvatar name={name} image={invitation.accepted_user_profile?.avatar} />
      <span className="dashboard-person-copy"><strong>{name}</strong><span><Mail size={12} />{invitation.email}</span><small>{role} · {invitation.status}</small></span>
      <ChevronRight className={expanded ? "dashboard-person-chevron expanded" : "dashboard-person-chevron"} size={16} />
    </button>
    {expanded && <div className="dashboard-person-details">
      <p><strong>Connection:</strong> {role}</p>
      <p><strong>Invitation:</strong> {invitation.status} · Sent {new Date(invitation.created_at).toLocaleDateString()}</p>
      {invitation.message && <p><strong>Message:</strong> {invitation.message}</p>}
      {invitation.accepted_user_profile && <p><strong>Account:</strong> Invitation accepted</p>}
    </div>}
  </article>;
}

function BeneficiaryCard({ relationship }: { relationship: DirectoryBeneficiary }) {
  const [expanded, setExpanded] = useState(false);
  const name = [relationship.beneficiary_user_profile?.first_name, relationship.beneficiary_user_profile?.last_name].filter(Boolean).join(" ") || relationship.full_name || relationship.recipient_email;

  return <article className="dashboard-person-card">
    <button type="button" className="dashboard-person-trigger" aria-expanded={expanded} onClick={() => setExpanded((current) => !current)}>
      <PersonAvatar name={name} image={relationship.beneficiary_user_profile?.avatar} />
      <span className="dashboard-person-copy"><strong>{name}</strong><span><Mail size={12} />{relationship.beneficiary_user_email || relationship.recipient_email}</span><small>{relationship.relationship_type} · {relationship.status} · {relationship.will_title}</small></span>
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
}

export function PeopleDirectory({ category }: { category: PeopleCategory }) {
  const router = useRouter();
  const { user, initialLoading } = useAuth();
  const [profileUser, setProfileUser] = useState<User | null>(user);
  const [invitations, setInvitations] = useState<Invitation[]>([]);
  const [beneficiaries, setBeneficiaries] = useState<DirectoryBeneficiary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const config = directoryConfig[category];
  const Icon = config.icon;

  useEffect(() => {
    if (initialLoading) return;
    if (!user) {
      router.replace("/login");
      return;
    }
    if (user.role !== "OWNER") {
      router.replace("/dashboard");
      return;
    }

    let current = true;
    setProfileUser(user);
    setLoading(true);
    setError("");

    async function loadDirectory() {
      try {
        if (category === "beneficiaries") {
          const willsResponse = await getWills();
          const groups = await Promise.all(willsResponse.data.map(async (will) => {
            try {
              const response = await getWillBeneficiaries(will.id);
              return response.data.map((relationship) => ({ ...relationship, will_title: will.title }));
            } catch {
              return [];
            }
          }));
          if (current) setBeneficiaries(groups.flat());
        } else {
          const response = await getInvitations();
          const role = category === "lawyers" ? "LAWYER_VERIFIER" : "WITNESS";
          if (current) setInvitations(response.data.filter((invitation) => invitation.role === role));
        }
      } catch (loadError) {
        if (current) setError(loadError instanceof Error ? loadError.message : "People could not be loaded.");
      } finally {
        if (current) setLoading(false);
      }
    }

    void loadDirectory();
    return () => { current = false; };
  }, [category, initialLoading, router, user]);

  const peopleCount = category === "beneficiaries" ? beneficiaries.length : invitations.length;

  return <DashboardShell profileUser={profileUser}>
    <div className="dashboard-page">
      <section className="mx-auto grid max-w-7xl gap-6 px-5 py-8 sm:px-8 lg:px-12">
        <Link href="/dashboard#people" className="inline-flex w-fit items-center gap-2 text-sm font-semibold text-[#1261cb]"><ArrowLeft size={15} /> People overview</Link>
        <header className="dashboard-directory-heading">
          <span className="dashboard-directory-icon"><Icon size={21} /></span>
          <div><p className="dashboard-directory-eyebrow">Owner workspace / People</p><h1>{config.title}</h1><p>{config.description}</p></div>
        </header>

        <nav className="dashboard-people-filters" aria-label="People directories">
          <Link href="/dashboard/people/lawyers" aria-current={category === "lawyers" ? "page" : undefined}>Lawyers</Link>
          <Link href="/dashboard/people/witnesses" aria-current={category === "witnesses" ? "page" : undefined}>Witnesses</Link>
          <Link href="/dashboard/people/beneficiaries" aria-current={category === "beneficiaries" ? "page" : undefined}>Beneficiaries</Link>
        </nav>

        <section className="dashboard-directory-list" aria-label={config.title}>
          <div className="dashboard-directory-list-heading"><h2>{config.title}</h2><span>{peopleCount}</span></div>
          {error && <p className="dashboard-people-empty" role="alert">{error}</p>}
          {loading ? <p className="dashboard-people-empty">Loading {category}...</p> : category === "beneficiaries" ? beneficiaries.length === 0 ? <p className="dashboard-people-empty">No beneficiaries have been added to your wills yet.</p> : <div className="dashboard-person-grid">{beneficiaries.map((relationship) => <BeneficiaryCard key={`${relationship.will}-${relationship.id}`} relationship={relationship} />)}</div> : invitations.length === 0 ? <p className="dashboard-people-empty">No {category} have been invited yet.</p> : <div className="dashboard-person-grid">{invitations.map((invitation) => <RoleInvitationCard key={invitation.id} invitation={invitation} />)}</div>}
        </section>
      </section>
    </div>
  </DashboardShell>;
}