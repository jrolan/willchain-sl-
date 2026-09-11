import Link from "next/link";
import { ArrowUpRight, Scale } from "lucide-react";
import type { InputHTMLAttributes, ReactNode } from "react";
import { ThemeToggle } from "@/components/common/theme-provider";

export function AuthShell({ children, eyebrow, title, description }: { children: ReactNode; eyebrow: string; title: string; description: string }) {
  return (
    <main className="auth-page min-h-screen lg:grid lg:grid-cols-[minmax(360px,0.8fr)_minmax(520px,1.2fr)]">
      <section className="auth-aside relative hidden overflow-hidden px-10 py-10 lg:flex lg:flex-col lg:justify-between xl:px-16">
        <div className="absolute -right-32 top-24 h-80 w-80 rounded-full border border-[#c7a86b]/30" />
        <div className="absolute -bottom-40 -left-32 h-[34rem] w-[34rem] rounded-full border border-[#c7a86b]/20" />
        <Link href="/" className="relative flex items-center gap-3 text-sm font-semibold tracking-[0.18em] text-[#f3dfae]">
          <span className="grid h-10 w-10 place-items-center rounded-full border border-[#c7a86b]/60"><Scale size={19} /></span>
          WILLCHAIN SL
        </Link>
        <div className="relative max-w-lg pb-10">
          <p className="mb-5 text-xs font-bold uppercase tracking-[0.25em] text-[#c7a86b]">Secure digital will registry</p>
          <h1 className="max-w-xl text-5xl font-semibold leading-[0.98] tracking-[-0.04em] xl:text-6xl">A careful record for decisions that matter.</h1>
          <p className="mt-7 max-w-md text-base leading-7 text-[#d9e4de]">A governed workspace for identity, protected documents, and accountable access across the life of a will.</p>
          <div className="mt-10 flex items-center gap-3 text-sm text-[#d9e4de]"><span className="h-px w-12 bg-[#c7a86b]" />Sierra Leone · Court-ready foundation</div>
        </div>
        <p className="relative text-xs text-[#a7c0b6]">Privacy by design. Human decisions remain human.</p>
      </section>
      <section className="auth-main flex min-h-screen flex-col px-5 py-6 sm:px-10 lg:px-16 lg:py-10 xl:px-24">
        <div className="flex items-center justify-between lg:justify-end"><Link href="/" className="flex items-center gap-2 text-xs font-bold tracking-[0.2em] lg:hidden"><Scale size={17} /> WILLCHAIN SL</Link><div className="flex items-center gap-4"><ThemeToggle /><Link href="/" className="hidden text-sm transition lg:flex lg:items-center lg:gap-1">Public overview <ArrowUpRight size={15} /></Link></div></div>
        <div className="my-auto w-full max-w-xl py-10"><p className="text-xs font-bold uppercase tracking-[0.2em] text-[#aa7d34]">{eyebrow}</p><h2 className="mt-4 text-4xl font-semibold leading-tight tracking-[-0.035em] text-[#17372f] sm:text-5xl">{title}</h2><p className="mt-4 max-w-lg text-[15px] leading-7 text-[#60776e]">{description}</p><div className="mt-9">{children}</div></div>
        <p className="auth-footer text-xs">WillChain SL · Identity and access control</p>
      </section>
    </main>
  );
}

export function Field({ label, hint, ...props }: { label: string; hint?: string } & InputHTMLAttributes<HTMLInputElement>) {
  return <label className="theme-field grid gap-2 text-sm font-semibold"><span>{label}</span><input {...props} />{hint && <span className="theme-hint text-xs font-normal">{hint}</span>}</label>;
}
