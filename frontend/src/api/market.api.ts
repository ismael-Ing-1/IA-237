import { apiClient } from "./client";

import type {
  PublicUserProfile,
} from "../types/user";


export interface ProviderSearchParams {
  requesterId?: string;
}


export interface RequesterSearchParams {
  providerId?: string;
}


export async function getProviders(
  resourceType: string,
  params: ProviderSearchParams = {},
): Promise<PublicUserProfile[]> {
  const response = await apiClient.get<PublicUserProfile[]>(
    `/market/providers/${encodeURIComponent(resourceType)}`,
    {
      params: {
        requester_id: params.requesterId,
      },
    },
  );

  return response.data;
}


export async function getRequesters(
  resourceType: string,
  params: RequesterSearchParams = {},
): Promise<PublicUserProfile[]> {
  const response = await apiClient.get<PublicUserProfile[]>(
    `/market/requesters/${encodeURIComponent(resourceType)}`,
    {
      params: {
        provider_id: params.providerId,
      },
    },
  );

  return response.data;
}
