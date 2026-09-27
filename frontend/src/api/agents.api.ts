import { apiClient } from "./client";

import type {
  AgentStepResult,
  CandidatePartner,
  RankedCoalition,
  MediationResult,
} from "../types/agent";

import type {
  Resource,
  ResourceRequest,
} from "../types/resource";


/**
 * These endpoints are intentionally isolated here because they depend on
 * the agent-facing routes being exposed by FastAPI.
 *
 * The rest of src/api works independently even if these routes are not
 * implemented yet.
 */


export interface PursueRequestInput {
  request: ResourceRequest;
  offered_resources: Resource[];
  message?: string | null;
}


export interface HandleOfferInput {
  negotiation_id: string;
  offer_id: string;
}


export async function discoverAgentCandidates(
  userId: string,
  resourceType: string,
): Promise<CandidatePartner[]> {
  const response = await apiClient.get<CandidatePartner[]>(
    `/agents/${encodeURIComponent(userId)}/candidates`,
    {
      params: {
        resource_type: resourceType,
      },
    },
  );

  return response.data;
}


export async function pursueAgentRequest(
  userId: string,
  input: PursueRequestInput,
): Promise<AgentStepResult> {
  const response = await apiClient.post<AgentStepResult>(
    `/agents/${encodeURIComponent(userId)}/pursue`,
    input,
  );

  return response.data;
}


export async function handleAgentOffer(
  userId: string,
  input: HandleOfferInput,
): Promise<AgentStepResult> {
  const response = await apiClient.post<AgentStepResult>(
    `/agents/${encodeURIComponent(userId)}/handle-offer`,
    input,
  );

  return response.data;
}


export async function getCoalitions(
  userId: string,
  params: {
    minSize?: number;
    maxSize?: number;
  } = {},
): Promise<RankedCoalition[]> {
  const response = await apiClient.get<RankedCoalition[]>(
    `/coalitions/${encodeURIComponent(userId)}`,
    {
      params: {
        min_size: params.minSize,
        max_size: params.maxSize,
      },
    },
  );

  return response.data;
}


export async function mediateNegotiation(
  negotiationId: string,
): Promise<MediationResult> {
  const response = await apiClient.post<MediationResult>(
    `/negotiations/${encodeURIComponent(negotiationId)}/mediate`,
  );

  return response.data;
}
