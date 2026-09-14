export type UserRole =
  | "OWNER"
  | "WITNESS"
  | "BENEFICIARY"
  | "LAWYER_VERIFIER"
  | "ADMINISTRATOR";

export type AccountStatus =
  | "PENDING_VERIFICATION"
  | "ACTIVE"
  | "INACTIVE"
  | "SUSPENDED";

export interface User {
  id: number;
  email: string;
  first_name: string;
  last_name: string;
  phone_number: string;
  avatar: string | null;
  role: UserRole;
  account_status: AccountStatus;
  email_verified: boolean;
  created_at: string;
  updated_at: string;
}

export interface AuthResponse {
  data: {
    access: string;
    user: User;
  };
}

export interface ApiError {
  error?: { code?: string; message?: string; fields?: Record<string, string[]> };
  detail?: string;
  message?: string;
}

export type InvitationRole = "WITNESS" | "BENEFICIARY" | "LAWYER_VERIFIER";
export type InvitationStatus = "PENDING" | "ACCEPTED" | "EXPIRED" | "REVOKED";

export interface Invitation {
  id: number;
  inviter_email: string;
  email: string;
  first_name: string;
  last_name: string;
  role: InvitationRole;
  status: InvitationStatus;
  message: string;
  expires_at: string;
  created_at: string;
  token?: string;
}

export interface InvitationDetail {
  email: string;
  first_name: string;
  last_name: string;
  role: InvitationRole;
  role_display: string;
  inviter_name: string;
}
