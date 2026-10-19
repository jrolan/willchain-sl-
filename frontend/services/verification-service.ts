import { apiDownload, apiRequest } from '@/services/auth-service';
import type {
  CaseEvidence,
  CreateCasePayload,
  Module8VerificationStatus,
  VerificationCase,
} from '@/types/verification';

const BASE = '/verification';

export const getCases = () =>
  apiRequest<{ data: VerificationCase[] }>(`${BASE}/cases/`);

export const getCase = (id: number) =>
  apiRequest<{ data: VerificationCase }>(`${BASE}/cases/${id}/`);

export const createCase = (payload: CreateCasePayload) =>
  apiRequest<{ data: VerificationCase; message: string }>(`${BASE}/cases/`, {
    method: 'POST',
    body: JSON.stringify(payload),
  });

export const submitCase = (id: number) =>
  apiRequest<{ data: VerificationCase; message: string }>(`${BASE}/cases/${id}/submit/`, {
    method: 'POST',
  });

export const uploadEvidence = (
  caseId: number,
  file: File,
  evidenceType: string,
  description: string,
) => {
  const form = new FormData();
  form.append('file', file);
  form.append('evidence_type', evidenceType);
  if (description) {
    form.append('description', description);
  }
  return apiRequest<{ data: CaseEvidence; message: string }>(
    `${BASE}/cases/${caseId}/evidence/`,
    {
      method: 'POST',
      body: form,
    },
  );
};

export const downloadEvidence = (caseId: number, evidenceId: number): Promise<Blob> =>
  apiDownload(`${BASE}/cases/${caseId}/evidence/${evidenceId}/download/`);

export const setEvidenceSufficiency = (caseId: number, evidenceId: number, sufficiencyFlag: boolean) =>
  apiRequest<{ data: CaseEvidence; message: string }>(
    `${BASE}/cases/${caseId}/evidence/${evidenceId}/sufficiency/`,
    {
      method: 'POST',
      body: JSON.stringify({ sufficiency_flag: sufficiencyFlag }),
    },
  );

export const beginReview = (caseId: number) =>
  apiRequest<{ data: VerificationCase; message: string }>(`${BASE}/cases/${caseId}/begin-review/`, {
    method: 'POST',
  });

export const requestInformation = (caseId: number, notes: string) =>
  apiRequest<{ data: VerificationCase; message: string }>(
    `${BASE}/cases/${caseId}/request-information/`,
    {
      method: 'POST',
      body: JSON.stringify({ notes }),
    },
  );

export const resubmitCase = (caseId: number) =>
  apiRequest<{ data: VerificationCase; message: string }>(`${BASE}/cases/${caseId}/resubmit/`, {
    method: 'POST',
  });

export const recordDecision = (caseId: number, decision: 'APPROVED' | 'REJECTED', notes: string) =>
  apiRequest<{ data: VerificationCase; message: string }>(`${BASE}/cases/${caseId}/decision/`, {
    method: 'POST',
    body: JSON.stringify({ decision, notes }),
  });

export const assessEligibility = (caseId: number, isEligible: boolean, notes: string) =>
  apiRequest<{ data: unknown; message: string }>(
    `${BASE}/cases/${caseId}/assess-eligibility/`,
    {
      method: 'POST',
      body: JSON.stringify({ is_eligible: isEligible, notes }),
    },
  );

export const authorizeDisclosure = (caseId: number, file: File) => {
  const form = new FormData();
  form.append('file', file);
  return apiRequest<{ data: VerificationCase; message: string }>(
    `${BASE}/cases/${caseId}/authorize-disclosure/`,
    {
      method: 'POST',
      body: form,
    },
  );
};

export const revokeDisclosure = (caseId: number) =>
  apiRequest<{ message: string }>(`${BASE}/cases/${caseId}/revoke-disclosure/`, {
    method: 'POST',
  });

export const downloadDisclosure = (caseId: number): Promise<Blob> =>
  apiDownload(`${BASE}/cases/${caseId}/disclosure-download/`);

export const withdrawCase = (caseId: number) =>
  apiRequest<{ data: VerificationCase; message: string }>(`${BASE}/cases/${caseId}/withdraw/`, {
    method: 'POST',
  });

export const getWillVerificationStatus = (willId: number) =>
  apiRequest<{ data: Module8VerificationStatus }>(`${BASE}/status/${willId}/`);

