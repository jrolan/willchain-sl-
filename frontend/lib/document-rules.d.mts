export const DOCUMENT_MAX_BYTES: 10_000_000;

export function validateDocumentFile(file: { name: string; size: number } | null, maxBytes?: number): string;

export function documentLifecycleRules(status: string): {
  canMutate: boolean;
  canCheckIntegrity: boolean;
  isReadOnly: boolean;
};

export function integrityResultMessage(result: string): string;
export function documentErrorMessage(error: unknown): string;