export type WillStatus = "DRAFT" | "FINALIZED" | "ARCHIVED";

export interface WillContent {
  testator?: {
    full_name?: string;
    address?: string;
    occupation?: string;
    marital_status?: "SINGLE" | "MARRIED" | "SEPARATED" | "WIDOWED" | "OTHER";
  };
  family?: {
    spouse_or_partner?: string;
    children?: Array<{ full_name: string; date_of_birth?: string; notes?: string }>;
    dependants?: Array<{ full_name: string; relationship?: string; notes?: string }>;
  };
  executor?: {
    full_name?: string;
    relationship?: string;
    address?: string;
    phone?: string;
    alternate_full_name?: string;
  };
  guardians?: Array<{ full_name: string; relationship?: string; for_minor?: boolean; notes?: string }>;
  beneficiaries?: Array<{ full_name: string; relationship?: string; contact?: string; notes?: string }>;
  gifts?: Array<{ description: string; beneficiary_name: string; conditions?: string }>;
  residual_estate?: string;
  funeral_wishes?: string;
  digital_assets_notes?: string;
  review_notes?: string;
  sections?: Array<{ title: string; body: string }>;
  [key: string]: unknown;
}

export interface Will {
  id: number;
  owner: number;
  owner_email: string;
  title: string;
  content: WillContent;
  status: WillStatus;
  version: number;
  finalized_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface WillPayload {
  title: string;
  content: WillContent;
}
