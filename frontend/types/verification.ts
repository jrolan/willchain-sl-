export type CaseType = 'PRE_DEATH_REVIEW' | 'POST_DEATH_VERIFY';

export type SubmissionType = 'OWNER_INITIATED' | 'BENEFICIARY_CLAIM' | 'CLAIMED_EXECUTOR';

export type CaseStatus =
  | 'PENDING_ELIGIBILITY'
  | 'OPEN'
  | 'INFORMATION_REQUIRED'
  | 'UNDER_REVIEW'
  | 'APPROVED'
  | 'REJECTED'
  | 'WITHDRAWN';

export type EvidenceType =
  | 'DEATH_CERTIFICATE'
  | 'IDENTITY_DOCUMENT'
  | 'PROBATE_DOCUMENT'
  | 'RELATIONSHIP_PROOF'
  | 'WILL_COPY'
  | 'OTHER';

export interface AssignedLawyerDisplay {
  display_name: string;
  assigned_at: string | null;
}

export interface CaseStatusHistoryItem {
  id: number;
  from_status: string;
  to_status: string;
  actor_role: string | null;
  notes: string;
  created_at: string;
}

export interface CaseEvidence {
  id: number;
  evidence_type: EvidenceType;
  description: string;
  original_filename: string;
  media_type: string;
  file_size: number;
  checksum_sha256: string;
  sufficiency_flag: boolean;
  created_at: string;
}

export interface WillDisclosureAuthorization {
  id: number;
  original_filename: string;
  media_type: string;
  file_size: number;
  checksum_sha256: string;
  is_active: boolean;
  revoked_at: string | null;
  created_at: string;
}

export interface EligibilityAssessment {
  id: number;
  is_eligible: boolean;
  notes: string;
  assessed_at: string;
  assessed_by_name: string | null;
}

export interface VerificationCase {
  id: number;
  will: number | null;
  case_type: CaseType;
  submission_type: SubmissionType;
  status: CaseStatus;
  claimed_executor_basis: string;
  decision_notes: string;
  information_request_notes: string;
  assigned_lawyer_display: AssignedLawyerDisplay | null;
  evidence: CaseEvidence[];
  status_history: CaseStatusHistoryItem[];
  disclosure_authorization: WillDisclosureAuthorization | null;
  eligibility_assessment: EligibilityAssessment | null;
  linked_prior_case: number | null;
  created_at: string;
  updated_at: string;
}

export interface CreateCasePayload {
  will?: number | null;
  case_type: CaseType;
  submission_type: SubmissionType;
  claimed_executor_basis?: string;
  linked_prior_case?: number | null;
}

export interface Module8VerificationStatus {
  case_id: number;
  will_id: number;
  case_type: CaseType;
  status: CaseStatus;
  approved_at: string | null;
}

