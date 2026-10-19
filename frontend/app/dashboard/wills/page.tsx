"use client";

import { FormEvent, useEffect, useState } from "react";
import { AlertTriangle, Bold, Check, CheckCircle2, ChevronLeft, ChevronRight, Columns2, Eye, FileCheck2, FilePenLine, FileText, Italic, List as ListIcon, ListOrdered, LockKeyhole, Redo2, Save, ShieldCheck, Underline as UnderlineIcon, Undo2, Upload } from "lucide-react";
import { EditorContent, useEditor } from "@tiptap/react";
import StarterKit from "@tiptap/starter-kit";
import Placeholder from "@tiptap/extension-placeholder";
import Underline from "@tiptap/extension-underline";

import { DashboardShell } from "@/components/layout/dashboard-shell";
import { useAuth } from "@/lib/auth-context";
import { buildWillDocumentHtml, buildWillDocumentText } from "@/lib/will-export.mjs";
import { WillBeneficiaryManager } from "@/components/beneficiaries/will-beneficiary-manager";
import { WillDocumentManager } from "@/components/documents/will-document-manager";
import { checkWillDocumentIntegrity, uploadWillDocument } from "@/services/document-service";
import { createWill, finalizeWill, getProfile, getWills, sendInvitation, updateWill } from "@/services/auth-service";
import { DOCUMENT_MAX_BYTES, validateDocumentFile } from "@/lib/document-rules.mjs";
import type { WillDocument } from "@/types/documents";
import type { InvitationRole, User } from "@/types/auth";
import type { Will, WillContent } from "@/types/wills";

const steps = ["Your details", "Family", "Appointments", "People who inherit", "Gifts and wishes", "Legal collaborators", "Review"];
const uploadSteps = ["Testator NIN & ID", "Cap. 25 Compliance", "Mode Selection", "Upload & Enclave", "Witness Verification", "Legal Seal & Registry"];

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
  const [workspaceView, setWorkspaceView] = useState<"split" | "form" | "document">("split");
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [draftSource, setDraftSource] = useState<"structured" | "upload" | "paste">("structured");
  const [draftText, setDraftText] = useState("");
  const [uploadedWillFile, setUploadedWillFile] = useState<File | null>(null);
  const [identityDocumentFile, setIdentityDocumentFile] = useState<File | null>(null);
  const [uploadedWillDocument, setUploadedWillDocument] = useState<WillDocument | null>(null);
  const [uploadedIdentityDocument, setUploadedIdentityDocument] = useState<WillDocument | null>(null);
  const [uploadStep, setUploadStep] = useState(0);
  const [uploadBusy, setUploadBusy] = useState(false);
  const [collaboratorEmail, setCollaboratorEmail] = useState("");
  const [collaboratorFirstName, setCollaboratorFirstName] = useState("");
  const [collaboratorLastName, setCollaboratorLastName] = useState("");
  const [collaboratorRole, setCollaboratorRole] = useState<InvitationRole>("WITNESS");
  const [collaboratorMessage, setCollaboratorMessage] = useState("");
  const [invitingCollaborator, setInvitingCollaborator] = useState(false);
  const pastedEditor = useEditor({
    extensions: [StarterKit, Underline, Placeholder.configure({ placeholder: "Paste your will text here. Use headings, lists, and emphasis to organize it." })],
    content: "<p></p>",
    immediatelyRender: false,
    onUpdate: ({ editor }) => setDraftText(editor.getText()),
  });

  useEffect(() => {
    if (!initialLoading && !user) window.location.href = "/login";
  }, [initialLoading, user]);

  useEffect(() => {
    if (!user) return;
    Promise.all([getProfile(), getWills()])
      .then(([profile, response]) => {
        setProfileUser(profile.data);
        setWills(response.data);
        const params = new URLSearchParams(window.location.search);
        const requestedWillId = Number(params.get("willId"));
        const requestedWill = response.data.find((will) => will.id === requestedWillId);
        if (requestedWill) {
          const requestedStep = Number.parseInt(params.get("step") ?? "0", 10);
          selectWill(requestedWill, Number.isFinite(requestedStep) ? requestedStep : 0);
        } else if (params.has("willId")) {
          setError("That will could not be found in your drafts.");
        } else if (response.data.length === 0) {
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

  useEffect(() => {
    if (!pastedEditor) return;
    if (selectedWillId === null) {
      pastedEditor.commands.clearContent();
      return;
    }
    const storedBody = wills.find((will) => will.id === selectedWillId)?.content.sections?.find((section) => section.title === "Pasted will draft")?.body;
    if (!storedBody) return;

    try {
      const parsed = JSON.parse(storedBody);
      if (parsed?.type === "doc" && Array.isArray(parsed.content)) {
        pastedEditor.commands.setContent(parsed);
        return;
      }
    } catch {
      // Older pasted drafts are stored as plain text.
    }

    pastedEditor.commands.setContent({
      type: "doc",
      content: storedBody.split(/\r?\n/).map((text) => ({
        type: "paragraph",
        content: text ? [{ type: "text", text }] : [],
      })),
    });
  }, [pastedEditor, selectedWillId, wills]);

  function updateSection<K extends keyof WillContent>(section: K, value: WillContent[K]) {
    setContent((current) => ({ ...current, [section]: value }));
  }

  function selectWill(will: Will, initialStep = 0) {
    setSelectedWillId(will.id);
    setTitle(will.title);
    setContent(cloneContent(will.content));
    setStep(Math.min(Math.max(initialStep, 0), steps.length - 1));
    setMessage("");
    setError("");
  }

  function startNew() {
    setSelectedWillId(null);
    setTitle("My Last Will and Testament");
    setContent(cloneContent(emptyContent));
    pastedEditor?.commands.clearContent();
    setDraftText("");
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
      const draftContent = draftSource === "paste" && draftText.trim()
        ? { ...content, sections: [{ title: "Pasted will draft", body: JSON.stringify(pastedEditor?.getJSON() ?? { type: "doc", content: [] }) }] }
        : content;
      const response = selectedWillId
        ? await updateWill(selectedWillId, { title, content: draftContent })
        : await createWill({ title, content: draftContent });
      setSelectedWillId(response.data.id);
      setContent(cloneContent(response.data.content));
      setMessage("Draft saved securely.");
      const willsResponse = await getWills();
      setWills(willsResponse.data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to save this draft.");
    } finally {
      setBusy(false);
    }
  }

  async function ensureEditableWillId() {
    if (selectedWillId !== null) {
      const selectedWill = wills.find((will) => will.id === selectedWillId);
      if (selectedWill && selectedWill.status !== "DRAFT") {
        throw new Error("Choose or create a draft before uploading documents.");
      }
      return selectedWillId;
    }
    const response = await createWill({ title, content });
    setSelectedWillId(response.data.id);
    setWills((current) => [response.data, ...current.filter((will) => will.id !== response.data.id)]);
    return response.data.id;
  }

  async function uploadIntakeDocument(file: File, documentType: "IDENTITY" | "OTHER", description: string) {
    const validationError = validateDocumentFile(file, DOCUMENT_MAX_BYTES);
    if (validationError) throw new Error(validationError);
    const willId = await ensureEditableWillId();
    const response = await uploadWillDocument(willId, file, documentType, description);
    await checkWillDocumentIntegrity(willId, response.data.id);
    return response.data;
  }

  async function saveIdentityAndContinue() {
    const nationalId = String(content.testator?.national_id ?? "").trim();
    if (!testator.full_name?.trim() || !nationalId || (!identityDocumentFile && !uploadedIdentityDocument)) {
      setError("Enter the testator's legal name and NIN, and choose a PDF or image of the identity document.");
      return;
    }
    if (uploadedIdentityDocument && !identityDocumentFile) {
      setUploadStep(1);
      return;
    }
    setUploadBusy(true);
    setError("");
    setMessage("");
    try {
      const document = await uploadIntakeDocument(identityDocumentFile!, "IDENTITY", `Testator identity document · NIN ${nationalId}`);
      setUploadedIdentityDocument(document);
      setIdentityDocumentFile(null);
      setMessage("Identity document stored privately; the integrity check was recorded.");
      setUploadStep(1);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to upload the identity document.");
    } finally {
      setUploadBusy(false);
    }
  }

  async function uploadExistingWill() {
    if (uploadedWillDocument) {
      setUploadStep(4);
      return;
    }
    if (!uploadedWillFile) {
      setError("Choose the signed will PDF before continuing.");
      return;
    }
    setUploadBusy(true);
    setError("");
    setMessage("");
    try {
      const document = await uploadIntakeDocument(uploadedWillFile, "OTHER", "Owner-supplied existing will · original file");
      setUploadedWillDocument(document);
      setUploadedWillFile(null);
      setMessage("Existing will stored privately; the integrity check was recorded. OCR and clause extraction are not available yet.");
      setUploadStep(4);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to upload the will document.");
    } finally {
      setUploadBusy(false);
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

  function downloadGeneratedWill() {
    const selectedWill = selectedWillId !== null ? wills.find((will) => will.id === selectedWillId) ?? null : null;
    if (!selectedWill) {
      setError("Save or select a will before downloading it.");
      return;
    }
    const blob = new Blob([buildWillDocumentText(selectedWill)], { type: "text/plain;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = `${selectedWill.title || "my-will"}.txt`;
    anchor.click();
    window.setTimeout(() => URL.revokeObjectURL(url), 1000);
    setMessage("The will draft is downloading as a readable text document.");
  }

  function printGeneratedWill() {
    const selectedWill = selectedWillId !== null ? wills.find((will) => will.id === selectedWillId) ?? null : null;
    if (!selectedWill) {
      setError("Save or select a will before printing it.");
      return;
    }
    const printWindow = window.open("", "_blank", "noopener,noreferrer");
    if (!printWindow) {
      setError("Your browser blocked the print window. Please allow popups and try again.");
      return;
    }
    printWindow.document.write(buildWillDocumentHtml(selectedWill));
    printWindow.document.close();
    printWindow.focus();
    window.setTimeout(() => {
      printWindow.print();
    }, 250);
    setMessage("Print preview opened. Use Save as PDF from your browser if needed.");
  }

  async function inviteCollaborator() {
    if (!collaboratorEmail.trim()) {
      setError("Please enter the collaborator email before sending the invitation.");
      return;
    }
    setInvitingCollaborator(true);
    setError("");
    setMessage("");
    try {
      await sendInvitation({
        email: collaboratorEmail.trim(),
        first_name: collaboratorFirstName.trim(),
        last_name: collaboratorLastName.trim(),
        role: collaboratorRole,
        message: collaboratorMessage.trim(),
      });
      setCollaboratorEmail("");
      setCollaboratorFirstName("");
      setCollaboratorLastName("");
      setCollaboratorMessage("");
      setMessage(`${collaboratorRole === "WITNESS" ? "Witness" : "Legal verifier"} invitation sent successfully.`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to send the collaborator invitation.");
    } finally {
      setInvitingCollaborator(false);
    }
  }

  const testator = content.testator ?? {};
  const family = content.family ?? {};
  const executor = content.executor ?? {};
  const beneficiaries = content.beneficiaries ?? [];
  const gifts = content.gifts ?? [];
  const draftProgress = [
    { label: "Testator", step: 0, value: [testator.full_name, testator.address, testator.occupation].filter((value) => Boolean(String(value ?? "").trim())).length, total: 3 },
    { label: "Family", step: 1, value: [family.spouse_or_partner, family.children?.length, family.dependants?.length].filter(Boolean).length, total: 3 },
    { label: "Appointments", step: 2, value: [executor.full_name, executor.relationship, executor.address, executor.phone].filter((value) => Boolean(String(value ?? "").trim())).length, total: 4 },
    { label: "People", step: 3, value: [beneficiaries.length, content.guardians?.length].filter(Boolean).length, total: 2 },
    { label: "Gifts", step: 4, value: [gifts.length, content.residual_estate, content.funeral_wishes, content.digital_assets_notes].filter((value) => Boolean(value)).length, total: 4 },
    { label: "Collaborators", step: 5, value: [collaboratorEmail, collaboratorFirstName, collaboratorLastName].filter((value) => Boolean(value.trim())).length, total: 3 },
    { label: "Saved", step: 6, value: selectedWillId ? 1 : 0, total: 1 },
  ];
  const progressEntered = draftProgress.reduce((total, item) => total + item.value, 0);
  const progressAvailable = draftProgress.reduce((total, item) => total + item.total, 0);

  if (initialLoading || loading) return <main className="min-h-screen p-10 text-[#60776e]">Loading your private will workspace...</main>;

  return (
    <DashboardShell profileUser={profileUser}>
      <div className="dashboard-page will-workspace">
      <section className="mx-auto max-w-7xl px-5 py-8 sm:px-8 lg:px-12">
        <header className="will-workspace-heading">
          <div>
            <p className="text-xs font-bold uppercase tracking-wider text-[#aa7d34]">Private workspace</p>
            <h1 className="mt-2 text-3xl font-semibold text-[#17372f]">Build your will</h1>
            <p className="mt-2 text-sm leading-6 text-[#60776e]">A guided draft for your review. You can save and return before making any final decision.</p>
          </div>
          <span className="will-workspace-step-count">Step {step + 1} of {steps.length}</span>
        </header>

        <div className="will-overview-toolbar">
          <nav className="will-view-switcher" aria-label="Will overview view">
            <button type="button" aria-pressed={workspaceView === "split"} onClick={() => setWorkspaceView("split")}><Columns2 size={14} /> Split view</button>
            <button type="button" aria-pressed={workspaceView === "form"} onClick={() => setWorkspaceView("form")}><FileText size={14} /> Structured form</button>
            <button type="button" aria-pressed={workspaceView === "document"} onClick={() => setWorkspaceView("document")}><Eye size={14} /> Document preview</button>
          </nav>
          <span className={`will-sync-status ${selectedWillId ? "saved" : "unsaved"}`}><span />{selectedWillId ? "Draft saved" : "Unsaved draft"}</span>
        </div>

        {draftSource !== "upload" && <nav className="will-stepper" aria-label="Will draft sections">
          {steps.map((label, index) => (
            <button key={label} type="button" aria-current={step === index ? "step" : undefined} onClick={() => setStep(index)} className={`will-stepper-item ${step === index ? "current" : index < step ? "complete" : "upcoming"}`}>
              <span className="will-stepper-number">{index < step ? "✓" : index + 1}</span>
              <span className="will-stepper-label"><small>{index < step ? "COMPLETE" : step === index ? "CURRENT" : `STEP ${String(index + 1).padStart(2, "0")}`}</small><strong>{label}</strong></span>
            </button>
          ))}
        </nav>}

        <div className={`will-workspace-main-grid ${workspaceView === "form" ? "form-only" : ""} ${workspaceView === "document" ? "document-only" : ""}`}>
        {workspaceView !== "document" && <div className="will-workspace-primary">
          <div className="rounded-xl border border-[#dce4df] bg-white p-6 shadow-sm sm:p-8">
            <div className="flex flex-wrap items-start justify-between gap-4 border-b border-[#edf1ee] pb-6">
              <div><p className="text-xs font-bold uppercase tracking-wider text-[#aa7d34]">Step {step + 1} of {steps.length}</p><h2 className="mt-2 text-2xl font-semibold text-[#17372f]">{steps[step]}</h2></div>
              <FilePenLine className="text-[#176b5b]" size={25} />
            </div>

            {message && <div className="mt-5 rounded-lg bg-[#d8f0e5] p-3 text-sm text-[#0f5548]" role="status">{message}</div>}
            {error && <div className="mt-5 rounded-lg bg-[#fff3ed] p-3 text-sm text-[#8c422c]" role="alert">{error}</div>}

            <div className="mt-6 rounded-xl border border-[#dce4df] bg-[#f8faf8] p-4">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <p className="text-xs font-bold uppercase tracking-wider text-[#aa7d34]">Draft format</p>
                  <p className="mt-1 text-sm text-[#60776e]">Choose the workflow that matches how you are preparing your will.</p>
                </div>
                <div className="flex flex-wrap gap-2">
                  <button type="button" onClick={() => setDraftSource("structured")} className={`rounded-lg px-3 py-2 text-xs font-semibold ${draftSource === "structured" ? "bg-[#176b5b] text-white" : "border border-[#dce4df] bg-white text-[#17372f]"}`}>Structured form</button>
                  <button type="button" onClick={() => setDraftSource("upload")} className={`rounded-lg px-3 py-2 text-xs font-semibold ${draftSource === "upload" ? "bg-[#176b5b] text-white" : "border border-[#dce4df] bg-white text-[#17372f]"}`}>Upload file</button>
                  <button type="button" onClick={() => setDraftSource("paste")} className={`rounded-lg px-3 py-2 text-xs font-semibold ${draftSource === "paste" ? "bg-[#176b5b] text-white" : "border border-[#dce4df] bg-white text-[#17372f]"}`}>Paste from Word</button>
                </div>
              </div>

              {draftSource === "upload" && <p className="mt-4 rounded-lg border border-[#dce4ef] bg-white p-3 text-xs leading-5 text-[#60708a]">Existing-will intake uses its own six-step process below. Export Word documents to PDF before upload; the secure document service accepts validated PDF files and records an integrity checksum.</p>}

              {draftSource === "paste" && (
                <section className="will-rich-editor" aria-label="Rich will document editor">
                  <div className="will-rich-toolbar" role="toolbar" aria-label="Document formatting">
                    <button type="button" aria-label="Bold" title="Bold" aria-pressed={pastedEditor?.isActive("bold") ?? false} disabled={!pastedEditor} onClick={() => pastedEditor?.chain().focus().toggleBold().run()}><Bold size={15} /></button>
                    <button type="button" aria-label="Italic" title="Italic" aria-pressed={pastedEditor?.isActive("italic") ?? false} disabled={!pastedEditor} onClick={() => pastedEditor?.chain().focus().toggleItalic().run()}><Italic size={15} /></button>
                    <button type="button" aria-label="Underline" title="Underline" aria-pressed={pastedEditor?.isActive("underline") ?? false} disabled={!pastedEditor} onClick={() => pastedEditor?.chain().focus().toggleUnderline().run()}><UnderlineIcon size={15} /></button>
                    <span />
                    <button type="button" aria-label="Bulleted list" title="Bulleted list" aria-pressed={pastedEditor?.isActive("bulletList") ?? false} disabled={!pastedEditor} onClick={() => pastedEditor?.chain().focus().toggleBulletList().run()}><ListIcon size={15} /></button>
                    <button type="button" aria-label="Numbered list" title="Numbered list" aria-pressed={pastedEditor?.isActive("orderedList") ?? false} disabled={!pastedEditor} onClick={() => pastedEditor?.chain().focus().toggleOrderedList().run()}><ListOrdered size={15} /></button>
                    <button type="button" aria-label="Heading" title="Heading" aria-pressed={pastedEditor?.isActive("heading") ?? false} disabled={!pastedEditor} onClick={() => pastedEditor?.chain().focus().toggleHeading({ level: 2 }).run()}><span className="will-rich-heading-icon">H</span></button>
                    <span />
                    <button type="button" aria-label="Undo" title="Undo" disabled={!pastedEditor?.can().undo()} onClick={() => pastedEditor?.chain().focus().undo().run()}><Undo2 size={15} /></button>
                    <button type="button" aria-label="Redo" title="Redo" disabled={!pastedEditor?.can().redo()} onClick={() => pastedEditor?.chain().focus().redo().run()}><Redo2 size={15} /></button>
                  </div>
                  <EditorContent editor={pastedEditor} className="will-rich-editor-content" />
                  <div className="will-rich-editor-footer"><span>Formatted text is saved with your draft.</span><span>{draftText.trim() ? draftText.trim().split(/\s+/).length : 0} words</span></div>
                </section>
              )}
            </div>

            {draftSource === "upload" && <section className="will-intake-panel" aria-labelledby="will-intake-title">
              <div className="will-intake-heading"><div><p>SECURE TESTAMENTARY INGESTION</p><h3 id="will-intake-title">Upload &amp; verify existing will</h3><span>Legal and statutory checks require qualified human review.</span></div><span className="will-intake-step-counter">STEP {uploadStep + 1} / {uploadSteps.length}</span></div>
              <nav className="will-stepper will-intake-stepper" aria-label="Existing will upload stages">
                {uploadSteps.map((label, index) => <button key={label} type="button" aria-current={uploadStep === index ? "step" : undefined} onClick={() => setUploadStep(index)} className={`will-stepper-item ${uploadStep === index ? "current" : index < uploadStep ? "complete" : "upcoming"}`}><span className="will-stepper-number">{index < uploadStep ? "✓" : index + 1}</span><span className="will-stepper-label"><small>{index < uploadStep ? "COMPLETE" : uploadStep === index ? "CURRENT" : `STEP ${String(index + 1).padStart(2, "0")}`}</small><strong>{label}</strong></span></button>)}
              </nav>

              {uploadStep === 0 && <div className="will-intake-stage">
               
<div>
  <h4>Testator identity</h4>
  <p>Save the testator&apos;s Sierra Leone National Identification Number and upload identity evidence to the private document vault.</p>
</div>

                <div className="grid gap-4 sm:grid-cols-2">
                  <Field label="Full legal name" value={testator.full_name ?? ""} onChange={(value) => updateSection("testator", { ...testator, full_name: value })} required />
                  <Field label="National Identification Number (NIN)" value={String(testator.national_id ?? "")} onChange={(value) => updateSection("testator", { ...testator, national_id: value })} required />
                </div>
                <label className="will-intake-file-label">Identity document (PDF, JPEG, or PNG)
                  <input type="file" accept=".pdf,.jpg,.jpeg,.png,application/pdf,image/jpeg,image/png" onChange={(event) => setIdentityDocumentFile(event.target.files?.[0] ?? null)} />
                </label>
                {uploadedIdentityDocument && <p className="will-intake-file-status"><CheckCircle2 size={15} /> Identity evidence stored · SHA-256 {uploadedIdentityDocument.checksum_sha256}</p>}
                <div className="will-intake-actions"><span /> <button type="button" disabled={uploadBusy} onClick={saveIdentityAndContinue}>{uploadBusy ? "Uploading identity..." : "Save identity & continue"} <ChevronRight size={15} /></button></div>
              </div>}

              {uploadStep === 1 && <div className="will-intake-stage">
                <div><h4>Cap. 25 review preparation</h4><p>This platform does not automatically determine compliance with the Wills Act (Cap. 25). Record the issues a qualified Sierra Leone legal practitioner should check.</p></div>
                <div className="will-intake-checklist">
                  <div><span><strong>Execution and signature</strong><small>Signature, date, and execution formalities require manual review.</small></span><b>MANUAL REVIEW</b></div>
                  <div><span><strong>Witness requirements</strong><small>Confirm applicable witness requirements with a legal practitioner.</small></span><b>MANUAL REVIEW</b></div>
                  <div><span><strong>Capacity and revocation</strong><small>Review capacity, prior wills, and revocation language with a practitioner.</small></span><b>MANUAL REVIEW</b></div>
                </div>
                <TextArea label="Notes for legal review" value={content.review_notes ?? ""} onChange={(value) => updateSection("review_notes", value)} hint="These notes are owner-provided and are not a compliance determination." />
                <div className="will-intake-actions"><button type="button" onClick={() => setUploadStep(0)}><ChevronLeft size={15} /> Previous</button><button type="button" onClick={() => setUploadStep(2)}>Continue <ChevronRight size={15} /></button></div>
              </div>}

              {uploadStep === 2 && <div className="will-intake-stage">
                <div><h4>Choose how to continue</h4><p>Keep this existing will as a private reference file, or switch to the guided seven-section editor to prepare a new structured draft.</p></div>
                <div className="will-intake-mode-grid"><article><FileCheck2 size={20} /><strong>Upload an executed will</strong><span>Store a signed will PDF and continue with owner-led review.</span><b>SELECTED WORKFLOW</b></article><button type="button" onClick={() => { setDraftSource("structured"); setStep(0); }}>Switch to guided drafting <ChevronRight size={15} /></button></div>
                <div className="will-intake-actions"><button type="button" onClick={() => setUploadStep(1)}><ChevronLeft size={15} /> Previous</button><button type="button" onClick={() => setUploadStep(3)}>Continue <ChevronRight size={15} /></button></div>
              </div>}

              {uploadStep === 3 && <div className="will-intake-stage">
                <div><h4>Upload the existing will</h4><p>The PDF is stored as a private will document. Its checksum is recorded and verified; OCR, clause extraction, and automatic legal review are not enabled.</p></div>
                <label className="will-intake-file-label">Signed will PDF (maximum 10 MB)
                  <input type="file" accept=".pdf,application/pdf" onChange={(event) => setUploadedWillFile(event.target.files?.[0] ?? null)} />
                </label>
                {uploadedWillFile && <p className="will-intake-file-status"><FileCheck2 size={15} /> Selected: {uploadedWillFile.name} · {(uploadedWillFile.size / 1_000_000).toFixed(1)} MB</p>}
                {uploadedWillDocument && <p className="will-intake-file-status"><CheckCircle2 size={15} /> Stored and integrity-checked · SHA-256 {uploadedWillDocument.checksum_sha256}</p>}
                <div className="will-intake-actions"><button type="button" onClick={() => setUploadStep(2)}><ChevronLeft size={15} /> Previous</button><button type="button" disabled={uploadBusy} onClick={uploadExistingWill}>{uploadBusy ? "Securely uploading..." : uploadedWillDocument ? "Continue" : "Upload PDF & continue"} <Upload size={15} /></button></div>
              </div>}

              {uploadStep === 4 && <div className="will-intake-stage">
                <div><h4>Witness verification</h4><p>Invite a witness or legal verifier. Sending an invitation does not complete attestation, notarization, or link the invite to a specific will.</p></div>
                <div className="grid gap-4 sm:grid-cols-2">
                  <label className="text-sm font-semibold text-[#183252]">Collaborator role<select value={collaboratorRole} onChange={(event) => setCollaboratorRole(event.target.value as InvitationRole)}><option value="WITNESS">Witness</option><option value="LAWYER_VERIFIER">Lawyer / Legal verifier</option></select></label>
                  <Field label="Email address" value={collaboratorEmail} onChange={setCollaboratorEmail} type="email" />
                  <Field label="First name" value={collaboratorFirstName} onChange={setCollaboratorFirstName} />
                  <Field label="Last name" value={collaboratorLastName} onChange={setCollaboratorLastName} />
                </div>
                <label className="text-sm font-semibold text-[#183252]">Personal message<textarea rows={3} value={collaboratorMessage} onChange={(event) => setCollaboratorMessage(event.target.value)} /></label>
                <div className="will-intake-actions"><button type="button" onClick={() => setUploadStep(3)}><ChevronLeft size={15} /> Previous</button><div><button type="button" disabled={invitingCollaborator || !collaboratorEmail.trim()} onClick={inviteCollaborator}>{invitingCollaborator ? "Sending..." : "Send invitation"}</button><button type="button" onClick={() => setUploadStep(5)}>Continue <ChevronRight size={15} /></button></div></div>
              </div>}

              {uploadStep === 5 && <div className="will-intake-stage">
                <div><h4>Legal seal &amp; registry</h4><p>Review your uploaded file and save the owner draft. Legal sealing, notarial attestation, and registry anchoring are not available in this module yet.</p></div>
                <div className="will-intake-summary"><div><span>Draft</span><strong>{title}</strong></div><div><span>Testator NIN</span><strong>{String(testator.national_id ?? "Not provided")}</strong></div><div><span>Identity evidence</span><strong>{uploadedIdentityDocument ? "Stored; integrity check recorded" : "Not uploaded"}</strong></div><div><span>Existing will</span><strong>{uploadedWillDocument ? uploadedWillDocument.original_filename : "Not uploaded"}</strong></div><div><span>Legal seal / registry</span><strong>Not available</strong></div></div>
                <div className="will-intake-warning"><AlertTriangle size={17} /><span>Saving this draft does not certify legal validity or finalize, seal, or register the will.</span></div>
                <div className="will-intake-actions"><button type="button" onClick={() => setUploadStep(4)}><ChevronLeft size={15} /> Previous</button><button type="button" disabled={busy} onClick={() => void saveDraft()}><Save size={15} /> {busy ? "Saving..." : "Save draft"}</button></div>
              </div>}
            </section>}

            {draftSource !== "upload" && <div className="mt-5 flex flex-wrap gap-3">
              <button type="button" onClick={downloadGeneratedWill} className="rounded-lg border border-[#dce4df] bg-white px-3 py-2 text-sm font-semibold text-[#17372f]">Download .txt</button>
              <button type="button" onClick={printGeneratedWill} className="rounded-lg border border-[#dce4df] bg-white px-3 py-2 text-sm font-semibold text-[#17372f]">Print / Save as PDF</button>
            </div>}

            {draftSource !== "upload" && <form className="mt-6" onSubmit={saveDraft}>
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

              {step === 5 && <div className="grid gap-5">
                <div className="rounded-lg border border-[#edf1ee] bg-[#fffaf0] p-4 text-sm leading-6 text-[#6d572c]">
                  Select the people who will witness or verify your will while you are still drafting it. They will receive an invitation and only become active after acceptance.
                </div>
                <div className="grid gap-4 sm:grid-cols-2">
                  <label className="text-sm font-semibold text-[#17372f]">Collaborator role
                    <select value={collaboratorRole} onChange={(event) => setCollaboratorRole(event.target.value as InvitationRole)} className="mt-1.5 w-full rounded-lg border border-[#dce4df] bg-white p-2.5 font-normal">
                      <option value="WITNESS">Witness</option>
                      <option value="LAWYER_VERIFIER">Lawyer / Legal verifier</option>
                    </select>
                  </label>
                  <label className="text-sm font-semibold text-[#17372f]">Email address
                    <input type="email" value={collaboratorEmail} onChange={(event) => setCollaboratorEmail(event.target.value)} className="mt-1.5 w-full rounded-lg border border-[#dce4df] p-2.5 font-normal" placeholder="collaborator@example.com" />
                  </label>
                  <Field label="First name" value={collaboratorFirstName} onChange={setCollaboratorFirstName} />
                  <Field label="Last name" value={collaboratorLastName} onChange={setCollaboratorLastName} />
                </div>
                <label className="text-sm font-semibold text-[#17372f]">Personal message
                  <textarea rows={3} value={collaboratorMessage} onChange={(event) => setCollaboratorMessage(event.target.value)} className="mt-1.5 w-full rounded-lg border border-[#dce4df] p-2.5 font-normal" placeholder="Please review and confirm my testamentary instructions." />
                </label>
                <div className="flex justify-end">
                  <button type="button" onClick={inviteCollaborator} disabled={invitingCollaborator || !collaboratorEmail.trim()} className="rounded-lg bg-[#176b5b] px-4 py-2 text-sm font-semibold text-white disabled:opacity-50">{invitingCollaborator ? "Sending..." : "Send invitation"}</button>
                </div>
              </div>}

              {step === 6 && <div className="grid gap-5"><Field label="Draft title" value={title} onChange={setTitle} required /><Review label="Testator" value={testator.full_name || "Not provided"} /><Review label="Executor" value={executor.full_name || "Not provided"} /><Review label="Beneficiaries" value={beneficiaries.map((item) => item.full_name).join(", ") || "Not provided"} /><Review label="Specific gifts" value={gifts.length ? `${gifts.length} gift instruction(s)` : "None recorded"} /><Review label="Legal collaborators" value={collaboratorRole ? `${collaboratorRole === "WITNESS" ? "Witness" : "Legal verifier"}${collaboratorEmail ? ` · ${collaboratorEmail}` : ""}` : "No collaborator selected"} /><div className="rounded-lg bg-[#fffaf0] p-4 text-sm leading-6 text-[#6d572c]">This is a product draft for your review. It is not legal advice and does not complete witnessing, notarization, legal verification, release, blockchain registration, or AI analysis.</div></div>}

              <div className="mt-8 flex flex-wrap justify-between gap-3 border-t border-[#edf1ee] pt-5"><button type="button" disabled={step === 0} onClick={() => setStep((current) => current - 1)} className="inline-flex items-center gap-2 rounded-lg border border-[#dce4df] px-4 py-2 text-sm font-semibold text-[#60776e] disabled:opacity-40"><ChevronLeft size={16} /> Previous</button><div className="flex gap-3"><button type="submit" disabled={busy} className="inline-flex items-center gap-2 rounded-lg border border-[#176b5b] px-4 py-2 text-sm font-semibold text-[#176b5b]"><Save size={16} /> {busy ? "Saving..." : "Save draft"}</button>{step < steps.length - 1 ? <button type="button" onClick={() => setStep((current) => current + 1)} className="inline-flex items-center gap-2 rounded-lg bg-[#176b5b] px-4 py-2 text-sm font-semibold text-white">Next <ChevronRight size={16} /></button> : <button type="button" disabled={busy || !selectedWillId} onClick={finalize} className="inline-flex items-center gap-2 rounded-lg bg-[#8c5e15] px-4 py-2 text-sm font-semibold text-white disabled:opacity-40"><Check size={16} /> Finalize</button>}</div></div>
            </form>}
          </div>

          <section className="mt-6 rounded-xl border border-[#dce4df] bg-white p-6 shadow-sm"><div className="flex items-center justify-between gap-3"><h2 className="text-lg font-semibold text-[#17372f]">Saved drafts</h2><button type="button" onClick={startNew} className="text-sm font-bold text-[#176b5b]">Start new</button></div>{wills.length === 0 ? <p className="mt-4 text-sm text-[#809189]">No saved drafts yet.</p> : <div className="mt-4 grid gap-2">{wills.map((will) => <button type="button" key={will.id} onClick={() => selectWill(will)} className={`flex items-center justify-between rounded-lg border p-3 text-left ${selectedWillId === will.id ? "border-[#176b5b] bg-[#f5faf7]" : "border-[#edf1ee]"}`}><span><span className="block text-sm font-semibold text-[#17372f]">{will.title}</span><span className="text-xs text-[#809189]">Version {will.version}</span></span><span className="text-xs font-bold text-[#176b5b]">{will.status}</span></button>)}</div>}</section>
          <div id="beneficiaries">
            {selectedWillId !== null ? (() => {
              const selectedWill = wills.find((will) => will.id === selectedWillId);
              return selectedWill ? <WillBeneficiaryManager key={selectedWill.id} willId={selectedWill.id} willStatus={selectedWill.status} /> : null;
            })() : <p className="mt-6 rounded-lg border border-[#dce4df] bg-white p-4 text-sm text-[#60776e]">Select a saved will to manage its beneficiary relationships.</p>}
          </div>
          {(profileUser?.role === 'OWNER' || profileUser?.role === 'MEMBER') && selectedWillId !== null && (() => {
            const selectedWill = wills.find((will) => will.id === selectedWillId);
            return selectedWill ? <WillDocumentManager key={`documents-${selectedWill.id}`} willId={selectedWill.id} willStatus={selectedWill.status} /> : null;
          })()}
        </div>}
        {workspaceView !== "form" && <aside className="will-workspace-preview">
          <div className="will-preview-heading"><span className="will-preview-live-dot" /><div><h2>Live legal structure preview</h2><p>Updates from the information entered so far</p></div><span className="will-preview-version">DRAFT</span></div>
          {draftSource === "upload" && uploadedWillDocument ? <div className="will-upload-preview"><FileCheck2 size={20} /><strong>{uploadedWillDocument.original_filename}</strong><small>Private file · integrity check recorded · OCR not available</small></div> : <article className="will-preview-paper">
            <p className="will-preview-jurisdiction">REPUBLIC OF SIERRA LEONE<br />IN THE MATTER OF THE WILLS ACT (CAP. 25)</p>
            <h3>LAST WILL AND TESTAMENT</h3>
            <h4>OF {testator.full_name?.trim() || "TESTATOR NAME"}</h4>
            <p className="will-preview-id">{title || "Untitled draft"} · {String(testator.national_id ?? "NIN not entered")}</p>
            <div className="will-preview-rule" />
            <PreviewClause title="TESTATOR DETAILS" value={[testator.address, testator.occupation].filter(Boolean).join(" · ")} empty="Add address and occupation in Your details." />
            <PreviewClause title="FAMILY AND DEPENDANTS" value={[family.spouse_or_partner, ...(family.children ?? []).map((item) => item.full_name), ...(family.dependants ?? []).map((item) => item.full_name)].filter(Boolean).join(" · ")} empty="Add family information in Family." />
            <PreviewClause title="EXECUTOR / PERSONAL REPRESENTATIVE" value={[executor.full_name, executor.relationship].filter(Boolean).join(" · ")} empty="Add an executor in Appointments." />
            <PreviewClause title="BENEFICIARIES AND GIFTS" value={[...beneficiaries.map((item) => item.full_name), ...gifts.map((item) => `${item.beneficiary_name}: ${item.description}`)].filter(Boolean).join(" · ")} empty="Add beneficiaries and gifts in their sections." />
            {draftSource === "paste" && draftText.trim() && <section className="will-preview-clause"><h5>PASTED WILL TEXT</h5><p>{draftText.slice(0, 1600)}{draftText.length > 1600 ? "…" : ""}</p></section>}
            <p className="will-preview-disclaimer">Draft preview only. This is not a legal determination or a final executed will.</p>
          </article>}

          <section className="will-progress-panel" aria-labelledby="will-progress-title">
            <div className="will-progress-heading"><div><h3 id="will-progress-title">Draft information chart</h3><p>{progressEntered} of {progressAvailable} information fields entered</p></div><span>{Math.round((progressEntered / progressAvailable) * 100)}%</span></div>
            <div className="will-progress-chart" role="group" aria-label="Information entered by will section">
              {draftProgress.map((item) => {
                const percentage = Math.round((item.value / item.total) * 100);
                return <button key={item.label} type="button" aria-label={`${item.label}: ${item.value} of ${item.total} fields entered. Go to section.`} aria-current={step === item.step ? "step" : undefined} onClick={() => { setDraftSource("structured"); setStep(item.step); setWorkspaceView("split"); }} className="will-progress-bar-item">
                  <span className="will-progress-bar-value">{item.value}/{item.total}</span><span className="will-progress-track"><span style={{ height: `${Math.max(percentage, 5)}%` }} /></span><small>{item.label}</small>
                </button>;
              })}
            </div>
            <p className="will-progress-disclaimer">Information coverage only. It does not indicate legal compliance or validity.</p>
          </section>
          <div className="will-workspace-privacy"><LockKeyhole size={14} /><span>Drafts are private to your account. Witnessing, legal verification, and registry steps require their own completed workflows.</span></div>
        </aside>}
        </div>
      </section>
      </div>
    </DashboardShell>
  );
}

function Field({ label, value, onChange, required = false, readOnly = false, type = "text" }: { label: string; value: string; onChange: (value: string) => void; required?: boolean; readOnly?: boolean; type?: string }) {
  return <label className="text-sm font-semibold text-[#17372f]">{label}<input type={type} required={required} readOnly={readOnly} value={value} onChange={(event) => onChange(event.target.value)} className={`mt-1.5 w-full rounded-lg border border-[#dce4df] p-2.5 font-normal ${readOnly ? "bg-[#f5f7f6] text-[#809189]" : "bg-white"}`} /></label>;
}

function TextArea({ label, value, onChange, hint }: { label: string; value: string; onChange: (value: string) => void; hint?: string }) {
  return <label className="text-sm font-semibold text-[#17372f]">{label}<textarea rows={5} value={value} onChange={(event) => onChange(event.target.value)} className="mt-1.5 w-full rounded-lg border border-[#dce4df] p-2.5 font-normal" />{hint && <span className="mt-1 block text-xs font-normal text-[#809189]">{hint}</span>}</label>;
}

function Review({ label, value }: { label: string; value: string }) {
  return <div className="rounded-lg border border-[#edf1ee] p-4"><p className="text-xs font-bold uppercase tracking-wider text-[#809189]">{label}</p><p className="mt-1 text-sm text-[#17372f]">{value}</p></div>;
}

function PreviewClause({ title, value, empty }: { title: string; value: string; empty: string }) {
  return <section className="will-preview-clause"><h5>{title}</h5><p>{value || empty}</p></section>;
}
