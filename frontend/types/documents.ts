export type DocumentType =
  | 'IDENTITY'
  | 'PASSPORT'
  | 'LAND_PROPERTY'
  | 'MARRIAGE_CERTIFICATE'
  | 'BIRTH_CERTIFICATE'
  | 'OTHER';

export type DocumentStatus = 'ACTIVE' | 'REPLACED' | 'DELETED';
export type IntegrityResult = 'VALID' | 'MISMATCH' | 'ERROR';

export interface DocumentIntegrityCheck {
  id: number;
  result: IntegrityResult;
  expected_checksum: string;
  computed_checksum: string;
  error_code: string;
  created_at: string;
}

export interface WillDocument {
  id: number;
  document_type: DocumentType;
  description: string;
  original_filename: string;
  media_type: string;
  file_size: number;
  checksum_sha256: string;
  status: DocumentStatus;
  version: number;
  created_at: string;
  updated_at: string;
  deleted_at: string | null;
  replaced_from_id: number | null;
  replaced_by_id: number | null;
  latest_integrity_check: DocumentIntegrityCheck | null;
}

export interface WillDocumentsResponse {
  data: WillDocument[];
  max_file_size_bytes: number;
}