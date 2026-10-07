import { apiRequest } from "@/services/auth-service";
import type { DashboardActivity } from "@/types/dashboard";

export function getMyActivity(): Promise<{ data: DashboardActivity[] }> {
  return apiRequest("/me/activity/");
}
