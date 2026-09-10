"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { ArrowRight, CircleUserRound, LogOut, ShieldCheck } from "lucide-react";

import { useAuth } from "@/lib/auth-context";

export default function DashboardPage() {
  const router = useRouter();
  const { user, signOut, busy } = useAuth();

  async function exit() {
    await signOut();
    router.push("/login");
  }

  return (
    <main className="min-h-screen bg-[#f4f0e7] text-[#18352d]">
      <header className="border-b border-[#dce4df] bg-[#fffdf8]">
        <div className="mx-auto flex max-w-7xl items-center justify-between px-5 py-5 sm:px-10 lg:px-16">
          <div className="flex items-center gap-3 text-sm font-bold text-[#123d35]"><span className="grid h-9 w-9 place-items-center rounded-full bg-[#123d35] text-white"><ShieldCheck size={17} /></span>WILLCHAIN SL</div>
          <button className="inline-flex items-center gap-2 rounded-lg border border-[#ccd8d2] bg-white px-3 py-2 text-sm font-bold text-[#25473d] hover:border-[#176b5b]" disabled={busy} onClick={exit}><LogOut size={16} />{busy ? "Signing out..." : "Sign out"}</button>
        </div>
      </header>
      <section className="mx-auto max-w-7xl px-5 py-12 sm:px-10 lg:px-16">
        <div className="flex flex-wrap items-end justify-between gap-5">
          <div><p className="text-xs font-bold uppercase text-[#aa7d34]">Protected workspace</p><h1 className="mt-3 text-4xl font-semibold sm:text-5xl">{user ? `Welcome, ${user.first_name}.` : "Authentication foundation"}</h1><p className="mt-3 text-[#60776e]">{user ? "Your workspace is scoped by your role and account state." : "Sign in to load your protected account profile."}</p></div>
          <Link className="inline-flex items-center gap-2 text-sm font-bold text-[#176b5b] hover:underline" href="/profile"><CircleUserRound size={18} /> Account profile <ArrowRight size={16} /></Link>
        </div>
        <div className="mt-10 grid gap-4 md:grid-cols-3">
          <div className="rounded-xl border border-[#dce4df] bg-[#fffdf8] p-6 shadow-sm"><p className="text-xs font-bold uppercase text-[#809189]">Role</p><p className="mt-3 text-xl font-semibold text-[#17372f]">{user?.role ?? "Not signed in"}</p></div>
          <div className="rounded-xl border border-[#dce4df] bg-[#fffdf8] p-6 shadow-sm"><p className="text-xs font-bold uppercase text-[#809189]">Account status</p><p className="mt-3 text-xl font-semibold text-[#176b5b]">{user?.account_status ?? "Unknown"}</p></div>
          <div className="rounded-xl border border-[#dce4df] bg-[#fffdf8] p-6 shadow-sm"><p className="text-xs font-bold uppercase text-[#809189]">Private access</p><p className="mt-3 leading-6 text-[#60776e]">Granted only by later resource workflows.</p></div>
        </div>
        <div className="mt-8 rounded-xl border border-[#c7a86b]/40 bg-[#fffaf0] p-5 text-sm leading-6 text-[#6d572c]">WillChain protects private will information through identity, relationship, explicit permission, and workflow state.</div>
      </section>
    </main>
  );
}
