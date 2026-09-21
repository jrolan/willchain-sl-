"use client";

import Link from "next/link";
import { FormEvent, useEffect, useState } from "react";
import { ArrowLeft, Check, ChevronLeft, ChevronRight, FilePenLine, LockKeyhole, Save, ShieldCheck } from "lucide-react";

import { useAuth } from "@/lib/auth-context";
import { createWill, finalizeWill, getProfile, getWills, updateWill } from "@/services/auth-service";
import type { User } from "@/types/auth";
import type { Will, WillContent } from "@/types/wills";

const steps = ["Your details", "Family", "Appointments", "People who inherit", "Gifts and wishes", "Review"];

const emptyContent: WillContent = {
  testator: { full_name: "", address: "", occupation: "", marital_status: "SINGLE" },
  family: { spouse_or_partner: "", children: [], dependants: [] },
  executor: { full_name: "", relationship: "", address: "", phone: "", alternate_full_name: "" },
  guardians: [],
  beneficiaries: [],
  gifts: [],
  residual_estate: "",
  funeral_wishes: "",
  digital_assets_notes: "",
  review_notes: "",
};

function cloneContent(content: WillContent): WillContent {
  return JSON.parse(JSON.stringify({ ...emptyContent, ...content })) as WillContent;
}

export default function WillsWorkspacePage() {
  const { user, initialLoading } = useAuth();
  const [profileUser, setProfileUser] = useState<User | null>(user);
  const [wills, setWills] = useState<Will[]>([]);
  const [selectedWillId, setSelectedWillId] = useState<number | null>(null);
  const [title, setTitle] = useState("My Last Will and Testament");
  const [content, setContent] = useState<WillContent>(cloneContent(emptyContent));
  const [step, setStep] = useState(0);
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    if (!initialLoading && !user) window.location.href = "/login";
  }, [initialLoading, user]);

  useEffect(() => {
    if (!user) return;
    Promise.all([getProfile(), getWills()])
      .then(([profile, response]) => {
        setProfileUser(profile.data);
        setWills(response.data);
        if (response.data.length === 0) {
          setContent((current) => ({
            ...current,
            testator: {
              ...current.testator,
              full_name: `${profile.data.first_name} ${profile.data.last_name}`.trim(),
              address: "",
              occupation: "",
            },
          }));
        }
      })
      .catch((err) => setError(err instanceof Error ? err.message : "Unable to load your wills."))
      .finally(() => setLoading(false));
  }, [user]);

  function updateSection<K extends keyof WillContent>(section: K, value: WillContent[K]) {
    setContent((current) => ({ ...current, [section]: value }));
  }

  function selectWill(will: Will) {
    setSelectedWillId(will.id);
    setTitle(will.title);
    setContent(cloneContent(will.content));
    setStep(0);
    setMessage("");
    setError("");
  }

  function startNew() {
    setSelectedWillId(null);
    setTitle("My Last Will and Testament");
    setContent(cloneContent(emptyContent));
    setStep(0);
    setMessage("");
    setError("");
  }

  async function saveDraft(event?: FormEvent<HTMLFormElement>) {
    event?.preventDefault();
    setBusy(true);
    setMessage("");
    setError("");
    try {
      const response = selectedWillId
        ? await updateWill(selectedWillId, { title, content })
        : await createWill({ title, content });
      setSelectedWillId(response.data.id);
      setMessage("Draft saved securely.");
      const willsResponse = await getWills();
      setWills(willsResponse.data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to save this draft.");
    } finally {
      setBusy(false);
    }
  }

  async function finalize() {
    if (!selectedWillId) {
      setError("Save the draft before reviewing it for finalization.");
      return;
    }
    if (!window.confirm("Finalize this will? A finalized will cannot be edited.")) return;
    setBusy(true);
    setMessage("");
    setError("");
    try {
      await finalizeWill(selectedWillId);
      const willsResponse = await getWills();
      setWills(willsResponse.data);
      setMessage("Will finalized successfully.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to finalize this will.");
    } finally {
      setBusy(false);
    }
  }

  const testator = content.testator ?? {};
  const family = content.family ?? {};
  const executor = content.executor ?? {};
  const beneficiaries = content.beneficiaries ?? [];
  const gifts = content.gifts ?? [];

  if (initialLoading || loading) return <main className="min-h-screen p-10 text-[#60776e]">Loading your private will workspace...</main>;

  return (
    <main className="dashboard-page will-workspace min-h-screen">
      <header className="dashboard-header">
        <div className="mx-auto flex max-w-7xl items-center justify-between px-5 py-5 sm:px-10 lg:px-16">
          <Link href="/dashboard" className="inline-flex items-center gap-2 text-sm font-bold text-[#17372f]"><ArrowLeft size={16} /> Dashboard</Link>
          <div className="inline-flex items-center gap-2 text-sm font-bold text-[#17372f]"><ShieldCheck size={17} /> WILLCHAIN SL</div>
        </div>
      </header>

      <section className="mx-auto grid max-w-7xl gap-8 px-5 py-10 sm:px-10 lg:grid-cols-[260px_1fr] lg:px-16">
        <aside>
          <p className="text-xs font-bold uppercase tracking-wider text-[#aa7d34]">Private workspace</p>
          <h1 className="mt-2 text-3xl font-semibold text-[#17372f]">Build your will</h1>
          <p className="mt-3 text-sm leading-6 text-[#60776e]">A guided draft for your review. You can save and return before making any final decision.</p>
          <nav className="mt-8 grid gap-2" aria-label="Will draft sections">
            {steps.map((label, index) => (
              <button key={label} type="button" onClick={() => setStep(index)} className={`flex items-center gap-3 border-b px-1 py-3 text-left text-sm font-semibold transition-colors ${step === index ? "border-[#176b5b] text-[#176b5b]" : index < step ? "border-[#c7a86b] text-[#60776e]" : "border-[#dce4df] text-[#809189] hover:text-[#176b5b]"}`}>
                <span className={`grid h-7 w-7 place-items-center rounded-full border text-xs ${step === index ? "border-[#176b5b] bg-[#176b5b] text-white" : index < step ? "border-[#c7a86b] text-[#8c5e15]" : "border-[#dce4df] text-[#809189]"}`}>{index < step ? "✓" : index + 1}</span>{label}
              </button>
            ))}
          </nav>
          <div className="mt-8 rounded-lg border border-[#dce4df] bg-white p-4 text-xs leading-5 text-[#60776e]"><LockKeyhole size={15} className="mb-2 text-[#176b5b]" />Your draft is private to your account. Witness, beneficiary, legal verification, blockchain, and AI workflows are not enabled here.</div>
        </aside>

        <div className="min-w-0">
          <div className="rounded-xl border border-[#dce4df] bg-white p-6 shadow-sm sm:p-8">
            <div className="flex flex-wrap items-start justify-between gap-4 border-b border-[#edf1ee] pb-6">
              <div><p className="text-xs font-bold uppercase tracking-wider text-[#aa7d34]">Step {step + 1} of {steps.length}</p><h2 className="mt-2 text-2xl font-semibold text-[#17372f]">{steps[step]}</h2></div>
              <FilePenLine className="text-[#176b5b]" size={25} />
            </div>

            {message && <div className="mt-5 rounded-lg bg-[#d8f0e5] p-3 text-sm text-[#0f5548]" role="status">{message}</div>}
            {error && <div className="mt-5 rounded-lg bg-[#fff3ed] p-3 text-sm text-[#8c422c]" role="alert">{error}</div>}

            <form className="mt-6" onSubmit={saveDraft}>
              {step === 0 && <div className="grid gap-6">
                <div className="border-b border-[#edf1ee] pb-5"><p className="text-sm leading-6 text-[#60776e]">We begin with the person making this will. Your account identifies you as the owner; these details describe you in the draft.</p></div>
                <div className="grid gap-4 sm:grid-cols-2">
                  <Field label="Will title" value={title} onChange={setTitle} required />
                  <Field label="Full legal name" value={testator.full_name ?? ""} onChange={(value) => updateSection("testator", { ...testator, full_name: value })} required />
                  <Field label="Residential address" value={testator.address ?? ""} onChange={(value) => updateSection("testator", { ...testator, address: value })} />
                  <Field label="Occupation" value={testator.occupation ?? ""} onChange={(value) => updateSection("testator", { ...testator, occupation: value })} />
                  <Field label="Account email" value={profileUser?.email ?? ""} onChange={() => undefined} readOnly />
                  <Field label="Phone number" value={profileUser?.phone_number ?? ""} onChange={() => undefined} readOnly />
                  <label className="text-sm font-semibold text-[#17372f]">Marital status<select value={testator.marital_status ?? "SINGLE"} onChange={(event) => updateSection("testator", { ...testator, marital_status: event.target.value as typeof testator.marital_status })} className="mt-1.5 w-full rounded-lg border border-[#dce4df] bg-white p-2.5 font-normal"><option value="SINGLE">Single</option><option value="MARRIED">Married</option><option value="SEPARATED">Separated</option><option value="WIDOWED">Widowed</option><option value="OTHER">Other</option></select></label>
                </div>
              </div>}

              {step === 1 && <div className="grid gap-5"><Field label="Spouse or partner" value={family.spouse_or_partner ?? ""} onChange={(value) => updateSection("family", { ...family, spouse_or_partner: value })} /><TextArea label="Children and dependants" value={(family.children ?? []).map((child) => child.full_name).join("\n")} onChange={(value) => updateSection("family", { ...family, children: value.split("\n").filter(Boolean).map((full_name) => ({ full_name })) })} hint="Enter one name per line. You can add more detail during review." /></div>}

              {step === 2 && <div className="grid gap-5 sm:grid-cols-2"><Field label="Executor / personal representative" value={executor.full_name ?? ""} onChange={(value) => updateSection("executor", { ...executor, full_name: value })} /><Field label="Relationship" value={executor.relationship ?? ""} onChange={(value) => updateSection("executor", { ...executor, relationship: value })} /><Field label="Address" value={executor.address ?? ""} onChange={(value) => updateSection("executor", { ...executor, address: value })} /><Field label="Phone" value={executor.phone ?? ""} onChange={(value) => updateSection("executor", { ...executor, phone: value })} /><Field label="Alternate executor (optional)" value={executor.alternate_full_name ?? ""} onChange={(value) => updateSection("executor", { ...executor, alternate_full_name: value })} /></div>}

              {step === 3 && <div className="grid gap-5"><TextArea label="Beneficiaries" value={beneficiaries.map((item) => item.full_name).join("\n")} onChange={(value) => updateSection("beneficiaries", value.split("\n").filter(Boolean).map((full_name) => ({ full_name })))} hint="Enter one person or organisation per line." /><TextArea label="Guardians or care arrangements (optional)" value={(content.guardians ?? []).map((item) => item.full_name).join("\n")} onChange={(value) => updateSection("guardians", value.split("\n").filter(Boolean).map((full_name) => ({ full_name })))} /></div>}

              {step === 4 && <div className="grid gap-5"><TextArea label="Specific gifts" value={gifts.map((item) => `${item.beneficiary_name}: ${item.description}`).join("\n")} onChange={(value) => updateSection("gifts", value.split("\n").filter(Boolean).map((line) => { const [beneficiary_name, ...description] = line.split(":"); return { beneficiary_name: beneficiary_name.trim(), description: description.join(":").trim() }; }))} hint="Use one line per gift: person or organisation: item or property." /><TextArea label="What should happen to the rest of your estate?" value={content.residual_estate ?? ""} onChange={(value) => updateSection("residual_estate", value)} /><TextArea label="Funeral or personal wishes (optional)" value={content.funeral_wishes ?? ""} onChange={(value) => updateSection("funeral_wishes", value)} /><TextArea label="Digital-assets notes (optional)" value={content.digital_assets_notes ?? ""} onChange={(value) => updateSection("digital_assets_notes", value)} /></div>}

              {step === 5 && <div className="grid gap-5"><Field label="Draft title" value={title} onChange={setTitle} required /><Review label="Testator" value={testator.full_name || "Not provided"} /><Review label="Executor" value={executor.full_name || "Not provided"} /><Review label="Beneficiaries" value={beneficiaries.map((item) => item.full_name).join(", ") || "Not provided"} /><Review label="Specific gifts" value={gifts.length ? `${gifts.length} gift instruction(s)` : "None recorded"} /><div className="rounded-lg bg-[#fffaf0] p-4 text-sm leading-6 text-[#6d572c]">This is a product draft for your review. It is not legal advice and does not complete witnessing, notarization, legal verification, release, blockchain registration, or AI analysis.</div></div>}

              <div className="mt-8 flex flex-wrap justify-between gap-3 border-t border-[#edf1ee] pt-5"><button type="button" disabled={step === 0} onClick={() => setStep((current) => current - 1)} className="inline-flex items-center gap-2 rounded-lg border border-[#dce4df] px-4 py-2 text-sm font-semibold text-[#60776e] disabled:opacity-40"><ChevronLeft size={16} /> Previous</button><div className="flex gap-3"><button type="submit" disabled={busy} className="inline-flex items-center gap-2 rounded-lg border border-[#176b5b] px-4 py-2 text-sm font-semibold text-[#176b5b]"><Save size={16} /> {busy ? "Saving..." : "Save draft"}</button>{step < steps.length - 1 ? <button type="button" onClick={() => setStep((current) => current + 1)} className="inline-flex items-center gap-2 rounded-lg bg-[#176b5b] px-4 py-2 text-sm font-semibold text-white">Next <ChevronRight size={16} /></button> : <button type="button" disabled={busy || !selectedWillId} onClick={finalize} className="inline-flex items-center gap-2 rounded-lg bg-[#8c5e15] px-4 py-2 text-sm font-semibold text-white disabled:opacity-40"><Check size={16} /> Finalize</button>}</div></div>
            </form>
          </div>

          <section className="mt-6 rounded-xl border border-[#dce4df] bg-white p-6 shadow-sm"><div className="flex items-center justify-between gap-3"><h2 className="text-lg font-semibold text-[#17372f]">Saved drafts</h2><button type="button" onClick={startNew} className="text-sm font-bold text-[#176b5b]">Start new</button></div>{wills.length === 0 ? <p className="mt-4 text-sm text-[#809189]">No saved drafts yet.</p> : <div className="mt-4 grid gap-2">{wills.map((will) => <button type="button" key={will.id} onClick={() => selectWill(will)} className={`flex items-center justify-between rounded-lg border p-3 text-left ${selectedWillId === will.id ? "border-[#176b5b] bg-[#f5faf7]" : "border-[#edf1ee]"}`}><span><span className="block text-sm font-semibold text-[#17372f]">{will.title}</span><span className="text-xs text-[#809189]">Version {will.version}</span></span><span className="text-xs font-bold text-[#176b5b]">{will.status}</span></button>)}</div>}</section>
        </div>
      </section>
    </main>
  );
}

function Field({ label, value, onChange, required = false, readOnly = false }: { label: string; value: string; onChange: (value: string) => void; required?: boolean; readOnly?: boolean }) {
  return <label className="text-sm font-semibold text-[#17372f]">{label}<input required={required} readOnly={readOnly} value={value} onChange={(event) => onChange(event.target.value)} className={`mt-1.5 w-full rounded-lg border border-[#dce4df] p-2.5 font-normal ${readOnly ? "bg-[#f5f7f6] text-[#809189]" : "bg-white"}`} /></label>;
}

function TextArea({ label, value, onChange, hint }: { label: string; value: string; onChange: (value: string) => void; hint?: string }) {
  return <label className="text-sm font-semibold text-[#17372f]">{label}<textarea rows={5} value={value} onChange={(event) => onChange(event.target.value)} className="mt-1.5 w-full rounded-lg border border-[#dce4df] p-2.5 font-normal" />{hint && <span className="mt-1 block text-xs font-normal text-[#809189]">{hint}</span>}</label>;
}

function Review({ label, value }: { label: string; value: string }) {
  return <div className="rounded-lg border border-[#edf1ee] p-4"><p className="text-xs font-bold uppercase tracking-wider text-[#809189]">{label}</p><p className="mt-1 text-sm text-[#17372f]">{value}</p></div>;
}
