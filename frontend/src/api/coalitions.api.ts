import { apiClient } from "./client";
import type { CoalitionDeal } from "../types/agent";

export interface CoalitionActionResult {
  message: string;
  coalition: CoalitionDeal;
  success?: boolean;
}

export async function getCoalitionDeals(): Promise<CoalitionDeal[]> {
  const response = await apiClient.get<CoalitionDeal[]>("/coalition-deals");
  return response.data;
}

export async function getCoalitionDeal(coalitionId: string): Promise<CoalitionDeal> {
  const response = await apiClient.get<CoalitionDeal>(`/coalition-deals/${coalitionId}`);
  return response.data;
}

export async function approveCoalition(
  coalitionId: string,
  userId: string,
): Promise<CoalitionActionResult> {
  const response = await apiClient.post<CoalitionActionResult>(
    `/coalition-deals/${coalitionId}/approve`,
    { user_id: userId },
  );
  return response.data;
}

export async function rejectCoalition(
  coalitionId: string,
  userId: string,
): Promise<CoalitionActionResult> {
  const response = await apiClient.post<CoalitionActionResult>(
    `/coalition-deals/${coalitionId}/reject`,
    { user_id: userId },
  );
  return response.data;
}

export async function executeCoalition(
  coalitionId: string,
): Promise<CoalitionActionResult> {
  const response = await apiClient.post<CoalitionActionResult>(
    `/coalition-deals/${coalitionId}/execute`,
  );
  return response.data;
}
