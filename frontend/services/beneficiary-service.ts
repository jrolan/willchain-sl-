import { apiRequest } from "@/services/auth-service";
import type {
  BeneficiaryInvitationPreview,
  BeneficiaryInvitationRegistration,
  BeneficiaryInvitationRegistrationResponse,
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

export function resendWillBeneficiaryInvitation(
  willId: number,
  relationshipId: number,
): Promise<{ data: { id: number; status: string }; message: string }> {
  return apiRequest(`/wills/${willId}/beneficiaries/${relationshipId}/resend-invitation/`, {
    method: "POST",
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
