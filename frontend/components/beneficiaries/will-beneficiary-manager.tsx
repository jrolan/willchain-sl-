"use client";

import { FormEvent, useEffect, useState } from "react";

import {
  createWillBeneficiary,
  getWillBeneficiaries,
  resendWillBeneficiaryInvitation,
  revokeWillBeneficiary,
  updateWillBeneficiary,
} from "@/services/beneficiary-service";
import type {
  BeneficiaryRelationship,
  BeneficiaryRelationshipType,
} from "@/types/beneficiaries";
import type { WillStatus } from "@/types/wills";

const relationshipTypes: Array<{ value: BeneficiaryRelationshipType; label: string }> = [
  { value: "PRIMARY", label: "Primary" },
  { value: "CONTINGENT", label: "Contingent" },
  { value: "RESIDUAL", label: "Residual" },
  { value: "WITNESS", label: "Witness" },
  { value: "LAWYER", label: "Lawyer" },
];

export function WillBeneficiaryManager({ willId, willStatus }: { willId: number; willStatus: WillStatus }) {
  const [relationships, setRelationships] = useState<BeneficiaryRelationship[]>([]);
  const [recipientEmail, setRecipientEmail] = useState("");
  const [fullName, setFullName] = useState("");
  const [relationshipType, setRelationshipType] = useState<BeneficiaryRelationshipType>("PRIMARY");
  const [loading, setLoading] = useState(true);
  const [busyId, setBusyId] = useState<number | null>(null);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [editName, setEditName] = useState("");
  const [editRelationshipType, setEditRelationshipType] = useState<BeneficiaryRelationshipType>("PRIMARY");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const editable = willStatus === "DRAFT";

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    getWillBeneficiaries(willId)
      .then((response) => {
        if (!cancelled) setRelationships(response.data);
      })
      .catch((err) => {
        if (!cancelled) setError(err instanceof Error ? err.message : "Unable to load beneficiaries.");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [willId]);

  async function refreshRelationships() {
    const response = await getWillBeneficiaries(willId);
    setRelationships(response.data);
  }

  async function handleCreate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError("");
    setMessage("");
    try {
      const response = await createWillBeneficiary(willId, {
        recipient_email: recipientEmail,
        full_name: fullName,
        relationship_type: relationshipType,
      });
      setMessage(response.message);
      setRecipientEmail("");
      setFullName("");
      setRelationshipType("PRIMARY");
      await refreshRelationships();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to invite this beneficiary.");
    } finally {
      setBusy(false);
    }
  }

  async function handleResend(relationship: BeneficiaryRelationship) {
    setBusyId(relationship.id);
    setError("");
    setMessage("");
    try {
      const response = await resendWillBeneficiaryInvitation(willId, relationship.id);
      setMessage(response.message);
      await refreshRelationships();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to resend the invitation.");
    } finally {
      setBusyId(null);
    }
  }

  async function handleUpdate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (editingId === null) return;
    setBusyId(editingId);
    setError("");
    setMessage("");
    try {
      const response = await updateWillBeneficiary(willId, editingId, {
        full_name: editName,
        relationship_type: editRelationshipType,
      });
      setMessage(response.message);
      setEditingId(null);
      await refreshRelationships();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to update this beneficiary.");
    } finally {
      setBusyId(null);
    }
  }

  async function handleRevoke(relationship: BeneficiaryRelationship) {
    if (!window.confirm(`Revoke ${relationship.recipient_email}'s beneficiary relationship?`)) return;
    setBusyId(relationship.id);
    setError("");
    setMessage("");
    try {
      const response = await revokeWillBeneficiary(willId, relationship.id);
      setMessage(response.message);
      await refreshRelationships();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to revoke this relationship.");
    } finally {
      setBusyId(null);
    }
  }

  return (
    <section className="mt-6 rounded-xl border border-[#dce4df] bg-white p-6 shadow-sm" aria-labelledby="beneficiary-manager-title">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 id="beneficiary-manager-title" className="text-lg font-semibold text-[#17372f]">Beneficiaries</h2>
          <p className="mt-1 text-sm text-[#60776e]">Manage invitation relationships for this will. Beneficiary status does not grant access to the will.</p>
        </div>
        <span className="rounded-full bg-[#f5f7f6] px-3 py-1 text-xs font-bold text-[#60776e]">{willStatus}</span>
      </div>

      {message && <p className="mt-4 rounded-lg bg-[#d8f0e5] p-3 text-sm text-[#0f5548]" role="status">{message}</p>}
      {error && <p className="mt-4 rounded-lg bg-[#fff3ed] p-3 text-sm text-[#8c422c]" role="alert">{error}</p>}

      {editable ? (
        <form className="mt-5 grid gap-3 border-b border-[#edf1ee] pb-5 sm:grid-cols-2" onSubmit={handleCreate}>
          <label className="text-sm font-semibold text-[#17372f]">Recipient email<input type="email" required value={recipientEmail} onChange={(event) => setRecipientEmail(event.target.value)} className="mt-1.5 w-full rounded-lg border border-[#dce4df] p-2.5 font-normal" autoComplete="email" /></label>
          <label className="text-sm font-semibold text-[#17372f]">Full name (optional)<input value={fullName} onChange={(event) => setFullName(event.target.value)} maxLength={200} className="mt-1.5 w-full rounded-lg border border-[#dce4df] p-2.5 font-normal" autoComplete="name" /></label>
          <label className="text-sm font-semibold text-[#17372f]">Relationship type<select value={relationshipType} onChange={(event) => setRelationshipType(event.target.value as BeneficiaryRelationshipType)} className="mt-1.5 w-full rounded-lg border border-[#dce4df] bg-white p-2.5 font-normal">{relationshipTypes.map((type) => <option key={type.value} value={type.value}>{type.label}</option>)}</select></label>
          <div className="flex items-end"><button type="submit" disabled={busy} className="rounded-lg bg-[#176b5b] px-4 py-2.5 text-sm font-semibold text-white disabled:opacity-50">{busy ? "Sending..." : "Invite beneficiary"}</button></div>
        </form>
      ) : (
        <p className="mt-5 rounded-lg bg-[#fffaf0] p-3 text-sm text-[#6d572c]">Only draft wills can add, resend, or revoke beneficiary invitations.</p>
      )}

      <div className="mt-5">
        <h3 className="text-sm font-semibold text-[#17372f]">Relationship records</h3>
        {loading ? <p className="mt-3 text-sm text-[#809189]">Loading beneficiaries...</p> : relationships.length === 0 ? <p className="mt-3 text-sm text-[#809189]">No beneficiary relationships for this will yet.</p> : (
          <ul className="mt-3 divide-y divide-[#edf1ee]">
            {relationships.map((relationship) => (
              <li key={relationship.id} className="flex flex-wrap items-center justify-between gap-3 py-4">
                <div className="min-w-0">
                  <p className="break-all text-sm font-semibold text-[#17372f]">{relationship.full_name || relationship.recipient_email}</p>
                  {relationship.full_name && <p className="break-all text-xs text-[#809189]">{relationship.recipient_email}</p>}
                  <p className="mt-1 text-xs text-[#60776e]">{relationship.relationship_type} · {relationship.status} · Invitation: {relationship.latest_invitation_status ?? "Not sent"}</p>
                </div>
                {editingId === relationship.id ? (
                  <form className="flex flex-wrap items-end gap-2" onSubmit={handleUpdate}>
                    <label className="text-xs font-semibold text-[#60776e]">Name<input value={editName} onChange={(event) => setEditName(event.target.value)} maxLength={200} className="mt-1 block rounded-lg border border-[#dce4df] p-2 font-normal" /></label>
                    <label className="text-xs font-semibold text-[#60776e]">Category<select value={editRelationshipType} onChange={(event) => setEditRelationshipType(event.target.value as BeneficiaryRelationshipType)} className="mt-1 block rounded-lg border border-[#dce4df] bg-white p-2 font-normal">{relationshipTypes.map((type) => <option key={type.value} value={type.value}>{type.label}</option>)}</select></label>
                    <button type="submit" disabled={busyId !== null} className="rounded-lg bg-[#176b5b] px-3 py-2 text-xs font-semibold text-white disabled:opacity-50">{busyId === relationship.id ? "Saving..." : "Save"}</button>
                    <button type="button" disabled={busyId !== null} onClick={() => setEditingId(null)} className="rounded-lg border border-[#dce4df] px-3 py-2 text-xs font-semibold text-[#60776e]">Cancel</button>
                  </form>
                ) : (
                  <div className="flex gap-2">
                    {editable && <button type="button" disabled={busyId !== null} onClick={() => { setEditingId(relationship.id); setEditName(relationship.full_name); setEditRelationshipType(relationship.relationship_type as BeneficiaryRelationshipType); }} className="rounded-lg border border-[#dce4df] px-3 py-1.5 text-xs font-semibold text-[#176b5b] disabled:opacity-50">Edit</button>}
                    {editable && relationship.status === "PENDING" && <button type="button" disabled={busyId !== null} onClick={() => handleResend(relationship)} className="rounded-lg border border-[#dce4df] px-3 py-1.5 text-xs font-semibold text-[#176b5b] disabled:opacity-50">{busyId === relationship.id ? "Working..." : "Resend"}</button>}
                    {editable && (relationship.status === "PENDING" || relationship.status === "ACTIVE") && <button type="button" disabled={busyId !== null} onClick={() => handleRevoke(relationship)} className="rounded-lg border border-[#d9a99a] px-3 py-1.5 text-xs font-semibold text-[#8c422c] disabled:opacity-50">Revoke</button>}
                  </div>
                )}
              </li>
            ))}
          </ul>
        )}
      </div>
    </section>
  );
}
