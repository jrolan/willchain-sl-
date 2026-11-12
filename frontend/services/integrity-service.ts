import { apiRequest } from "@/services/auth-service";
import type { IntegrityOperationsData, IntegrityVerification, WillIntegrityRecord, WillIntegrityStatus } from "@/types/integrity";

export const getWillIntegrity = (willId: number) =>
  apiRequest<{ data: WillIntegrityStatus }>(`/wills/${willId}/integrity/`);

export const verifyWillIntegrity = (willId: number) =>
  apiRequest<{ data: { record: WillIntegrityRecord; verification: IntegrityVerification } }>(
    `/wills/${willId}/integrity/`,
    { method: "POST" },
  );

export const getLawyerWillIntegrity = (willId: number) =>
  apiRequest<{ data: WillIntegrityRecord }>(`/wills/${willId}/integrity/lawyer/`);

export const verifyLawyerWillIntegrity = (willId: number) =>
  apiRequest<{ data: { record: WillIntegrityRecord; verification: IntegrityVerification } }>(
    `/wills/${willId}/integrity/lawyer/`,
    { method: "POST" },
  );

export const getIntegrityOperations = () =>
  apiRequest<{ data: IntegrityOperationsData }>("/integrity/admin/operations/");

export const retryIntegrityOperation = (reference: string) =>
  apiRequest<{ data: { record_reference: string; anchor_status: string } }>(
    `/integrity/admin/operations/${encodeURIComponent(reference)}/retry/`,
    { method: "POST" },
  );
