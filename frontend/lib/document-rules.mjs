export const DOCUMENT_MAX_BYTES = 10_000_000;

const supportedExtensions = new Set(['pdf', 'jpg', 'jpeg', 'png']);
const willStatuses = new Set(['DRAFT', 'FINALIZED', 'ARCHIVED']);

export function validateDocumentFile(file, maxBytes = DOCUMENT_MAX_BYTES) {
  if (!file || typeof file.name !== 'string' || !Number.isFinite(file.size)) {
    return 'Choose a valid document file.';
  }

  const extension = file.name.split('.').pop()?.toLowerCase();
  if (!supportedExtensions.has(extension ?? '')) {
    return 'Choose a PDF, JPEG, or PNG file.';
  }
  if (file.size <= 0) {
    return 'Empty files are not accepted.';
  }
  if (file.size > maxBytes) {
    return `The file exceeds the ${maxBytes} byte limit.`;
  }
  return '';
}

export function documentLifecycleRules(status) {
  return {
    canMutate: status === 'DRAFT',
    canCheckIntegrity: willStatuses.has(status),
    isReadOnly: status === 'FINALIZED' || status === 'ARCHIVED',
  };
}

export function integrityResultMessage(result) {
  if (result === 'VALID') return 'Stored content matches the accepted checksum; the original checksum is unchanged.';
  if (result === 'MISMATCH') return 'Stored content differs from the accepted checksum; the original checksum is retained.';
  if (result === 'ERROR') return 'The stored file could not be verified; the original checksum is unchanged.';
  return 'Integrity has not been checked.';
}

export function documentErrorMessage(error) {
  return error instanceof Error ? error.message : 'The document request could not be completed.';
}