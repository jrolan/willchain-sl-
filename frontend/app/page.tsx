"use client";

import Link from "next/link";
import {
  ArrowRight,
  CheckCircle2,
  EyeOff,
  Fingerprint,
  Gavel,
  LockKeyhole,
  Scale,
  ShieldCheck,
  UserCheck,
  Users,
} from "lucide-react";
import { ThemeToggle } from "@/components/common/theme-provider";

const roles = [
  { icon: UserCheck, title: "Testator", description: "Create and manage a private will." },
  { icon: Gavel, title: "Lawyer", description: "Verify death documents and release conditions." },
  { icon: Users, title: "Beneficiary", description: "Confirm identity and track beneficiary status." },
  { icon: CheckCircle2, title: "Witness", description: "Confirm the will was created or signed." },
  { icon: ShieldCheck, title: "Admin", description: "Support oversight, evidence, and audit controls." },
];

export default function HomePage() {
  return (
    <main className="home-page">
      <nav className="home-nav">
        <Link href="/" className="brand-mark"><span className="brand-icon"><Scale size={19} /></span>WILLCHAIN SL</Link>
        <div className="nav-actions">
          <ThemeToggle />
          <Link className="nav-sign-in" href="/login">Sign in</Link>
          <Link className="nav-create" href="/register">Create account</Link>
        </div>
      </nav>

      <section className="home-content">
        <div className="home-heading">
          <div className="secure-badge"><Fingerprint size={15} /> Private by design</div>
          <h1>WillChain <span>SL</span></h1>
          <p>Secure digital wills, verified on-chain.</p>
        </div>

        <div className="trust-row" aria-label="WillChain security features">
          <span><Fingerprint size={14} /> Identity verified</span>
          <span><EyeOff size={14} /> Private by default</span>
          <span><ShieldCheck size={14} /> Auditable release</span>
        </div>

        <div className="role-grid">
          {roles.map(({ icon: Icon, title, description }) => (
            <article className="role-card" key={title}>
              <Icon className="role-icon" size={20} />
              <h2>{title}</h2>
              <p>{description}</p>
            </article>
          ))}
        </div>

        <div className="home-actions">
          <Link className="primary-action" href="/register">Get started <ArrowRight size={17} /></Link>
          <Link className="secondary-action" href="/login">Log in to your workspace</Link>
        </div>

        <p className="privacy-note"><LockKeyhole size={14} /> Nobody receives will content until the required release checks are complete.</p>
      </section>
    </main>
  );
}
