"use client";

import { useEffect, useState } from 'react';
import { Check, Clock3, Download, FileCheck2, FilePlus2, Pencil, RefreshCw, Trash2, X } from 'lucide-react';

import {
  checkWillDocumentIntegrity,
  deleteWillDocument,
  downloadWillDocument,
  getWillDocuments,
  getWillDocumentIntegrityHistory,
  getWillDocumentVersions,
  replaceWillDocument,
  updateWillDocument,
  uploadWillDocument,
} from '@/services/document-service';
import type { DocumentIntegrityCheck, DocumentType, WillDocument } from '@/types/documents';
import type { WillStatus } from '@/types/wills';

const documentTypes: Array<{ value: DocumentType; label: string }> = [
  { value: 'IDENTITY', label: 'Identity document' },
  { value: 'PASSPORT', label: 'Passport' },
  { value: 'LAND_PROPERTY', label: 'Land or property record' },
  { value: 'MARRIAGE_CERTIFICATE', label: 'Marriage certificate' },
  { value: 'BIRTH_CERTIFICATE', label: 'Birth certificate' },
  { value: 'OTHER', label: 'Other supporting evidence' },
];

function formatSize(size: number) {
  return size < 1_000_000 ? `${Math.ceil(size / 1000)} KB` : `${(size / 1_000_000).toFixed(1)} MB`;
}

function errorMessage(error: unknown) {
  return error instanceof Error ? error.message : 'The document request could not be completed.';
}

export function WillDocumentManager({ willId, willStatus }: { willId: number; willStatus: WillStatus }) {
  const [documents, setDocuments] = useState<WillDocument[]>([]);
  const [maxFileSize, setMaxFileSize] = useState(0);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [documentType, setDocumentType] = useState<DocumentType>('IDENTITY');
  const [description, setDescription] = useState('');
  const [editingId, setEditingId] = useState<number | null>(null);
  const [editType, setEditType] = useState<DocumentType>('IDENTITY');
  const [editDescription, setEditDescription] = useState('');
  const [checks, setChecks] = useState<Record<number, DocumentIntegrityCheck[]>>({});
  const [versions, setVersions] = useState<Record<number, WillDocument[]>>({});
  const [openHistory, setOpenHistory] = useState<Record<number, boolean>>({});
  const [busyId, setBusyId] = useState<number | 'upload' | null>(null);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');

  async function refreshDocuments() {
    const response = await getWillDocuments(willId);
    setDocuments(response.data);
    setMaxFileSize(response.max_file_size_bytes);
  }

  useEffect(() => {
    let mounted = true;
    getWillDocuments(willId)
      .then((response) => {
        if (mounted) {
          setDocuments(response.data);
          setMaxFileSize(response.max_file_size_bytes);
        }
      })
      .catch((loadError: unknown) => { if (mounted) setError(errorMessage(loadError)); });
    return () => { mounted = false; };
  }, [willId]);

  function validateFile(file: File) {
    const extension = file.name.split('.').pop()?.toLowerCase();
    if (!['pdf', 'jpg', 'jpeg', 'png'].includes(extension ?? '')) return 'Choose a PDF, JPEG, or PNG file.';
    if (maxFileSize > 0 && file.size > maxFileSize) return `The file exceeds the ${formatSize(maxFileSize)} limit.`;
    if (file.size === 0) return 'Empty files are not accepted.';
    return '';
  }

  async function runAction(action: () => Promise<unknown>, successMessage: string) {
    setError('');
    setMessage('');
    try {
      await action();
      await refreshDocuments();
      setMessage(successMessage);
    } catch (actionError) {
      setError(errorMessage(actionError));
    } finally {
      setBusyId(null);
    }
  }

  async function submitUpload() {
    if (!selectedFile) return;
    const validationError = validateFile(selectedFile);
    if (validationError) { setError(validationError); return; }
    setBusyId('upload');
    await runAction(
      () => uploadWillDocument(willId, selectedFile, documentType, description),
      'Document uploaded.',
    );
    setSelectedFile(null);
    setDescription('');
  }

  async function download(document: WillDocument) {
    setBusyId(document.id);
    setError('');
    try {
      const blob = await downloadWillDocument(willId, document.id);
      const url = URL.createObjectURL(blob);
      const anchor = window.document.createElement('a');
      anchor.href = url;
      anchor.download = document.original_filename;
      anchor.click();
      URL.revokeObjectURL(url);
    } catch (downloadError) {
      setError(errorMessage(downloadError));
    } finally {
      setBusyId(null);
    }
  }

  async function runIntegrityCheck(documentId: number) {
    setBusyId(documentId);
    setError('');
    try {
      await checkWillDocumentIntegrity(willId, documentId);
      const history = await getWillDocumentIntegrityHistory(willId, documentId);
      setChecks((current) => ({ ...current, [documentId]: history.data }));
      await refreshDocuments();
      setMessage('Integrity check recorded.');
    } catch (checkError) {
      setError(errorMessage(checkError));
    } finally {
      setBusyId(null);
    }
  }

  async function toggleHistory(documentId: number) {
    const opening = !openHistory[documentId];
    setOpenHistory((current) => ({ ...current, [documentId]: opening }));
    if (!opening) return;
    setBusyId(documentId);
    setError('');
    try {
      const [versionResponse, checkResponse] = await Promise.all([
        getWillDocumentVersions(willId, documentId),
        getWillDocumentIntegrityHistory(willId, documentId),
      ]);
      setVersions((current) => ({ ...current, [documentId]: versionResponse.data }));
      setChecks((current) => ({ ...current, [documentId]: checkResponse.data }));
    } catch (historyError) {
      setError(errorMessage(historyError));
      setOpenHistory((current) => ({ ...current, [documentId]: false }));
    } finally {
      setBusyId(null);
    }
  }

  async function saveMetadata(documentId: number) {
    setBusyId(documentId);
    await runAction(
      () => updateWillDocument(willId, documentId, { document_type: editType, description: editDescription }),
      'Document metadata updated.',
    );
    setEditingId(null);
  }

  async function replaceFile(document: WillDocument, file: File | undefined) {
    if (!file) return;
    const validationError = validateFile(file);
    if (validationError) { setError(validationError); return; }
    setBusyId(document.id);
    await runAction(() => replaceWillDocument(willId, document.id, file), 'New document version created.');
  }

  async function softDelete(document: WillDocument) {
    if (!window.confirm(`Soft-delete ${document.original_filename}? Its audit and version history will be retained.`)) return;
    setBusyId(document.id);
    await runAction(() => deleteWillDocument(willId, document.id), 'Document soft-deleted.');
  }

  const editable = willStatus === 'DRAFT';

  return (
    <section className="mt-6 rounded-xl border border-[#dce4df] bg-white p-6 shadow-sm" aria-labelledby="will-documents-heading">
      <div className="flex flex-wrap items-start justify-between gap-3 border-b border-[#edf1ee] pb-4">
        <div>
          <h2 id="will-documents-heading" className="text-lg font-semibold text-[#17372f]">Supporting documents</h2>
          <p className="mt-1 text-sm text-[#60776e]">Private files for this will. Document content is available only to the will owner.</p>
        </div>
        <span className="text-xs font-bold uppercase tracking-wider text-[#60776e]">{willStatus}</span>
      </div>

      {message && <p className="mt-4 rounded-lg bg-[#d8f0e5] p-3 text-sm text-[#0f5548]" role="status">{message}</p>}
      {error && <p className="mt-4 rounded-lg bg-[#fff3ed] p-3 text-sm text-[#8c422c]" role="alert">{error}</p>}

      {editable && <div className="mt-5 grid gap-3 border-b border-[#edf1ee] pb-5 sm:grid-cols-[1fr_1fr_1.3fr_auto] sm:items-end">
        <label className="text-sm font-semibold text-[#17372f]">Purpose
          <select value={documentType} onChange={(event) => setDocumentType(event.target.value as DocumentType)} className="mt-1.5 w-full rounded-lg border border-[#dce4df] bg-white p-2.5 font-normal">
            {documentTypes.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}
          </select>
        </label>
        <label className="text-sm font-semibold text-[#17372f]">File
          <input type="file" accept=".pdf,.jpg,.jpeg,.png,application/pdf,image/jpeg,image/png" onChange={(event) => setSelectedFile(event.target.files?.[0] ?? null)} className="mt-1.5 block w-full text-xs font-normal" />
        </label>
        <label className="text-sm font-semibold text-[#17372f]">Description
          <input value={description} onChange={(event) => setDescription(event.target.value)} maxLength={255} className="mt-1.5 w-full rounded-lg border border-[#dce4df] p-2.5 font-normal" />
        </label>
        <button type="button" onClick={submitUpload} disabled={!selectedFile || busyId !== null} className="inline-flex items-center justify-center gap-2 rounded-lg bg-[#176b5b] px-4 py-2.5 text-sm font-semibold text-white disabled:opacity-50">
          <FilePlus2 size={16} /> {busyId === 'upload' ? 'Uploading...' : 'Upload'}
        </button>
        <p className="text-xs text-[#809189] sm:col-span-4">PDF, JPEG, or PNG. Maximum {maxFileSize ? formatSize(maxFileSize) : '10 MB'}.</p>
      </div>}

      {documents.length === 0 ? <p className="mt-5 text-sm text-[#809189]">No supporting documents.</p> : <ul className="divide-y divide-[#edf1ee]">
        {documents.map((document) => {
          const latestCheck = checks[document.id]?.[0] ?? document.latest_integrity_check;
          return <li key={document.id} className="py-5">
            <div className="flex flex-wrap items-start justify-between gap-4">
              <div className="min-w-0 flex-1">
                <p className="break-all text-sm font-semibold text-[#17372f]">{document.original_filename} <span className="ml-1 font-normal text-[#809189]">v{document.version}</span></p>
                <p className="mt-1 text-xs text-[#60776e]">{documentTypes.find((item) => item.value === document.document_type)?.label ?? document.document_type} · {formatSize(document.file_size)} · {new Date(document.created_at).toLocaleString()}</p>
                {document.description && <p className="mt-1 text-sm text-[#60776e]">{document.description}</p>}
                <p className="mt-1 break-all font-mono text-[11px] text-[#809189]">SHA-256 {document.checksum_sha256}</p>
                <p className="mt-2 inline-flex items-center gap-1 text-xs font-semibold text-[#60776e]">
                  <FileCheck2 size={14} /> Integrity: {latestCheck ? `${latestCheck.result} · ${new Date(latestCheck.created_at).toLocaleString()}` : 'Not checked'}
                </p>
                {latestCheck?.result === 'MISMATCH' && <p className="mt-1 text-xs font-semibold text-[#8c422c]">Stored content differs from the accepted checksum. The original checksum is retained.</p>}
              </div>
              <div className="flex flex-wrap items-center gap-2">
                <button type="button" title="Download document" aria-label={`Download ${document.original_filename}`} disabled={busyId !== null} onClick={() => download(document)} className="grid h-9 w-9 place-items-center rounded-lg border border-[#dce4df] text-[#176b5b] disabled:opacity-50"><Download size={16} /></button>
                <button type="button" title="Verify integrity" aria-label={`Verify integrity of ${document.original_filename}`} disabled={busyId !== null} onClick={() => runIntegrityCheck(document.id)} className="grid h-9 w-9 place-items-center rounded-lg border border-[#dce4df] text-[#176b5b] disabled:opacity-50"><Check size={16} /></button>
                <button type="button" title="View version and integrity history" aria-label={`View history for ${document.original_filename}`} disabled={busyId !== null} onClick={() => toggleHistory(document.id)} className="grid h-9 w-9 place-items-center rounded-lg border border-[#dce4df] text-[#176b5b] disabled:opacity-50"><Clock3 size={16} /></button>
                {editable && <>
                  <button type="button" title="Edit metadata" aria-label={`Edit ${document.original_filename} metadata`} disabled={busyId !== null} onClick={() => { setEditingId(document.id); setEditType(document.document_type); setEditDescription(document.description); }} className="grid h-9 w-9 place-items-center rounded-lg border border-[#dce4df] text-[#176b5b]"><Pencil size={16} /></button>
                  <label title="Replace with a new version" className="grid h-9 w-9 cursor-pointer place-items-center rounded-lg border border-[#dce4df] text-[#176b5b]">
                    <RefreshCw size={16} /><span className="sr-only">Replace {document.original_filename}</span>
                    <input type="file" accept=".pdf,.jpg,.jpeg,.png,application/pdf,image/jpeg,image/png" disabled={busyId !== null} onChange={(event) => { void replaceFile(document, event.target.files?.[0]); event.target.value = ''; }} className="sr-only" />
                  </label>
                  <button type="button" title="Soft-delete document" aria-label={`Soft-delete ${document.original_filename}`} disabled={busyId !== null} onClick={() => softDelete(document)} className="grid h-9 w-9 place-items-center rounded-lg border border-[#ead6ce] text-[#8c422c]"><Trash2 size={16} /></button>
                </>}
              </div>
            </div>
            {openHistory[document.id] && <div className="mt-4 grid gap-4 border-t border-[#edf1ee] pt-4 sm:grid-cols-2">
              <div><h3 className="text-xs font-bold uppercase text-[#60776e]">Versions</h3><ul className="mt-2 grid gap-2">{(versions[document.id] ?? []).map((version) => <li key={version.id} className="break-all text-xs text-[#60776e]">v{version.version} · {version.status} · {new Date(version.created_at).toLocaleString()}</li>)}</ul></div>
              <div><h3 className="text-xs font-bold uppercase text-[#60776e]">Integrity checks</h3><ul className="mt-2 grid gap-2">{(checks[document.id] ?? []).length === 0 ? <li className="text-xs text-[#809189]">No checks recorded.</li> : (checks[document.id] ?? []).map((check) => <li key={check.id} className="text-xs text-[#60776e]">{check.result} · {new Date(check.created_at).toLocaleString()}</li>)}</ul></div>
            </div>}
            {editingId === document.id && <div className="mt-4 grid gap-3 rounded-lg bg-[#f5f8f6] p-4 sm:grid-cols-[1fr_1fr_auto_auto] sm:items-end">
              <label className="text-sm font-semibold text-[#17372f]">Purpose<select value={editType} onChange={(event) => setEditType(event.target.value as DocumentType)} className="mt-1 w-full rounded-lg border border-[#dce4df] bg-white p-2 font-normal">{documentTypes.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}</select></label>
              <label className="text-sm font-semibold text-[#17372f]">Description<input value={editDescription} onChange={(event) => setEditDescription(event.target.value)} maxLength={255} className="mt-1 w-full rounded-lg border border-[#dce4df] p-2 font-normal" /></label>
              <button type="button" onClick={() => saveMetadata(document.id)} disabled={busyId !== null} className="inline-flex items-center justify-center gap-1 rounded-lg bg-[#176b5b] px-3 py-2 text-sm font-semibold text-white"><Check size={15} /> Save</button>
              <button type="button" onClick={() => setEditingId(null)} className="inline-flex items-center justify-center gap-1 rounded-lg border border-[#dce4df] px-3 py-2 text-sm font-semibold text-[#60776e]"><X size={15} /> Cancel</button>
            </div>}
          </li>;
        })}
      </ul>}
    </section>
  );
}