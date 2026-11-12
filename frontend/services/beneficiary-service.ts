import { apiRequest } from "@/services/auth-service";
import type {
  BeneficiaryInvitationPreview,
  BeneficiaryInvitationRegistration,
  BeneficiaryInvitationRegistrationResponse,
  BeneficiaryAllocationAccess,
  BeneficiaryAllocationRecord,
  BeneficiaryRelationship,
  BeneficiarySelfRelationship,
  CreateBeneficiaryRelationship,
} from "@/types/beneficiaries";

export function getMyBeneficiaryRelationships(): Promise<{ data: BeneficiarySelfRelationship[] }> {
  return apiRequest("/me/beneficiary-relationships/");
}

export function getWillBeneficiaries(willId: number): Promise<{ data: BeneficiaryRelationship[] }> {
  return apiRequest(`/wills/${willId}/beneficiaries/`);
}

export function createWillBeneficiary(
  willId: number,
  payload: CreateBeneficiaryRelationship,
): Promise<{ data: BeneficiaryRelationship; message: string }> {
  return apiRequest(`/wills/${willId}/beneficiaries/`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function updateWillBeneficiary(
  willId: number,
  relationshipId: number,
  payload: Partial<Pick<CreateBeneficiaryRelationship, "full_name" | "relationship_type">>,
): Promise<{ data: BeneficiaryRelationship; message: string }> {
  return apiRequest(`/wills/${willId}/beneficiaries/${relationshipId}/`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

export function revokeWillBeneficiary(
  willId: number,
  relationshipId: number,
): Promise<{ data: { id: number; status: string }; message: string }> {
  return apiRequest(`/wills/${willId}/beneficiaries/${relationshipId}/`, {
    method: "DELETE",
  });
}

export function getBeneficiaryInvitationPreview(token: string): Promise<BeneficiaryInvitationPreview> {
  return apiRequest(`/beneficiary-invitations/${encodeURIComponent(token)}/`);
}

export function registerFromBeneficiaryInvitation(
  payload: BeneficiaryInvitationRegistration,
): Promise<BeneficiaryInvitationRegistrationResponse> {
  return apiRequest("/beneficiary-invitations/register/", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function acceptBeneficiaryInvitation(token: string): Promise<{ data: BeneficiaryRelationship; message: string }> {
  return apiRequest("/beneficiary-invitations/accept/", {
    method: "POST",
    body: JSON.stringify({ token }),
  });
}

export function declineBeneficiaryInvitation(token: string): Promise<{ data: { status: string }; message: string }> {
  return apiRequest("/beneficiary-invitations/decline/", {
    method: "POST",
    body: JSON.stringify({ token }),
  });
}

export function getMyBeneficiaryAllocations(): Promise<{ data: BeneficiaryAllocationAccess[] }> {
  return apiRequest("/me/beneficiary-allocations/");
}

export function getWillBeneficiaryAllocations(willId: number, beneficiaryId: number): Promise<{ data: BeneficiaryAllocationRecord[] }> {
  return apiRequest(`/wills/${willId}/beneficiaries/${beneficiaryId}/allocations/`);
}

export function createWillBeneficiaryAllocation(
  willId: number,
  beneficiaryId: number,
  payload: Pick<BeneficiaryAllocationRecord, "allocation_type" | "description" | "amount" | "currency_code" | "percentage">,
): Promise<{ data: BeneficiaryAllocationRecord }> {
  return apiRequest(`/wills/${willId}/beneficiaries/${beneficiaryId}/allocations/`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function updateWillBeneficiaryAllocation(
  willId: number,
  beneficiaryId: number,
  allocationId: number,
  payload: Pick<BeneficiaryAllocationRecord, "allocation_type" | "description" | "amount" | "currency_code" | "percentage">,
): Promise<{ data: BeneficiaryAllocationRecord }> {
  return apiRequest(`/wills/${willId}/beneficiaries/${beneficiaryId}/allocations/${allocationId}/`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

export function deleteWillBeneficiaryAllocation(willId: number, beneficiaryId: number, allocationId: number): Promise<void> {
  return apiRequest(`/wills/${willId}/beneficiaries/${beneficiaryId}/allocations/${allocationId}/`, {
    method: "DELETE",
  });
}

export function validateBeneficiaryReleaseToken(token: string): Promise<{ data: { valid: true; beneficiary_email: string } }> {
  return apiRequest("/beneficiary-release/validate-token/", {
    method: "POST",
    body: JSON.stringify({ token }),
  });
}

export function registerBeneficiaryRelease(payload: {
  token: string;
  email: string;
  first_name: string;
  last_name: string;
  password: string;
  password_confirmation: string;
}): Promise<{ data: { email: string; account_status: string }; message: string }> {
  return apiRequest("/beneficiary-release/register/", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function claimBeneficiaryRelease(token: string): Promise<{ data: { claimed: true }; message: string }> {
  return apiRequest("/beneficiary-release/claim/", {
    method: "POST",
    body: JSON.stringify({ token }),
  });
}

export function verifyBeneficiaryReleaseIdentity(token: string, code: string): Promise<{ data: { verified: true }; message: string }> {
  return apiRequest("/beneficiary-release/verify-identity/", {
    method: "POST",
    body: JSON.stringify({ token, code }),
  });
}
