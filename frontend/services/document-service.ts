import { apiDownload, apiRequest } from '@/services/auth-service';
import type { DocumentIntegrityCheck, DocumentType, WillDocument, WillDocumentsResponse } from '@/types/documents';

export function getWillDocuments(willId: number): Promise<WillDocumentsResponse> {
  return apiRequest(`/wills/${willId}/documents/`);
}

export function uploadWillDocument(willId: number, file: File, documentType: DocumentType, description: string) {
  const body = new FormData();
  body.set('file', file);
  body.set('document_type', documentType);
  body.set('description', description);
  return apiRequest<{ data: WillDocument; message: string }>(`/wills/${willId}/documents/`, { method: 'POST', body });
}

export function updateWillDocument(willId: number, documentId: number, payload: { document_type?: DocumentType; description?: string }) {
  return apiRequest<{ data: WillDocument; message: string }>(`/wills/${willId}/documents/${documentId}/`, {
    method: 'PATCH',
    body: JSON.stringify(payload),
  });
}

export function replaceWillDocument(willId: number, documentId: number, file: File) {
  const body = new FormData();
  body.set('file', file);
  return apiRequest<{ data: WillDocument; message: string }>(`/wills/${willId}/documents/${documentId}/replace/`, {
    method: 'POST',
    body,
  });
}

export function deleteWillDocument(willId: number, documentId: number) {
  return apiRequest<{ data: { id: number; status: string }; message: string }>(`/wills/${willId}/documents/${documentId}/`, {
    method: 'DELETE',
  });
}

export function downloadWillDocument(willId: number, documentId: number): Promise<Blob> {
  return apiDownload(`/wills/${willId}/documents/${documentId}/download/`);
}

export function checkWillDocumentIntegrity(willId: number, documentId: number) {
  return apiRequest<{ data: DocumentIntegrityCheck; message: string }>(`/wills/${willId}/documents/${documentId}/integrity-checks/`, {
    method: 'POST',
  });
}

export function getWillDocumentIntegrityHistory(willId: number, documentId: number) {
  return apiRequest<{ data: DocumentIntegrityCheck[] }>(`/wills/${willId}/documents/${documentId}/integrity-checks/`);
}

export function getWillDocumentVersions(willId: number, documentId: number) {
  return apiRequest<{ data: WillDocument[] }>(`/wills/${willId}/documents/${documentId}/versions/`);
}