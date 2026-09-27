import { apiClient } from "./client";
export async function stopAgentObjective(userId: string): Promise<{ message: string; user_id: string }> {
  const response = await apiClient.post<{ message: string; user_id: string }>(
    `/agents/${encodeURIComponent(userId)}/stop`,
  );
  return response.data;
}
