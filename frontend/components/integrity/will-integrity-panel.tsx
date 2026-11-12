"use client";

import { useEffect, useState } from "react";
import { CheckCircle2, Clock3, Fingerprint, RefreshCw, ShieldAlert } from "lucide-react";

import {
  getLawyerWillIntegrity,
  getWillIntegrity,
  verifyLawyerWillIntegrity,
  verifyWillIntegrity,
} from "@/services/integrity-service";
import type { IntegrityAnchorStatus, WillIntegrityRecord, WillIntegrityStatus } from "@/types/integrity";

type Props = { willId: number; mode: "owner" | "lawyer"; refreshKey?: string };

const anchorLabels: Record<IntegrityAnchorStatus | "NOT_ANCHORED", string> = {
  QUEUED: "PENDING",
  SUBMITTING: "PENDING",
  SUBMITTED: "PENDING",
  CONFIRMED: "CONFIRMED",
  FAILED: "FAILED",
  NOT_ANCHORED: "NOT ANCHORED",
};

function badgeTone(status: IntegrityAnchorStatus | "NOT_ANCHORED") {
  if (status === "CONFIRMED") return "border-emerald-200 bg-emerald-50 text-emerald-800";
  if (status === "FAILED") return "border-rose-200 bg-rose-50 text-rose-800";
  if (status === "NOT_ANCHORED") return "border-slate-200 bg-slate-50 text-slate-700";
  return "border-amber-200 bg-amber-50 text-amber-800";
}

function getExplorerUrl(chainId: number, txHash: string): string | null {
  if (!txHash) return null;
  if (chainId === 11155111) return `https://sepolia.etherscan.io/tx/${txHash}`;
  if (chainId === 1) return `https://etherscan.io/tx/${txHash}`;
  return null;
}

export function WillIntegrityPanel({ willId, mode, refreshKey = "" }: Props) {
  const [ownerStatus, setOwnerStatus] = useState<WillIntegrityStatus | null>(null);
  const [lawyerRecord, setLawyerRecord] = useState<WillIntegrityRecord | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const record = mode === "owner" ? ownerStatus?.record ?? null : lawyerRecord;
  const finalized = mode === "lawyer" || ownerStatus?.will_status === "FINALIZED" || ownerStatus?.will_status === "ARCHIVED";

  useEffect(() => {
    let active = true;
    const handleError = (requestError: unknown) => {
      if (active) setError(requestError instanceof Error ? requestError.message : "Unable to load integrity evidence.");
    };
    const handleComplete = () => {
      if (active) setLoading(false);
    };
    if (mode === "owner") {
      getWillIntegrity(willId)
        .then(({ data }) => {
          if (active) {
            setOwnerStatus(data);
            setError("");
          }
        })
        .catch(handleError)
        .finally(handleComplete);
    } else {
      getLawyerWillIntegrity(willId)
        .then(({ data }) => {
          if (active) {
            setLawyerRecord(data);
            setError("");
          }
        })
        .catch(handleError)
        .finally(handleComplete);
    }
    return () => {
      active = false;
    };
  }, [mode, refreshKey, willId]);

  async function verify() {
    setBusy(true);
    setError("");
    try {
      const response = mode === "owner"
        ? await verifyWillIntegrity(willId)
        : await verifyLawyerWillIntegrity(willId);
      if (mode === "owner") {
        setOwnerStatus((current) => current ? { ...current, record: response.data.record } : current);
      } else {
        setLawyerRecord(response.data.record);
      }
    } catch (requestError: unknown) {
      setError(requestError instanceof Error ? requestError.message : "Unable to verify this will's integrity.");
    } finally {
      setBusy(false);
    }
  }

  const anchorStatus = record?.anchor_status ?? "NOT_ANCHORED";
  const verification = record?.latest_verification;

  return (
    <section className="rounded-xl border border-[#dce4df] bg-white p-5 shadow-sm" aria-label="Blockchain integrity">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="flex items-center gap-2 text-[#17372f]">
            <Fingerprint size={19} className="text-[#176b5b]" />
            <h2 className="text-base font-semibold">Blockchain integrity</h2>
          </div>
          <p className="mt-1 text-sm text-[#60776e]">
            {mode === "lawyer" ? "Read-only integrity evidence for this authorized case." : "A private snapshot is created when the will is finalized."}
          </p>
        </div>
        <span className={`rounded-full border px-3 py-1 text-xs font-bold ${badgeTone(anchorStatus)}`}>
          {anchorLabels[anchorStatus]}
        </span>
      </div>

      {loading ? <p className="mt-4 text-sm text-[#60776e]">Loading integrity status…</p> : (
        <div className="mt-4 grid gap-3 text-sm sm:grid-cols-2">
          <p><span className="font-semibold text-[#17372f]">Will status:</span> {ownerStatus?.will_status ?? (record ? "FINALIZED" : "Not finalized")}</p>
          <p><span className="font-semibold text-[#17372f]">Network:</span> {record?.network ?? "Not registered"}</p>
          <p><span className="font-semibold text-[#17372f]">Version:</span> {record?.finalized_version ?? "—"}</p>
          <p><span className="font-semibold text-[#17372f]">Confirmations:</span> {record?.confirmations ?? 0}</p>
          <p><span className="font-semibold text-[#17372f]">Block:</span> {record?.block_number ?? "Not confirmed"}</p>
          {record?.transaction_hash && (
            <p className="sm:col-span-2">
              <span className="font-semibold text-[#17372f]">Transaction:</span>{" "}
              <code className="break-all text-xs">{record.transaction_hash}</code>
            </p>
          )}
          {record?.last_error_code && (
            <p className="sm:col-span-2 text-amber-800">
              <span className="font-semibold">Status detail:</span> {record.last_error_code.replaceAll("_", " ")}
            </p>
          )}
          {verification && (
            <p className="sm:col-span-2 flex items-center gap-2">
              {verification.result === "MATCH" ? <CheckCircle2 size={16} className="text-emerald-700" /> : verification.result === "MISMATCH" ? <ShieldAlert size={16} className="text-rose-700" /> : <Clock3 size={16} className="text-amber-700" />}
              <span>
                Last verification: <strong>{verification.result === "MATCH" ? "VERIFICATION MATCH" : verification.result === "MISMATCH" ? "VERIFICATION MISMATCH" : verification.result}</strong>
                {" · "}{new Date(verification.checked_at).toLocaleString()}
              </span>
            </p>
          )}
          {mode === "owner" && record?.document_records.map((document) => (
            <p className="sm:col-span-2" key={document.record_reference}>
              Supporting document v{document.document_version}: <strong>{anchorLabels[document.anchor_status]}</strong>
              {document.transaction_hash && <> · <code className="break-all text-xs">{document.transaction_hash}</code></>}
            </p>
          ))}
          {mode === "owner" && verification?.details.documents?.map((document) => (
            <p className="sm:col-span-2" key={`document-check-${document.document_id}`}>
              Document #{document.document_id}: <strong>VERIFICATION {document.result}</strong>
            </p>
          ))}
        </div>
      )}

      {error && <p className="mt-3 text-sm text-rose-700" role="alert">{error}</p>}
      <div className="mt-4 flex flex-wrap items-center gap-3">
        <button
          type="button"
          onClick={verify}
          disabled={loading || busy || !finalized || !record}
          className="inline-flex items-center gap-2 rounded-lg bg-[#176b5b] px-3 py-2 text-sm font-semibold text-white disabled:opacity-50"
        >
          <RefreshCw size={15} className={busy ? "animate-spin" : ""} />
          {busy ? "Verifying…" : "Verify integrity"}
        </button>
        {record?.transaction_hash && (() => {
          const explorerUrl = getExplorerUrl(record.chain_id, record.transaction_hash);
          return explorerUrl ? (
            <a
              href={explorerUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1 text-xs font-semibold text-[#176b5b] underline hover:text-[#124d41]"
            >
              View on block explorer ↗
            </a>
          ) : (
            <span className="text-xs text-[#60776e]">No trusted explorer is configured for this local network.</span>
          );
        })()}
      </div>
      <p className="mt-3 text-xs leading-5 text-[#60776e]">
        Blockchain checks whether the committed snapshot or file has changed. It does not establish legal validity, capacity, authorship, or truth.
      </p>
    </section>
  );
}
