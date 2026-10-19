import Link from "next/link";
import { ArrowUpRight, Check, LockKeyhole, ShieldCheck } from "lucide-react";
import type { InputHTMLAttributes, ReactNode } from "react";
import { ThemeToggle } from "@/components/common/theme-provider";

export function AuthShell({ children, eyebrow, title, description }: { children: ReactNode; eyebrow: string; title: string; description: string }) {
  return (
    <main className="auth-page min-h-screen lg:grid lg:grid-cols-[minmax(330px,0.84fr)_minmax(0,1.16fr)]">
      <section className="auth-aside relative hidden overflow-hidden px-8 py-8 lg:flex lg:flex-col lg:justify-between lg:px-10 xl:px-12">
        <Link href="/" className="auth-brand">
          <span className="auth-brand-icon"><ShieldCheck size={20} /></span>
          <span><strong>WillChain <i>SL</i></strong><small>SECURE DIGITAL WILL REGISTRY</small></span>
        </Link>
        <div className="auth-aside-copy relative">
          <p className="auth-eyebrow"><span /> PRIVATE BY DESIGN · SIERRA LEONE</p>
          <h1>A careful record for decisions that matter.</h1>
          <p className="auth-aside-description">A governed workspace for identity, protected documents, and accountable access across the life of a will.</p>
          <div className="auth-proof-panel">
            <span className="auth-proof-icon"><LockKeyhole size={19} /></span>
            <div><strong>Privacy is built into the workflow</strong><p>Access follows your account permissions and the status of each will.</p></div>
            <span className="auth-proof-status"><Check size={12} /> ACTIVE</span>
          </div>
        </div>
        <p className="auth-aside-footer"><span /> Human decisions remain human. <span>Freetown, Sierra Leone</span></p>
      </section>
      <section className="auth-main flex min-h-screen flex-col px-5 py-5 sm:px-9 lg:px-10 xl:px-14">
        <div className="auth-topbar"><Link href="/" className="auth-mobile-brand"><span className="auth-brand-icon"><ShieldCheck size={18} /></span><span>WillChain <i>SL</i></span></Link><div className="auth-top-actions"><ThemeToggle /><Link href="/" className="auth-overview-link">Public overview <ArrowUpRight size={14} /></Link></div></div>
        <div className="auth-card-wrap">
          <div className="auth-card">
            <div className="auth-card-heading"><p className="auth-card-eyebrow">{eyebrow}</p><span>HIGH ASSURANCE</span></div>
            <h2>{title}</h2>
            <p className="auth-card-description">{description}</p>
            {children}
          </div>
        </div>
        <footer className="auth-footer"><span>WillChain SL <i>·</i> Identity and access control</span><span>SIERRA LEONE <i>·</i> v1.0</span></footer>
      </section>
    </main>
  );
}

export function Field({ label, hint, ...props }: { label: string; hint?: string } & InputHTMLAttributes<HTMLInputElement>) {
  return <label className="theme-field grid gap-2 text-sm font-semibold"><span>{label}</span><input {...props} />{hint && <span className="theme-hint text-xs font-normal">{hint}</span>}</label>;
}
