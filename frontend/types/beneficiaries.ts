import type { User } from "@/types/auth";

export interface BeneficiaryInvitationPreview {
  recipient_email: string;
  status: "PENDING";
  expires_at: string;
}

export interface BeneficiaryRelationship {
  id: number;
  will: number;
  recipient_email: string;
  beneficiary_user: number | null;
  beneficiary_user_email: string | null;
  full_name: string;
  relationship_type: string;
  status: "ACTIVE" | "PENDING" | "DECLINED" | "REVOKED";
  latest_invitation_status: "PENDING" | "ACCEPTED" | "DECLINED" | "REVOKED" | "EXPIRED" | null;
  latest_invitation_expires_at: string | null;
  latest_invitation_sent_at: string | null;
  accepted_at: string | null;
  revoked_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface BeneficiarySelfRelationship {
  id: number;
  recipient_email: string;
  full_name: string;
  relationship_type: string;
  status: "ACTIVE";
  accepted_at: string | null;
  created_at: string;
}

export type BeneficiaryRelationshipType = "PRIMARY" | "CONTINGENT" | "RESIDUAL" | "WITNESS" | "LAWYER";

export interface CreateBeneficiaryRelationship {
  recipient_email: string;
  full_name?: string;
  relationship_type: BeneficiaryRelationshipType;
}

export interface BeneficiaryInvitationRegistration {
  email: string;
  first_name: string;
  last_name: string;
  phone_number: string;
  password: string;
  password_confirmation: string;
  invitation_token: string;
}

export interface BeneficiaryInvitationRegistrationResponse {
  data: User;
  message: string;
}
