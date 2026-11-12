"use client";

import { useEffect, useState } from "react";
import { Blocks, RefreshCw } from "lucide-react";

import { DashboardShell } from "@/components/layout/dashboard-shell";
import { getIntegrityOperations, retryIntegrityOperation } from "@/services/integrity-service";
import { useAuth } from "@/lib/auth-context";
import type { IntegrityOperationsData } from "@/types/integrity";

export default function IntegrityOperationsPage() {
  const { user, initialLoading } = useAuth();
  const [operations, setOperations] = useState<IntegrityOperationsData>({ wills: [], documents: [] });
  const [loading, setLoading] = useState(true);
  const [busyReference, setBusyReference] = useState("");
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  async function loadOperations() {
    setLoading(true);
    setError("");
    try {
      const response = await getIntegrityOperations();
      setOperations(response.data);
    } catch (requestError: unknown) {
      setError(requestError instanceof Error ? requestError.message : "Unable to load integrity operations.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    if (user?.role !== "ADMINISTRATOR") return;
    let active = true;
    getIntegrityOperations()
      .then(({ data }) => {
        if (active) {
          setOperations(data);
          setError("");
        }
      })
      .catch((requestError: unknown) => {
        if (active) setError(requestError instanceof Error ? requestError.message : "Unable to load integrity operations.");
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [user?.role]);

  async function retry(reference: string) {
    setBusyReference(reference);
    setError("");
    setMessage("");
    try {
      await retryIntegrityOperation(reference);
      setMessage("Integrity operation queued for retry. The anchor worker will process it.");
      await loadOperations();
    } catch (requestError: unknown) {
      setError(requestError instanceof Error ? requestError.message : "Unable to retry this operation.");
    } finally {
      setBusyReference("");
    }
  }

  if (initialLoading || (user?.role === "ADMINISTRATOR" && loading)) {
    return <main className="min-h-screen p-10 text-[#60776e]">Loading integrity operations...</main>;
  }

  return (
    <DashboardShell>
      <main className="dashboard-page mx-auto max-w-7xl px-5 py-8 sm:px-8 lg:px-12">
        <header className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <p className="text-xs font-bold uppercase tracking-wider text-[#aa7d34]">Module 6</p>
            <h1 className="mt-2 flex items-center gap-2 text-3xl font-semibold text-[#17372f]"><Blocks size={26} /> Integrity operations</h1>
            <p className="mt-2 max-w-3xl text-sm leading-6 text-[#60776e]">
              Monitor queued and failed commitments without opening will content or private documents.
            </p>
          </div>
          <button type="button" onClick={() => void loadOperations()} disabled={loading} className="inline-flex items-center gap-2 rounded-lg border border-[#dce4df] bg-white px-3 py-2 text-sm font-semibold text-[#17372f] disabled:opacity-50">
            <RefreshCw size={15} /> Refresh
          </button>
        </header>

        {user?.role !== "ADMINISTRATOR" && (
          <p className="mt-6 rounded-lg border border-rose-200 bg-rose-50 p-4 text-sm text-rose-800" role="alert">
            This operational view is available only to administrators.
          </p>
        )}
        {error && <p className="mt-6 rounded-lg border border-rose-200 bg-rose-50 p-4 text-sm text-rose-800" role="alert">{error}</p>}
        {message && <p className="mt-6 rounded-lg border border-emerald-200 bg-emerald-50 p-4 text-sm text-emerald-800" role="status">{message}</p>}

        {user?.role === "ADMINISTRATOR" && !error && (
          <section className="mt-6 rounded-xl border border-[#dce4df] bg-white p-5 shadow-sm">
            <p className="text-sm leading-6 text-[#60776e]">
              Anchoring is processed by the backend outbox worker. In local development, run <code>python manage.py process_integrity_anchors --loop</code> from the backend directory.
            </p>
            {operations.wills.length === 0 && operations.documents.length === 0 ? (
              <p className="mt-5 rounded-lg bg-[#f7faf8] p-4 text-sm text-[#60776e]">No queued or failed integrity operations.</p>
            ) : (
              <div className="mt-5 space-y-3">
                {[...operations.wills.map((item) => ({ ...item, kind: "Will" })), ...operations.documents.map((item) => ({ ...item, kind: "Document" }))].map((item) => (
                  <article key={item.record_reference} className="rounded-lg border border-[#e5ebe7] p-4">
                    <div className="flex flex-wrap items-start justify-between gap-4">
                      <div className="min-w-0">
                        <div className="flex flex-wrap items-center gap-2">
                          <strong className="text-sm text-[#17372f]">{item.kind} #{item.will_id}</strong>
                          <span className={`rounded-full px-2 py-1 text-[11px] font-bold ${item.anchor_status === "FAILED" ? "bg-rose-50 text-rose-800" : "bg-amber-50 text-amber-800"}`}>{item.anchor_status}</span>
                        </div>
                        <p className="mt-2 break-all font-mono text-xs text-[#60776e]">{item.record_reference}</p>
                        <p className="mt-2 text-xs text-[#60776e]">{item.network} · chain {item.chain_id} · attempts {item.attempts}</p>
                        {item.transaction_hash && (
                          <p className="mt-1 break-all text-xs text-[#60776e]">
                            Transaction: {item.transaction_hash}
                            {item.chain_id === 11155111 && (
                              <a
                                href={`https://sepolia.etherscan.io/tx/${item.transaction_hash}`}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="ml-1 font-semibold text-[#176b5b] underline"
                              >
                                Sepolia Etherscan ↗
                              </a>
                            )}
                          </p>
                        )}
                        {item.last_error_code && <p className="mt-1 text-xs font-medium text-rose-700">Error: {item.last_error_code.replaceAll("_", " ")}</p>}
                      </div>
                      {item.anchor_status === "FAILED" && (
                        <button type="button" disabled={busyReference === item.record_reference} onClick={() => void retry(item.record_reference)} className="rounded-lg border border-[#176b5b] px-3 py-2 text-xs font-semibold text-[#176b5b] disabled:opacity-50">
                          {busyReference === item.record_reference ? "Queuing…" : "Retry"}
                        </button>
                      )}
                    </div>
                  </article>
                ))}
              </div>
            )}
          </section>
        )}
        <p className="mt-5 text-xs leading-5 text-[#60776e]">
          Blockchain anchoring records integrity commitments only. It does not expose will contents and does not determine legal validity.
        </p>
      </main>
    </DashboardShell>
  );
}
