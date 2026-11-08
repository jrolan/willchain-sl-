"use client";

import { useEffect, useState } from "react";
import { LockKeyhole, RefreshCw, ShieldCheck } from "lucide-react";
import { useRouter } from "next/navigation";

import { DashboardShell } from "@/components/layout/dashboard-shell";
import { useAuth } from "@/lib/auth-context";
import { getMyBeneficiaryAllocations } from "@/services/beneficiary-service";
import type { BeneficiaryAllocationAccess } from "@/types/beneficiaries";

export default function BeneficiaryAllocationsPage() {
  const router = useRouter();
  const { user, initialLoading } = useAuth();
  const [allocations, setAllocations] = useState<BeneficiaryAllocationAccess[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!initialLoading && !user) router.replace("/login");
  }, [initialLoading, user, router]);

  useEffect(() => {
    if (!user || initialLoading) return;
    let active = true;
    setLoading(true);
    getMyBeneficiaryAllocations()
      .then(({ data }) => {
        if (active) setAllocations(data);
      })
      .catch((requestError: unknown) => {
        if (active) setError(requestError instanceof Error ? requestError.message : "Unable to load released allocations.");
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [user, initialLoading]);

  return (
    <DashboardShell>
      <div className="space-y-7">
        <header className="flex flex-wrap items-end justify-between gap-4 border-b border-slate-200 pb-5 dark:border-slate-800">
          <div>
            <p className="text-sm font-semibold text-emerald-700 dark:text-emerald-400">Beneficiary workspace</p>
            <h1 className="mt-1 text-2xl font-bold text-slate-900 dark:text-white">My released allocations</h1>
          </div>
          <p className="flex items-center gap-2 text-sm text-slate-500"><ShieldCheck size={16} /> Private to your linked account</p>
        </header>

        {error && <div role="alert" className="border-l-4 border-rose-500 bg-rose-50 px-4 py-3 text-sm text-rose-800 dark:bg-rose-950/30 dark:text-rose-300">{error}</div>}

        {loading ? (
          <p className="py-10 text-sm text-slate-500">Loading authorized allocations...</p>
        ) : allocations.length === 0 ? (
          <div className="flex items-start gap-4 border-y border-slate-200 py-8 dark:border-slate-800">
            <LockKeyhole className="mt-1 text-slate-500" size={20} />
            <div>
              <h2 className="font-semibold text-slate-900 dark:text-white">No allocation is available yet</h2>
              <p className="mt-1 max-w-xl text-sm leading-6 text-slate-600 dark:text-slate-400">Only allocations that have been individually reviewed and explicitly authorized for release appear here.</p>
            </div>
          </div>
        ) : (
          <section aria-label="Released allocations" className="divide-y divide-slate-200 dark:divide-slate-800">
            {allocations.map((allocation) => (
              <article key={allocation.id} className="grid gap-3 py-6 sm:grid-cols-[minmax(0,1fr)_auto] sm:items-start">
                <div>
                  <p className="text-xs font-semibold uppercase text-slate-500">{allocation.will_title}</p>
                  <h2 className="mt-1 text-lg font-semibold text-slate-900 dark:text-white">
                    {allocation.allocation_type.replaceAll("_", " ")}
                  </h2>
                  <p className="mt-2 whitespace-pre-wrap text-sm leading-6 text-slate-700 dark:text-slate-300">{allocation.description || "No additional description."}</p>
                  {allocation.allocation_type === "FIXED_AMOUNT" && allocation.amount && (
                    <p className="mt-3 text-base font-semibold text-emerald-800 dark:text-emerald-300">{allocation.amount} {allocation.currency_code}</p>
                  )}
                  {allocation.allocation_type === "PERCENTAGE" && allocation.percentage && (
                    <p className="mt-3 text-base font-semibold text-emerald-800 dark:text-emerald-300">{allocation.percentage}%</p>
                  )}
                </div>
                <div className="text-xs text-slate-500 sm:text-right">
                  <span className="inline-flex items-center gap-1.5 font-semibold text-emerald-700 dark:text-emerald-400"><ShieldCheck size={14} /> Authorized</span>
                  <p className="mt-2">Released {new Date(allocation.released_at).toLocaleDateString()}</p>
                </div>
              </article>
            ))}
          </section>
        )}

        <button type="button" onClick={() => router.refresh()} className="inline-flex items-center gap-2 border border-slate-300 px-3 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50 dark:border-slate-700 dark:text-slate-200 dark:hover:bg-slate-900">
          <RefreshCw size={15} /> Refresh
        </button>
      </div>
    </DashboardShell>
  );
}
