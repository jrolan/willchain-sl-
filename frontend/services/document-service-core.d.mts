type ApiRequest = <T = unknown>(path: string, init?: RequestInit) => Promise<T>;
type ApiDownload = (path: string) => Promise<Blob>;

export function createDocumentService(apiRequest: ApiRequest, apiDownload: ApiDownload): {
  getWillDocuments: <T = unknown>(willId: number) => Promise<T>;
  uploadWillDocument: <T = unknown>(willId: number, file: Blob, documentType: string, description: string) => Promise<T>;
  updateWillDocument: <T = unknown>(willId: number, documentId: number, payload: object) => Promise<T>;
  replaceWillDocument: <T = unknown>(willId: number, documentId: number, file: Blob) => Promise<T>;
  deleteWillDocument: <T = unknown>(willId: number, documentId: number) => Promise<T>;
  downloadWillDocument(willId: number, documentId: number): Promise<Blob>;
  checkWillDocumentIntegrity: <T = unknown>(willId: number, documentId: number) => Promise<T>;
  getWillDocumentIntegrityHistory: <T = unknown>(willId: number, documentId: number) => Promise<T>;
  getWillDocumentVersions: <T = unknown>(willId: number, documentId: number) => Promise<T>;
};