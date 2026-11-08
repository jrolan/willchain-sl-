"use client";

import { FormEvent, useEffect, useState } from "react";

import {
  createWillBeneficiary,
  createWillBeneficiaryAllocation,
  deleteWillBeneficiaryAllocation,
  getWillBeneficiaries,
  getWillBeneficiaryAllocations,
  revokeWillBeneficiary,
  updateWillBeneficiaryAllocation,
  updateWillBeneficiary,
} from "@/services/beneficiary-service";
import type {
  BeneficiaryRelationship,
  BeneficiaryRelationshipType,
  BeneficiaryAllocationRecord,
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
  const [allocations, setAllocations] = useState<Record<number, BeneficiaryAllocationRecord[]>>({});
  const [allocationRelationshipId, setAllocationRelationshipId] = useState<number | null>(null);
  const [editingAllocationId, setEditingAllocationId] = useState<number | null>(null);
  const [allocationType, setAllocationType] = useState<BeneficiaryAllocationRecord["allocation_type"]>("SPECIFIC_ITEM");
  const [allocationDescription, setAllocationDescription] = useState("");
  const [allocationAmount, setAllocationAmount] = useState("");
  const [allocationCurrency, setAllocationCurrency] = useState("");
  const [allocationPercentage, setAllocationPercentage] = useState("");
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

  async function toggleAllocations(relationshipId: number) {
    if (allocationRelationshipId === relationshipId) {
      setAllocationRelationshipId(null);
      return;
    }
    setAllocationRelationshipId(relationshipId);
    try {
      const response = await getWillBeneficiaryAllocations(willId, relationshipId);
      setAllocations((current) => ({ ...current, [relationshipId]: response.data }));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to load allocations.");
    }
  }

  async function handleAllocationCreate(event: FormEvent<HTMLFormElement>, relationshipId: number) {
    event.preventDefault();
    setBusyId(relationshipId);
    setError("");
    setMessage("");
    try {
      const payload = {
        allocation_type: allocationType,
        description: allocationDescription,
        amount: allocationType === "FIXED_AMOUNT" ? allocationAmount : null,
        currency_code: allocationType === "FIXED_AMOUNT" ? allocationCurrency.toUpperCase() : "",
        percentage: allocationType === "PERCENTAGE" ? allocationPercentage : null,
      };
      const response = editingAllocationId === null
        ? await createWillBeneficiaryAllocation(willId, relationshipId, payload)
        : await updateWillBeneficiaryAllocation(willId, relationshipId, editingAllocationId, payload);
      setAllocations((current) => ({
        ...current,
        [relationshipId]: editingAllocationId === null
          ? [...(current[relationshipId] ?? []), response.data]
          : (current[relationshipId] ?? []).map((allocation) => allocation.id === editingAllocationId ? response.data : allocation),
      }));
      setEditingAllocationId(null);
      setAllocationDescription("");
      setAllocationAmount("");
      setAllocationCurrency("");
      setAllocationPercentage("");
      setMessage("Allocation saved. It will not be released or notified until verification and explicit authorization.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to save this allocation.");
    } finally {
      setBusyId(null);
    }
  }

  async function handleAllocationDelete(relationshipId: number, allocationId: number) {
    setBusyId(relationshipId);
    setError("");
    try {
      await deleteWillBeneficiaryAllocation(willId, relationshipId, allocationId);
      setAllocations((current) => ({ ...current, [relationshipId]: (current[relationshipId] ?? []).filter((allocation) => allocation.id !== allocationId) }));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to remove this allocation.");
    } finally {
      setBusyId(null);
    }
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
      setError(err instanceof Error ? err.message : "Unable to add this beneficiary.");
    } finally {
      setBusy(false);
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
          <p className="mt-1 text-sm text-[#60776e]">Record the intended beneficiaries. Adding or editing a relationship sends no notification and grants no will access.</p>
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
          <div className="flex items-end"><button type="submit" disabled={busy} className="rounded-lg bg-[#176b5b] px-4 py-2.5 text-sm font-semibold text-white disabled:opacity-50">{busy ? "Adding..." : "Add beneficiary"}</button></div>
        </form>
      ) : (
        <p className="mt-5 rounded-lg bg-[#fffaf0] p-3 text-sm text-[#6d572c]">Only draft wills can change beneficiary relationships. Notifications are sent only after an allocation is individually reviewed and explicitly released.</p>
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
                  <p className="mt-1 text-xs text-[#60776e]">{relationship.relationship_type} · {relationship.status} · No release notification sent</p>
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
                      {editable && <button type="button" disabled={busyId !== null} onClick={() => toggleAllocations(relationship.id)} className="rounded-lg border border-[#dce4df] px-3 py-1.5 text-xs font-semibold text-[#176b5b] disabled:opacity-50">{allocationRelationshipId === relationship.id ? "Hide allocations" : "Manage allocations"}</button>}
                      {editable && (relationship.status === "PENDING" || relationship.status === "ACTIVE") && <button type="button" disabled={busyId !== null} onClick={() => handleRevoke(relationship)} className="rounded-lg border border-[#d9a99a] px-3 py-1.5 text-xs font-semibold text-[#8c422c] disabled:opacity-50">Revoke</button>}
                    </div>
                )}
                  {allocationRelationshipId === relationship.id && editable && (
                    <div className="mt-4 basis-full border-t border-[#edf1ee] pt-4">
                      <h4 className="text-sm font-semibold text-[#17372f]">Allocation records</h4>
                      <ul className="mt-2 divide-y divide-[#edf1ee]">
                        {(allocations[relationship.id] ?? []).map((allocation) => (
                          <li key={allocation.id} className="flex flex-wrap items-center justify-between gap-2 py-2 text-sm">
                            <span>{allocation.allocation_type.replaceAll("_", " ")} · {allocation.description || (allocation.amount ? `${allocation.amount} ${allocation.currency_code}` : `${allocation.percentage}%`)} · {allocation.review_status}</span>
                            <span className="flex gap-3"><button type="button" disabled={busyId !== null} onClick={() => { setEditingAllocationId(allocation.id); setAllocationType(allocation.allocation_type); setAllocationDescription(allocation.description); setAllocationAmount(allocation.amount ?? ""); setAllocationCurrency(allocation.currency_code); setAllocationPercentage(allocation.percentage ?? ""); }} className="text-xs font-semibold text-[#176b5b] disabled:opacity-50">Edit</button><button type="button" disabled={busyId !== null} onClick={() => handleAllocationDelete(relationship.id, allocation.id)} className="text-xs font-semibold text-[#8c422c] disabled:opacity-50">Remove</button></span>
                          </li>
                        ))}
                        {(allocations[relationship.id] ?? []).length === 0 && <li className="py-2 text-xs text-[#809189]">No allocation records yet.</li>}
                      </ul>
                      <form className="mt-4 grid gap-3 sm:grid-cols-2" onSubmit={(event) => handleAllocationCreate(event, relationship.id)}>
                        <label className="text-xs font-semibold text-[#60776e]">Allocation type<select value={allocationType} onChange={(event) => setAllocationType(event.target.value as BeneficiaryAllocationRecord["allocation_type"])} className="mt-1 block w-full rounded-lg border border-[#dce4df] bg-white p-2 text-sm font-normal"><option value="SPECIFIC_ITEM">Specific item</option><option value="FIXED_AMOUNT">Fixed amount</option><option value="PERCENTAGE">Percentage</option></select></label>
                        {allocationType === "FIXED_AMOUNT" && <><label className="text-xs font-semibold text-[#60776e]">Amount<input required type="number" min="0" step="0.0001" value={allocationAmount} onChange={(event) => setAllocationAmount(event.target.value)} className="mt-1 block w-full rounded-lg border border-[#dce4df] p-2 text-sm font-normal" /></label><label className="text-xs font-semibold text-[#60776e]">Currency code<input required minLength={3} maxLength={3} value={allocationCurrency} onChange={(event) => setAllocationCurrency(event.target.value)} className="mt-1 block w-full rounded-lg border border-[#dce4df] p-2 text-sm uppercase font-normal" placeholder="ISO code" /></label></>}
                        {allocationType === "PERCENTAGE" && <label className="text-xs font-semibold text-[#60776e]">Percentage<input required type="number" min="0" max="100" step="0.01" value={allocationPercentage} onChange={(event) => setAllocationPercentage(event.target.value)} className="mt-1 block w-full rounded-lg border border-[#dce4df] p-2 text-sm font-normal" /></label>}
                        <label className="text-xs font-semibold text-[#60776e] sm:col-span-2">{allocationType === "SPECIFIC_ITEM" ? "Item description" : "Description (optional)"}<input required={allocationType === "SPECIFIC_ITEM"} value={allocationDescription} onChange={(event) => setAllocationDescription(event.target.value)} maxLength={500} className="mt-1 block w-full rounded-lg border border-[#dce4df] p-2 text-sm font-normal" /></label>
                        <div className="flex gap-2 sm:col-span-2"><button type="submit" disabled={busyId !== null} className="rounded-lg bg-[#176b5b] px-3 py-2 text-xs font-semibold text-white disabled:opacity-50">{busyId === relationship.id ? "Saving..." : editingAllocationId === null ? "Save allocation" : "Save changes"}</button>{editingAllocationId !== null && <button type="button" onClick={() => { setEditingAllocationId(null); setAllocationDescription(""); setAllocationAmount(""); setAllocationCurrency(""); setAllocationPercentage(""); }} className="rounded-lg border border-[#dce4df] px-3 py-2 text-xs font-semibold text-[#60776e]">Cancel</button>}</div>
                      </form>
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
