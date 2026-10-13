import { apiDownload, apiRequest } from '@/services/auth-service';
import type { DocumentIntegrityCheck, DocumentType, WillDocument, WillDocumentsResponse } from '@/types/documents';
import { createDocumentService } from './document-service-core.mjs';

const documentService = createDocumentService(apiRequest, apiDownload);

export const getWillDocuments = (willId: number): Promise<WillDocumentsResponse> =>
  documentService.getWillDocuments<WillDocumentsResponse>(willId);

export const uploadWillDocument = (willId: number, file: File, documentType: DocumentType, description: string) =>
  documentService.uploadWillDocument<{ data: WillDocument; message: string }>(willId, file, documentType, description);

export const updateWillDocument = (
  willId: number,
  documentId: number,
  payload: { document_type?: DocumentType; description?: string },
) => documentService.updateWillDocument<{ data: WillDocument; message: string }>(willId, documentId, payload);

export const replaceWillDocument = (willId: number, documentId: number, file: File) =>
  documentService.replaceWillDocument<{ data: WillDocument; message: string }>(willId, documentId, file);

export const deleteWillDocument = (willId: number, documentId: number) =>
  documentService.deleteWillDocument<{ data: { id: number; status: string }; message: string }>(willId, documentId);

export const downloadWillDocument = (willId: number, documentId: number): Promise<Blob> =>
  documentService.downloadWillDocument(willId, documentId);

export const checkWillDocumentIntegrity = (willId: number, documentId: number) =>
  documentService.checkWillDocumentIntegrity<{ data: DocumentIntegrityCheck; message: string }>(willId, documentId);

export const getWillDocumentIntegrityHistory = (willId: number, documentId: number) =>
  documentService.getWillDocumentIntegrityHistory<{ data: DocumentIntegrityCheck[] }>(willId, documentId);

export const getWillDocumentVersions = (willId: number, documentId: number) =>
  documentService.getWillDocumentVersions<{ data: WillDocument[] }>(willId, documentId);