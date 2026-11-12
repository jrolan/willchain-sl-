import type { WillStatus } from "@/types/wills";

export type IntegrityAnchorStatus = "QUEUED" | "SUBMITTING" | "SUBMITTED" | "CONFIRMED" | "FAILED";
export type IntegrityVerificationResult = "MATCH" | "MISMATCH" | "PENDING" | "UNAVAILABLE";

export interface DocumentIntegrityStatus {
  document_id: number;
  document_version: number;
  record_reference: string;
  network: string;
  chain_id: number;
  contract_address: string;
  anchor_status: IntegrityAnchorStatus;
  transaction_hash: string;
  block_number: number | null;
  confirmations: number;
  last_error_code: string;
  confirmed_at: string | null;
}

export interface IntegrityVerification {
  result: IntegrityVerificationResult;
  content_matches: boolean | null;
  chain_matches: boolean | null;
  details: {
    error_code?: string;
    documents?: Array<{ document_id: number; result: IntegrityVerificationResult }>;
  };
  checked_at: string;
}

export interface WillIntegrityRecord {
  record_reference: string;
  finalized_version: number;
  network: string;
  chain_id: number;
  contract_address: string;
  anchor_status: IntegrityAnchorStatus;
  transaction_hash: string;
  block_number: number | null;
  confirmations: number;
  last_error_code: string;
  submitted_at: string | null;
  confirmed_at: string | null;
  latest_verification: IntegrityVerification | null;
  document_records: DocumentIntegrityStatus[];
}

export interface WillIntegrityStatus {
  will_id: number;
  will_status: WillStatus;
  record: WillIntegrityRecord | null;
}

export interface IntegrityOperationsData {
  wills: Array<{
    will_id: number;
    record_reference: string;
    network: string;
    chain_id: number;
    contract_address: string;
    anchor_status: IntegrityAnchorStatus;
    transaction_hash: string;
    block_number: number | null;
    confirmations: number;
    attempts: number;
    last_error_code: string;
    updated_at: string;
  }>;
  documents: Array<{
    will_id: number;
    document_id: number;
    record_reference: string;
    network: string;
    chain_id: number;
    contract_address: string;
    anchor_status: IntegrityAnchorStatus;
    transaction_hash: string;
    block_number: number | null;
    confirmations: number;
    attempts: number;
    last_error_code: string;
    updated_at: string;
  }>;
}
