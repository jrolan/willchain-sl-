export function createDocumentService(apiRequest, apiDownload) {
  return {
    getWillDocuments(willId) {
      return apiRequest(`/wills/${willId}/documents/`);
    },
    uploadWillDocument(willId, file, documentType, description) {
      const body = new FormData();
      body.set('file', file);
      body.set('document_type', documentType);
      body.set('description', description);
      return apiRequest(`/wills/${willId}/documents/`, { method: 'POST', body });
    },
    updateWillDocument(willId, documentId, payload) {
      return apiRequest(`/wills/${willId}/documents/${documentId}/`, {
        method: 'PATCH',
        body: JSON.stringify(payload),
      });
    },
    replaceWillDocument(willId, documentId, file) {
      const body = new FormData();
      body.set('file', file);
      return apiRequest(`/wills/${willId}/documents/${documentId}/replace/`, { method: 'POST', body });
    },
    deleteWillDocument(willId, documentId) {
      return apiRequest(`/wills/${willId}/documents/${documentId}/`, { method: 'DELETE' });
    },
    downloadWillDocument(willId, documentId) {
      return apiDownload(`/wills/${willId}/documents/${documentId}/download/`);
    },
    checkWillDocumentIntegrity(willId, documentId) {
      return apiRequest(`/wills/${willId}/documents/${documentId}/integrity-checks/`, { method: 'POST' });
    },
    getWillDocumentIntegrityHistory(willId, documentId) {
      return apiRequest(`/wills/${willId}/documents/${documentId}/integrity-checks/`);
    },
    getWillDocumentVersions(willId, documentId) {
      return apiRequest(`/wills/${willId}/documents/${documentId}/versions/`);
    },
  };
}