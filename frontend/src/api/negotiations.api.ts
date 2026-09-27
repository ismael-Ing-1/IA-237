import { apiClient } from "./client";

import type {
  Offer,
} from "../types/offer";

import type {
  Negotiation,
  NegotiationStatus,
} from "../types/negotiation";

import type {
  Resource,
  ResourceRequest,
} from "../types/resource";


export interface CreateNegotiationInput {
  participant_ids: string[];
  max_rounds?: number;
}


export interface OfferInput {
  sender_id: string;
  receiver_id: string;

  offered_resources: Resource[];
  requested_resources: ResourceRequest[];

  message?: string | null;
  expires_at?: string | null;
}


export interface CounterOfferInput extends OfferInput {
  previous_offer_id: string;
}


export interface RejectOfferInput {
  close_negotiation?: boolean;
}


export interface OfferDecisionResponse {
  message: string;
  offer: Offer;
  negotiation_status: NegotiationStatus;
}


export interface NegotiationResponse {
  message: string;
  negotiation: Negotiation;
}


export interface ExecuteExchangeResponse {
  success: boolean;
  message: string;
  negotiation_id: string;
}


export async function getNegotiations(): Promise<Negotiation[]> {
  const response = await apiClient.get<Negotiation[]>(
    "/negotiations",
  );

  return response.data;
}


export async function getNegotiation(
  negotiationId: string,
): Promise<Negotiation> {
  const response = await apiClient.get<Negotiation>(
    `/negotiations/${encodeURIComponent(negotiationId)}`,
  );

  return response.data;
}


export async function createNegotiation(
  input: CreateNegotiationInput,
): Promise<Negotiation> {
  const response = await apiClient.post<Negotiation>(
    "/negotiations",
    input,
  );

  return response.data;
}


export async function sendOffer(
  negotiationId: string,
  input: OfferInput,
): Promise<Offer> {
  const response = await apiClient.post<Offer>(
    `/negotiations/${encodeURIComponent(negotiationId)}/offers`,
    input,
  );

  return response.data;
}


export async function sendCounterOffer(
  negotiationId: string,
  input: CounterOfferInput,
): Promise<Offer> {
  const response = await apiClient.post<Offer>(
    `/negotiations/${encodeURIComponent(negotiationId)}/counter-offers`,
    input,
  );

  return response.data;
}


export async function acceptOffer(
  negotiationId: string,
  offerId: string,
): Promise<OfferDecisionResponse> {
  const response = await apiClient.post<OfferDecisionResponse>(
    `/negotiations/${encodeURIComponent(negotiationId)}/offers/${encodeURIComponent(offerId)}/accept`,
  );

  return response.data;
}


export async function rejectOffer(
  negotiationId: string,
  offerId: string,
  input: RejectOfferInput = {},
): Promise<OfferDecisionResponse> {
  const response = await apiClient.post<OfferDecisionResponse>(
    `/negotiations/${encodeURIComponent(negotiationId)}/offers/${encodeURIComponent(offerId)}/reject`,
    input,
  );

  return response.data;
}


export async function requestHumanApproval(
  negotiationId: string,
): Promise<NegotiationResponse> {
  const response = await apiClient.post<NegotiationResponse>(
    `/negotiations/${encodeURIComponent(negotiationId)}/request-approval`,
  );

  return response.data;
}


export async function approveNegotiation(
  negotiationId: string,
): Promise<NegotiationResponse> {
  const response = await apiClient.post<NegotiationResponse>(
    `/negotiations/${encodeURIComponent(negotiationId)}/approve`,
  );

  return response.data;
}


export async function rejectNegotiation(
  negotiationId: string,
): Promise<NegotiationResponse> {
  const response = await apiClient.post<NegotiationResponse>(
    `/negotiations/${encodeURIComponent(negotiationId)}/reject`,
  );

  return response.data;
}


export async function cancelNegotiation(
  negotiationId: string,
): Promise<NegotiationResponse> {
  const response = await apiClient.post<NegotiationResponse>(
    `/negotiations/${encodeURIComponent(negotiationId)}/cancel`,
  );

  return response.data;
}


export async function executeNegotiation(
  negotiationId: string,
): Promise<ExecuteExchangeResponse> {
  const response = await apiClient.post<ExecuteExchangeResponse>(
    `/negotiations/${encodeURIComponent(negotiationId)}/execute`,
  );

  return response.data;
}
