"use client";

import Link from "next/link";
import {
  ArrowRight,
  CheckCircle2,
  EyeOff,
  Fingerprint,
  Gavel,
  LockKeyhole,
  ShieldCheck,
  UserCheck,
  Users,
} from "lucide-react";
import { ThemeToggle } from "@/components/common/theme-provider";

const roles = [
  { icon: UserCheck, title: "Testator", badge: "OWNER PORTAL", description: "Create, draft, and manage your private will.", action: "Launch Testator Space" },
  { icon: Gavel, title: "Lawyer", badge: "LEGAL CONSOLE", description: "Review assigned wills and support governed release.", action: "Access Lawyer Workspace" },
  { icon: Users, title: "Beneficiary", badge: "BENEFICIARY PORTAL", description: "Confirm identity and follow your claim status.", action: "Open Beneficiary Portal" },
  { icon: CheckCircle2, title: "Witness", badge: "ATTESTATION PORTAL", description: "Review an invitation and complete assigned attestations.", action: "Open Witness Portal" },
  { icon: ShieldCheck, title: "System Administrator", badge: "AUDIT & OPS", description: "Support oversight, evidence, and account controls.", action: "Open Admin Console" },
];

export default function HomePage() {
  return (
    <main className="home-page">
      <nav className="home-nav">
        <Link href="/" className="brand-mark"><span className="brand-icon"><ShieldCheck size={18} /></span><span>WillChain <i>SL</i><small>SECURE DIGITAL WILL REGISTRY</small></span></Link>
        <div className="nav-actions">
          <ThemeToggle />
          <Link className="nav-sign-in" href="/login">Sign in</Link>
          <Link className="nav-create" href="/register">Create account <ArrowRight size={15} /></Link>
        </div>
      </nav>

      <section className="home-content">
        <div className="home-heading">
          <div className="secure-badge"><span /> Private by design <i>·</i> Sierra Leone legal framework</div>
          <h1>WillChain <span>SL</span></h1>
          <p>Secure digital wills, with controlled access and accountable records.</p>
        </div>

        <div className="trust-row" aria-label="WillChain security features">
          <span><Fingerprint size={14} /> Identity checks</span>
          <span><EyeOff size={14} /> Private workspace</span>
          <span><ShieldCheck size={14} /> Governed access</span>
        </div>

        <div className="role-grid">
          {roles.map(({ icon: Icon, title, badge, description, action }) => (
            <article className="role-card" key={title}>
              <div className="role-card-main"><span className="role-icon-wrap"><Icon className="role-icon" size={18} /></span><div className="role-card-copy"><div className="role-card-title"><h2>{title}</h2><span>{badge}</span></div><p>{description}</p></div></div>
              <Link href={title === "Testator" ? "/register" : "/login"} className="role-card-link">{action}<ArrowRight size={13} /></Link>
            </article>
          ))}
        </div>

        <div className="home-actions">
          <Link className="primary-action" href="/register">Get started with WillChain <ArrowRight size={17} /></Link>
          <Link className="secondary-action" href="/login"><LockKeyhole size={14} /> Log in to your workspace</Link>
        </div>

        <p className="privacy-note"><LockKeyhole size={14} /> Will information is shared only through authorized workflows.</p>
      </section>
      <footer className="home-footer"><span><strong>WillChain SL</strong><i>·</i> National Digital Estate &amp; Testamentary Infrastructure</span><span>Privacy by design · Human decisions remain human</span></footer>
    </main>
  );
}
