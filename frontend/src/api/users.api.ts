import { apiClient } from "./client";

import type {
  NegotiationStrategy,
  PublicUserProfile,
  User,
  UserDashboard,
} from "../types/user";


export interface UpdateUserStrategyResponse {
  user_id: string;
  strategy: NegotiationStrategy;
}


export async function getUsers(): Promise<PublicUserProfile[]> {
  const response = await apiClient.get<PublicUserProfile[]>(
    "/users",
  );

  return response.data;
}


export async function getUser(
  userId: string,
): Promise<PublicUserProfile> {
  const response = await apiClient.get<PublicUserProfile>(
    `/users/${encodeURIComponent(userId)}`,
  );

  return response.data;
}


/**
 * Owner-oriented view used by the dashboard.
 *
 * This endpoint should never be used to display another user's private data.
 * In production it should be protected with authentication.
 */
export async function getUserDashboard(
  userId: string,
): Promise<UserDashboard> {
  const response = await apiClient.get<UserDashboard>(
    `/users/${encodeURIComponent(userId)}/dashboard`,
  );

  return response.data;
}


export async function createUser(
  user: User,
): Promise<PublicUserProfile> {
  const response = await apiClient.post<PublicUserProfile>(
    "/users",
    user,
  );

  return response.data;
}


export async function updateUserStrategy(
  userId: string,
  strategy: NegotiationStrategy,
): Promise<UpdateUserStrategyResponse> {
  const response =
    await apiClient.patch<UpdateUserStrategyResponse>(
      `/users/${encodeURIComponent(userId)}/strategy`,
      {
        strategy,
      },
    );

  return response.data;
}
