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
}
