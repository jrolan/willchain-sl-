"use client";

import { useEffect, useState } from "react";
import {
  AlertCircle,
  CheckCircle2,
  Clock,
  Download,
  FileCheck,
  FileText,
  Gavel,
  Lock,
  PlusCircle,
  RefreshCw,
  Send,
  Upload,
  UserCheck,
  XCircle,
} from "lucide-react";

import { DashboardShell } from "@/components/layout/dashboard-shell";
import { useAuth } from "@/lib/auth-context";
import {
  assessEligibility,
  authorizeDisclosure,
  beginReview,
  createCase,
  downloadDisclosure,
  downloadEvidence,
  getCases,
  recordDecision,
  requestInformation,
  resubmitCase,
  revokeDisclosure,
  setEvidenceSufficiency,
  submitCase,
  uploadEvidence,
  withdrawCase,
} from "@/services/verification-service";
import type {
  CaseEvidence,
  CaseStatus,
  CaseType,
  EvidenceType,
  SubmissionType,
  VerificationCase,
} from "@/types/verification";

const PRE_DEATH_DISCLAIMER =
  "This is a pre-death legal review. No approval from this review affects the legal validity of your will or grants any person access to your will's contents. A pre-death review is for your own preparation and awareness only. You must explicitly authorise any disclosure of a will copy to your assigned verifier.";

const STATUS_BADGE_CLASSES: Record<CaseStatus, string> = {
  PENDING_ELIGIBILITY: "bg-amber-100 text-amber-800 dark:bg-amber-950 dark:text-amber-300",
  OPEN: "bg-blue-100 text-blue-800 dark:bg-blue-950 dark:text-blue-300",
  INFORMATION_REQUIRED: "bg-purple-100 text-purple-800 dark:bg-purple-950 dark:text-purple-300",
  UNDER_REVIEW: "bg-indigo-100 text-indigo-800 dark:bg-indigo-950 dark:text-indigo-300",
  APPROVED: "bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300",
  REJECTED: "bg-rose-100 text-rose-800 dark:bg-rose-950 dark:text-rose-300",
  WITHDRAWN: "bg-slate-100 text-slate-800 dark:bg-slate-900 dark:text-slate-300",
};

export default function VerificationDashboardPage() {
  const { user } = useAuth();
  const [cases, setCases] = useState<VerificationCase[]>([]);
  const [selectedCase, setSelectedCase] = useState<VerificationCase | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  // Form states for creating a new case
  const [caseType, setCaseType] = useState<CaseType>("PRE_DEATH_REVIEW");
  const [submissionType, setSubmissionType] = useState<SubmissionType>("OWNER_INITIATED");
  const [willId, setWillId] = useState<string>("");
  const [claimedBasis, setClaimedBasis] = useState<string>("");

  // Form states for evidence upload
  const [evidenceType, setEvidenceType] = useState<EvidenceType>("IDENTITY_DOCUMENT");
  const [evidenceDescription, setEvidenceDescription] = useState("");
  const [evidenceFile, setEvidenceFile] = useState<File | null>(null);

  // Form states for lawyer review actions
  const [requestNotes, setRequestNotes] = useState("");
  const [decisionNotes, setDecisionNotes] = useState("");
  const [eligibilityNotes, setEligibilityNotes] = useState("");

  // Will copy disclosure file
  const [disclosureFile, setDisclosureFile] = useState<File | null>(null);

  const fetchCases = async () => {
    try {
      setLoading(true);
      setError(null);
      const res = await getCases();
      setCases(res.data);
      if (selectedCase) {
        const refreshed = res.data.find((c) => c.id === selectedCase.id);
        if (refreshed) setSelectedCase(refreshed);
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to load verification cases.";
      setError(msg);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchCases();
  }, []);

  const handleCreateCase = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    setSuccessMessage(null);

    try {
      const payload = {
        case_type: caseType,
        submission_type: submissionType,
        will: willId ? Number(willId) : null,
        claimed_executor_basis: claimedBasis,
      };
      const res = await createCase(payload);
      setSuccessMessage(res.message || "Verification case created.");
      await fetchCases();
      setSelectedCase(res.data);
      setWillId("");
      setClaimedBasis("");
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to create verification case.";
      setError(msg);
    } finally {
      setBusy(false);
    }
  };

  const handleUploadEvidence = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedCase || !evidenceFile) return;

    setBusy(true);
    setError(null);
    setSuccessMessage(null);

    try {
      const res = await uploadEvidence(
        selectedCase.id,
        evidenceFile,
        evidenceType,
        evidenceDescription,
      );
      setSuccessMessage(res.message || "Evidence file uploaded.");
      setEvidenceFile(null);
      setEvidenceDescription("");
      await fetchCases();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to upload evidence.";
      setError(msg);
    } finally {
      setBusy(false);
    }
  };

  const handleDownloadEvidence = async (evidence: CaseEvidence) => {
    if (!selectedCase) return;
    try {
      const blob = await downloadEvidence(selectedCase.id, evidence.id);
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = evidence.original_filename;
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to download evidence.";
      setError(msg);
    }
  };

  const handleAuthorizeDisclosure = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedCase || !disclosureFile) return;

    setBusy(true);
    setError(null);
    setSuccessMessage(null);

    try {
      const res = await authorizeDisclosure(selectedCase.id, disclosureFile);
      setSuccessMessage(res.message || "Will disclosure authorized.");
      setDisclosureFile(null);
      await fetchCases();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to authorize disclosure.";
      setError(msg);
    } finally {
      setBusy(false);
    }
  };

  const handleRevokeDisclosure = async () => {
    if (!selectedCase) return;
    setBusy(true);
    setError(null);
    setSuccessMessage(null);

    try {
      const res = await revokeDisclosure(selectedCase.id);
      setSuccessMessage(res.message || "Will disclosure revoked.");
      await fetchCases();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to revoke disclosure.";
      setError(msg);
    } finally {
      setBusy(false);
    }
  };

  const handleDownloadDisclosure = async () => {
    if (!selectedCase) return;
    try {
      const blob = await downloadDisclosure(selectedCase.id);
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = selectedCase.disclosure_authorization?.original_filename || "will_copy.pdf";
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to download disclosed will copy.";
      setError(msg);
    }
  };

  const handleSubmitCase = async () => {
    if (!selectedCase) return;
    setBusy(true);
    setError(null);
    setSuccessMessage(null);

    try {
      const res = await submitCase(selectedCase.id);
      setSuccessMessage(res.message || "Case submitted for review.");
      await fetchCases();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to submit case.";
      setError(msg);
    } finally {
      setBusy(false);
    }
  };

  const handleResubmit = async () => {
    if (!selectedCase) return;
    setBusy(true);
    setError(null);
    setSuccessMessage(null);

    try {
      const res = await resubmitCase(selectedCase.id);
      setSuccessMessage(res.message || "Additional information submitted.");
      await fetchCases();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to resubmit case.";
      setError(msg);
    } finally {
      setBusy(false);
    }
  };

  const handleWithdraw = async () => {
    if (!selectedCase) return;
    setBusy(true);
    setError(null);
    setSuccessMessage(null);

    try {
      const res = await withdrawCase(selectedCase.id);
      setSuccessMessage(res.message || "Case withdrawn.");
      await fetchCases();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to withdraw case.";
      setError(msg);
    } finally {
      setBusy(false);
    }
  };

  const handleAssessEligibility = async (eligible: boolean) => {
    if (!selectedCase) return;
    setBusy(true);
    setError(null);
    setSuccessMessage(null);

    try {
      const res = await assessEligibility(selectedCase.id, eligible, eligibilityNotes);
      setSuccessMessage(res.message || "Eligibility assessment recorded.");
      setEligibilityNotes("");
      await fetchCases();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to assess eligibility.";
      setError(msg);
    } finally {
      setBusy(false);
    }
  };

  const handleBeginReview = async () => {
    if (!selectedCase) return;
    setBusy(true);
    setError(null);
    setSuccessMessage(null);

    try {
      const res = await beginReview(selectedCase.id);
      setSuccessMessage(res.message || "Review started.");
      await fetchCases();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to begin review.";
      setError(msg);
    } finally {
      setBusy(false);
    }
  };

  const handleRequestInformation = async () => {
    if (!selectedCase || !requestNotes.trim()) return;
    setBusy(true);
    setError(null);
    setSuccessMessage(null);

    try {
      const res = await requestInformation(selectedCase.id, requestNotes);
      setSuccessMessage(res.message || "Information requested.");
      setRequestNotes("");
      await fetchCases();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to request information.";
      setError(msg);
    } finally {
      setBusy(false);
    }
  };

  const handleDecision = async (decision: "APPROVED" | "REJECTED") => {
    if (!selectedCase) return;
    setBusy(true);
    setError(null);
    setSuccessMessage(null);

    try {
      const res = await recordDecision(selectedCase.id, decision, decisionNotes);
      setSuccessMessage(res.message || `Decision recorded as ${decision}.`);
      setDecisionNotes("");
      await fetchCases();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to record decision.";
      setError(msg);
    } finally {
      setBusy(false);
    }
  };

  const handleSufficiencyToggle = async (evidence: CaseEvidence) => {
    if (!selectedCase) return;
    try {
      await setEvidenceSufficiency(selectedCase.id, evidence.id, !evidence.sufficiency_flag);
      await fetchCases();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to update evidence sufficiency.";
      setError(msg);
    }
  };

  const isLawyer = user?.role === "LAWYER_VERIFIER";

  return (
    <DashboardShell>
      <div className="space-y-6">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-slate-900 dark:text-white">
            Verification & Legal Workflow
          </h1>
          <p className="mt-1 text-sm text-slate-600 dark:text-slate-400">
            Submit wills or supporting documents for pre-death review or post-death verification.
          </p>
        </div>

        {error && (
          <div role="alert" className="flex items-center gap-2 rounded-lg bg-rose-50 p-4 text-sm text-rose-800 dark:bg-rose-950/50 dark:text-rose-300">
            <AlertCircle className="h-5 w-5 shrink-0" />
            <span>{error}</span>
          </div>
        )}

        {successMessage && (
          <div role="status" className="flex items-center gap-2 rounded-lg bg-emerald-50 p-4 text-sm text-emerald-800 dark:bg-emerald-950/50 dark:text-emerald-300">
            <CheckCircle2 className="h-5 w-5 shrink-0" />
            <span>{successMessage}</span>
          </div>
        )}

        {/* Create Case Form (for non-lawyers or anyone initiating) */}
        {!isLawyer && (
          <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm dark:border-slate-800 dark:bg-slate-900">
            <h2 className="text-lg font-semibold text-slate-900 dark:text-white">
              Initiate a Verification Case
            </h2>

            {caseType === "PRE_DEATH_REVIEW" && (
              <div className="my-4 rounded-lg bg-amber-50 p-4 text-sm text-amber-900 dark:bg-amber-950/40 dark:text-amber-200">
                <div className="flex gap-2">
                  <AlertCircle className="h-5 w-5 shrink-0 text-amber-600 dark:text-amber-400" />
                  <p className="font-medium">{PRE_DEATH_DISCLAIMER}</p>
                </div>
              </div>
            )}

            <form onSubmit={handleCreateCase} className="mt-4 grid gap-4 sm:grid-cols-2">
              <div>
                <label className="block text-sm font-medium text-slate-700 dark:text-slate-300">
                  Case Type
                </label>
                <select
                  value={caseType}
                  onChange={(e) => {
                    const ct = e.target.value as CaseType;
                    setCaseType(ct);
                    if (ct === "PRE_DEATH_REVIEW") {
                      setSubmissionType("OWNER_INITIATED");
                    } else {
                      setSubmissionType("BENEFICIARY_CLAIM");
                    }
                  }}
                  className="mt-1 block w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-sm shadow-sm dark:border-slate-700 dark:bg-slate-800 dark:text-white"
                >
                  <option value="PRE_DEATH_REVIEW">Pre-Death Legal Review</option>
                  <option value="POST_DEATH_VERIFY">Post-Death Verification</option>
                </select>
              </div>

              <div>
                <label className="block text-sm font-medium text-slate-700 dark:text-slate-300">
                  Submission Type
                </label>
                <select
                  value={submissionType}
                  onChange={(e) => setSubmissionType(e.target.value as SubmissionType)}
                  className="mt-1 block w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-sm shadow-sm dark:border-slate-700 dark:bg-slate-800 dark:text-white"
                >
                  {caseType === "PRE_DEATH_REVIEW" ? (
                    <option value="OWNER_INITIATED">Owner Initiated</option>
                  ) : (
                    <>
                      <option value="BENEFICIARY_CLAIM">Beneficiary Claim</option>
                      <option value="CLAIMED_EXECUTOR">Claimed Executor</option>
                    </>
                  )}
                </select>
              </div>

              <div>
                <label className="block text-sm font-medium text-slate-700 dark:text-slate-300">
                  Will ID {caseType === "PRE_DEATH_REVIEW" && "(Required)"}
                </label>
                <input
                  type="number"
                  value={willId}
                  onChange={(e) => setWillId(e.target.value)}
                  placeholder="e.g. 1"
                  required={caseType === "PRE_DEATH_REVIEW"}
                  className="mt-1 block w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-sm shadow-sm dark:border-slate-700 dark:bg-slate-800 dark:text-white"
                />
              </div>

              {submissionType === "CLAIMED_EXECUTOR" && (
                <div className="sm:col-span-2">
                  <label className="block text-sm font-medium text-slate-700 dark:text-slate-300">
                    Claimed Executor Basis (Max 512 chars)
                  </label>
                  <textarea
                    value={claimedBasis}
                    onChange={(e) => setClaimedBasis(e.target.value)}
                    maxLength={512}
                    placeholder="Describe the basis of executor authority..."
                    className="mt-1 block w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-sm shadow-sm dark:border-slate-700 dark:bg-slate-800 dark:text-white"
                    rows={2}
                  />
                </div>
              )}

              <div className="sm:col-span-2">
                <button
                  type="submit"
                  disabled={busy}
                  className="inline-flex items-center gap-2 rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white shadow hover:bg-blue-700 disabled:opacity-50"
                >
                  <PlusCircle className="h-4 w-4" />
                  {busy ? "Creating..." : "Create Case"}
                </button>
              </div>
            </form>
          </div>
        )}

        {/* Case List & Detail Grid */}
        <div className="grid gap-6 lg:grid-cols-3">
          {/* List Column */}
          <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm dark:border-slate-800 dark:bg-slate-900 lg:col-span-1">
            <div className="flex items-center justify-between pb-3">
              <h2 className="text-base font-semibold text-slate-900 dark:text-white">
                Verification Cases
              </h2>
              <button
                onClick={fetchCases}
                disabled={loading}
                className="rounded p-1 text-slate-500 hover:bg-slate-100 dark:hover:bg-slate-800"
              >
                <RefreshCw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} />
              </button>
            </div>

            {loading ? (
              <p className="py-6 text-center text-sm text-slate-500">Loading cases...</p>
            ) : cases.length === 0 ? (
              <p className="py-6 text-center text-sm text-slate-500">No verification cases found.</p>
            ) : (
              <ul className="space-y-2">
                {cases.map((c) => (
                  <li key={c.id}>
                    <button
                      onClick={() => setSelectedCase(c)}
                      className={`w-full rounded-lg p-3 text-left transition ${
                        selectedCase?.id === c.id
                          ? "bg-blue-50 border border-blue-200 dark:bg-blue-950/40 dark:border-blue-900"
                          : "hover:bg-slate-50 dark:hover:bg-slate-800/60"
                      }`}
                    >
                      <div className="flex items-center justify-between">
                        <span className="text-sm font-medium text-slate-900 dark:text-white">
                          Case #{c.id}
                        </span>
                        <span
                          className={`rounded px-2 py-0.5 text-xs font-medium ${
                            STATUS_BADGE_CLASSES[c.status]
                          }`}
                        >
                          {c.status.replace("_", " ")}
                        </span>
                      </div>
                      <div className="mt-1 flex items-center justify-between text-xs text-slate-500">
                        <span>{c.case_type}</span>
                        <span>Will #{c.will || "N/A"}</span>
                      </div>
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </div>

          {/* Details Column */}
          <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm dark:border-slate-800 dark:bg-slate-900 lg:col-span-2">
            {selectedCase ? (
              <div className="space-y-6">
                <div className="flex flex-wrap items-center justify-between gap-4 border-b border-slate-200 pb-4 dark:border-slate-800">
                  <div>
                    <h2 className="text-xl font-bold text-slate-900 dark:text-white">
                      Case #{selectedCase.id}: {selectedCase.case_type}
                    </h2>
                    <p className="mt-1 text-xs text-slate-500">
                      Created {new Date(selectedCase.created_at).toLocaleString()} • Will ID: #{selectedCase.will || "None"}
                    </p>
                  </div>
                  <span
                    className={`rounded-md px-3 py-1 text-sm font-semibold ${
                      STATUS_BADGE_CLASSES[selectedCase.status]
                    }`}
                  >
                    {selectedCase.status.replace("_", " ")}
                  </span>
                </div>

                {/* Assigned Verifier Information (OD-5 Privacy: display name and assigned_at only) */}
                <div className="rounded-lg bg-slate-50 p-4 dark:bg-slate-800/50">
                  <h3 className="text-sm font-semibold text-slate-900 dark:text-white">
                    Assigned Legal Verifier
                  </h3>
                  {selectedCase.assigned_lawyer_display ? (
                    <div className="mt-2 text-sm text-slate-600 dark:text-slate-300">
                      <p className="font-medium text-slate-900 dark:text-white">
                        {selectedCase.assigned_lawyer_display.display_name}
                      </p>
                      <p className="text-xs text-slate-500">
                        Assigned on:{" "}
                        {selectedCase.assigned_lawyer_display.assigned_at
                          ? new Date(selectedCase.assigned_lawyer_display.assigned_at).toLocaleString()
                          : "Pending"}
                      </p>
                    </div>
                  ) : (
                    <p className="mt-1 text-xs text-slate-500">
                      No legal verifier has been assigned to this case yet.
                    </p>
                  )}
                </div>

                {/* Claimed Executor Basis */}
                {selectedCase.submission_type === "CLAIMED_EXECUTOR" && (
                  <div className="rounded-lg border border-amber-200 bg-amber-50/50 p-4 dark:border-amber-900 dark:bg-amber-950/20">
                    <h3 className="text-sm font-semibold text-amber-900 dark:text-amber-200">
                      Claimed Executor Basis
                    </h3>
                    <p className="mt-1 text-sm text-amber-800 dark:text-amber-300">
                      {selectedCase.claimed_executor_basis || "No basis provided."}
                    </p>
                  </div>
                )}

                {/* Notes and Request Info */}
                {selectedCase.information_request_notes && (
                  <div className="rounded-lg border border-purple-200 bg-purple-50 p-4 dark:border-purple-900 dark:bg-purple-950/30">
                    <h3 className="text-sm font-semibold text-purple-900 dark:text-purple-200">
                      Information Requested by Verifier
                    </h3>
                    <p className="mt-1 text-sm text-purple-800 dark:text-purple-300">
                      {selectedCase.information_request_notes}
                    </p>
                  </div>
                )}

                {selectedCase.decision_notes && (
                  <div className="rounded-lg bg-slate-50 p-4 dark:bg-slate-800/40">
                    <h3 className="text-sm font-semibold text-slate-900 dark:text-white">
                      Verifier Decision Notes
                    </h3>
                    <p className="mt-1 text-sm text-slate-600 dark:text-slate-300">
                      {selectedCase.decision_notes}
                    </p>
                  </div>
                )}

                {/* Evidence Files (OD-3) */}
                <div>
                  <h3 className="text-sm font-semibold text-slate-900 dark:text-white">
                    Supporting Evidence ({selectedCase.evidence.length})
                  </h3>
                  {selectedCase.evidence.length === 0 ? (
                    <p className="mt-1 text-xs text-slate-500">No evidence uploaded yet.</p>
                  ) : (
                    <ul className="mt-2 divide-y divide-slate-100 rounded-md border border-slate-200 dark:divide-slate-800 dark:border-slate-800">
                      {selectedCase.evidence.map((ev) => (
                        <li key={ev.id} className="flex items-center justify-between p-3 text-sm">
                          <div>
                            <span className="font-medium text-slate-900 dark:text-white">
                              {ev.original_filename}
                            </span>
                            <span className="ml-2 rounded bg-slate-100 px-2 py-0.5 text-xs text-slate-600 dark:bg-slate-800 dark:text-slate-300">
                              {ev.evidence_type}
                            </span>
                            {ev.sufficiency_flag && (
                              <span className="ml-2 rounded bg-emerald-100 px-2 py-0.5 text-xs text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300">
                                Verified Sufficient
                              </span>
                            )}
                            {ev.description && (
                              <p className="text-xs text-slate-500">{ev.description}</p>
                            )}
                          </div>
                          <div className="flex items-center gap-2">
                            {isLawyer && (
                              <button
                                onClick={() => handleSufficiencyToggle(ev)}
                                className={`rounded px-2 py-1 text-xs font-medium ${
                                  ev.sufficiency_flag
                                    ? "bg-slate-200 text-slate-700 hover:bg-slate-300 dark:bg-slate-700 dark:text-slate-200"
                                    : "bg-emerald-600 text-white hover:bg-emerald-700"
                                }`}
                              >
                                {ev.sufficiency_flag ? "Revoke Sufficiency" : "Mark Sufficient"}
                              </button>
                            )}
                            <button
                              onClick={() => handleDownloadEvidence(ev)}
                              className="rounded p-1.5 text-slate-500 hover:bg-slate-100 hover:text-slate-700 dark:hover:bg-slate-800"
                            >
                              <Download className="h-4 w-4" />
                            </button>
                          </div>
                        </li>
                      ))}
                    </ul>
                  )}

                  {/* Upload Evidence Form (if case not terminal) */}
                  {!["APPROVED", "REJECTED", "WITHDRAWN"].includes(selectedCase.status) && (
                    <form onSubmit={handleUploadEvidence} className="mt-4 rounded-lg border border-slate-200 p-4 dark:border-slate-800">
                      <h4 className="text-xs font-semibold uppercase tracking-wider text-slate-500">
                        Upload Evidence File
                      </h4>
                      <div className="mt-3 grid gap-3 sm:grid-cols-2">
                        <div>
                          <label className="block text-xs font-medium text-slate-700 dark:text-slate-300">
                            Type
                          </label>
                          <select
                            value={evidenceType}
                            onChange={(e) => setEvidenceType(e.target.value as EvidenceType)}
                            className="mt-1 block w-full rounded-md border border-slate-300 px-2.5 py-1.5 text-xs shadow-sm dark:border-slate-700 dark:bg-slate-800 dark:text-white"
                          >
                            <option value="IDENTITY_DOCUMENT">Identity Document</option>
                            <option value="DEATH_CERTIFICATE">Death Certificate</option>
                            <option value="PROBATE_DOCUMENT">Probate Document</option>
                            <option value="RELATIONSHIP_PROOF">Relationship Proof</option>
                            <option value="OTHER">Other Evidence</option>
                          </select>
                        </div>
                        <div>
                          <label className="block text-xs font-medium text-slate-700 dark:text-slate-300">
                            Description
                          </label>
                          <input
                            type="text"
                            value={evidenceDescription}
                            onChange={(e) => setEvidenceDescription(e.target.value)}
                            placeholder="Brief description..."
                            className="mt-1 block w-full rounded-md border border-slate-300 px-2.5 py-1.5 text-xs shadow-sm dark:border-slate-700 dark:bg-slate-800 dark:text-white"
                          />
                        </div>
                        <div className="sm:col-span-2">
                          <input
                            type="file"
                            onChange={(e) => setEvidenceFile(e.target.files?.[0] || null)}
                            required
                            className="block w-full text-xs text-slate-500 file:mr-2 file:rounded-md file:border-0 file:bg-slate-100 file:px-3 file:py-1.5 file:text-xs file:font-semibold file:text-slate-700 hover:file:bg-slate-200 dark:file:bg-slate-800 dark:file:text-slate-300"
                          />
                        </div>
                        <div className="sm:col-span-2">
                          <button
                            type="submit"
                            disabled={busy || !evidenceFile}
                            className="inline-flex items-center gap-1.5 rounded-md bg-blue-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-blue-700 disabled:opacity-50"
                          >
                            <Upload className="h-3.5 w-3.5" />
                            {busy ? "Uploading..." : "Upload File"}
                          </button>
                        </div>
                      </div>
                    </form>
                  )}
                </div>

                {/* Will Disclosure Section (OD-2: Pre-death only) */}
                {selectedCase.case_type === "PRE_DEATH_REVIEW" && (
                  <div className="rounded-lg border border-slate-200 p-4 dark:border-slate-800">
                    <h3 className="text-sm font-semibold text-slate-900 dark:text-white">
                      Will Copy Disclosure Authorization
                    </h3>
                    <p className="mt-1 text-xs text-slate-500">
                      Disclosing a will copy allows your assigned legal verifier to inspect the document text. You may revoke disclosure at any time.
                    </p>

                    {selectedCase.disclosure_authorization?.is_active ? (
                      <div className="mt-3 flex items-center justify-between rounded-md bg-emerald-50 p-3 text-xs text-emerald-800 dark:bg-emerald-950/40 dark:text-emerald-300">
                        <div className="flex items-center gap-2">
                          <FileCheck className="h-4 w-4" />
                          <span>
                            Disclosure Active: {selectedCase.disclosure_authorization.original_filename}
                          </span>
                        </div>
                        <div className="flex items-center gap-2">
                          {isLawyer && (
                            <button
                              onClick={handleDownloadDisclosure}
                              className="rounded bg-emerald-600 px-2.5 py-1 text-xs font-medium text-white hover:bg-emerald-700"
                            >
                              Download Copy
                            </button>
                          )}
                          {!isLawyer && (
                            <button
                              onClick={handleRevokeDisclosure}
                              disabled={busy}
                              className="rounded bg-rose-600 px-2.5 py-1 text-xs font-medium text-white hover:bg-rose-700 disabled:opacity-50"
                            >
                              Revoke Disclosure
                            </button>
                          )}
                        </div>
                      </div>
                    ) : (
                      <form onSubmit={handleAuthorizeDisclosure} className="mt-3 flex items-center gap-3">
                        <input
                          type="file"
                          onChange={(e) => setDisclosureFile(e.target.files?.[0] || null)}
                          required
                          className="block text-xs text-slate-500 file:mr-2 file:rounded-md file:border-0 file:bg-slate-100 file:px-3 file:py-1.5 file:text-xs file:font-semibold file:text-slate-700 hover:file:bg-slate-200 dark:file:bg-slate-800 dark:file:text-slate-300"
                        />
                        <button
                          type="submit"
                          disabled={busy || !disclosureFile}
                          className="rounded-md bg-indigo-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-indigo-700 disabled:opacity-50"
                        >
                          Authorize Disclosure
                        </button>
                      </form>
                    )}
                  </div>
                )}

                {/* Workflow Actions */}
                <div className="border-t border-slate-200 pt-4 dark:border-slate-800">
                  <h3 className="text-sm font-semibold text-slate-900 dark:text-white">
                    Workflow Actions
                  </h3>
                  <div className="mt-3 flex flex-wrap gap-2">
                    {/* Initiator Submit */}
                    {selectedCase.status === "OPEN" && !isLawyer && (
                      <button
                        onClick={handleSubmitCase}
                        disabled={busy}
                        className="inline-flex items-center gap-1.5 rounded-md bg-blue-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-blue-700 disabled:opacity-50"
                      >
                        <Send className="h-3.5 w-3.5" />
                        Submit for Legal Review
                      </button>
                    )}

                    {/* Resubmit when INFORMATION_REQUIRED */}
                    {selectedCase.status === "INFORMATION_REQUIRED" && !isLawyer && (
                      <button
                        onClick={handleResubmit}
                        disabled={busy}
                        className="inline-flex items-center gap-1.5 rounded-md bg-purple-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-purple-700 disabled:opacity-50"
                      >
                        <Send className="h-3.5 w-3.5" />
                        Resubmit Information
                      </button>
                    )}

                    {/* Lawyer Actions */}
                    {isLawyer && selectedCase.status === "PENDING_ELIGIBILITY" && (
                      <div className="w-full space-y-2 rounded-lg bg-slate-50 p-3 dark:bg-slate-800/60">
                        <input
                          type="text"
                          value={eligibilityNotes}
                          onChange={(e) => setEligibilityNotes(e.target.value)}
                          placeholder="Eligibility assessment notes..."
                          className="w-full rounded border border-slate-300 p-1.5 text-xs dark:border-slate-700 dark:bg-slate-900"
                        />
                        <div className="flex gap-2">
                          <button
                            onClick={() => handleAssessEligibility(true)}
                            disabled={busy}
                            className="rounded bg-emerald-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-emerald-700"
                          >
                            Approve Executor Authority
                          </button>
                          <button
                            onClick={() => handleAssessEligibility(false)}
                            disabled={busy}
                            className="rounded bg-rose-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-rose-700"
                          >
                            Reject Executor Claim
                          </button>
                        </div>
                      </div>
                    )}

                    {isLawyer && selectedCase.status === "OPEN" && (
                      <button
                        onClick={handleBeginReview}
                        disabled={busy}
                        className="rounded bg-indigo-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-indigo-700"
                      >
                        Begin Legal Review
                      </button>
                    )}

                    {isLawyer && ["OPEN", "UNDER_REVIEW"].includes(selectedCase.status) && (
                      <div className="w-full space-y-2 rounded-lg bg-slate-50 p-3 dark:bg-slate-800/60">
                        <textarea
                          value={requestNotes}
                          onChange={(e) => setRequestNotes(e.target.value)}
                          placeholder="Describe additional evidence required..."
                          className="w-full rounded border border-slate-300 p-1.5 text-xs dark:border-slate-700 dark:bg-slate-900"
                          rows={2}
                        />
                        <button
                          onClick={handleRequestInformation}
                          disabled={busy || !requestNotes.trim()}
                          className="rounded bg-purple-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-purple-700 disabled:opacity-50"
                        >
                          Request Information
                        </button>
                      </div>
                    )}

                    {isLawyer && selectedCase.status === "UNDER_REVIEW" && (
                      <div className="w-full space-y-2 rounded-lg bg-slate-50 p-3 dark:bg-slate-800/60">
                        <textarea
                          value={decisionNotes}
                          onChange={(e) => setDecisionNotes(e.target.value)}
                          placeholder="Formal decision notes..."
                          className="w-full rounded border border-slate-300 p-1.5 text-xs dark:border-slate-700 dark:bg-slate-900"
                          rows={2}
                        />
                        <div className="flex gap-2">
                          <button
                            onClick={() => handleDecision("APPROVED")}
                            disabled={busy}
                            className="rounded bg-emerald-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-emerald-700"
                          >
                            Approve Case
                          </button>
                          <button
                            onClick={() => handleDecision("REJECTED")}
                            disabled={busy}
                            className="rounded bg-rose-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-rose-700"
                          >
                            Reject Case
                          </button>
                        </div>
                      </div>
                    )}

                    {/* Withdraw (non-terminal) */}
                    {!["APPROVED", "REJECTED", "WITHDRAWN"].includes(selectedCase.status) && (
                      <button
                        onClick={handleWithdraw}
                        disabled={busy}
                        className="rounded border border-slate-300 bg-white px-3 py-1.5 text-xs font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-50 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-300"
                      >
                        Withdraw Case
                      </button>
                    )}
                  </div>
                </div>

                {/* Audit & Status History Timeline */}
                <div className="border-t border-slate-200 pt-4 dark:border-slate-800">
                  <h3 className="text-sm font-semibold text-slate-900 dark:text-white">
                    Review History (Append-Only)
                  </h3>
                  <div className="mt-3 flow-root">
                    <ul className="-mb-8">
                      {selectedCase.status_history.map((item, idx) => (
                        <li key={item.id}>
                          <div className="relative pb-8">
                            {idx !== selectedCase.status_history.length - 1 && (
                              <span
                                className="absolute left-4 top-4 -ml-px h-full w-0.5 bg-slate-200 dark:bg-slate-800"
                                aria-hidden="true"
                              />
                            )}
                            <div className="relative flex space-x-3">
                              <div>
                                <span className="flex h-8 w-8 items-center justify-center rounded-full bg-blue-100 text-blue-600 dark:bg-blue-950 dark:text-blue-400">
                                  <Clock className="h-4 w-4" />
                                </span>
                              </div>
                              <div className="flex min-w-0 flex-1 justify-between space-x-4 pt-1.5">
                                <div>
                                  <p className="text-xs text-slate-700 dark:text-slate-300">
                                    <span className="font-semibold text-slate-900 dark:text-white">
                                      {item.from_status ? `${item.from_status} → ` : "Initial state: "}
                                      {item.to_status}
                                    </span>{" "}
                                    {item.actor_role && `by ${item.actor_role}`}
                                  </p>
                                  {item.notes && (
                                    <p className="mt-0.5 text-xs text-slate-500">
                                      {item.notes}
                                    </p>
                                  )}
                                </div>
                                <div className="whitespace-nowrap text-right text-xs text-slate-400">
                                  {new Date(item.created_at).toLocaleTimeString([], {
                                    hour: "2-digit",
                                    minute: "2-digit",
                                  })}
                                </div>
                              </div>
                            </div>
                          </div>
                        </li>
                      ))}
                    </ul>
                  </div>
                </div>
              </div>
            ) : (
              <div className="flex h-64 flex-col items-center justify-center text-center text-slate-500">
                <Gavel className="h-10 w-10 text-slate-400" />
                <p className="mt-2 text-sm font-medium">Select a verification case</p>
                <p className="text-xs">Choose a case from the left panel to view details and review status.</p>
              </div>
            )}
          </div>
        </div>
      </div>
    </DashboardShell>
  );
}

