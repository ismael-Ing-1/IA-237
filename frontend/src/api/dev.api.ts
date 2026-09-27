import { apiClient } from "./client";


export interface HealthResponse {
  status: string;
  users: number;
  negotiations: number;
}


export interface ResetResponse {
  message: string;
}


export async function getHealth(): Promise<HealthResponse> {
  const response = await apiClient.get<HealthResponse>(
    "/health",
  );

  return response.data;
}


/**
 * Development / hackathon utility.
 * Do not expose this action in a production UI.
 */
export async function resetBackendState(): Promise<ResetResponse> {
  const response = await apiClient.delete<ResetResponse>(
    "/dev/reset",
  );

  return response.data;
}
