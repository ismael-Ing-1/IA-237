import type {
  ISODateTime,
  Metadata,
} from "./common";

import type {
  AgentDecision,
  MediationResult,
  CoalitionDeal,
  RankedCoalition,
} from "./agent";

import type {
  Negotiation,
} from "./negotiation";

import type {
  Offer,
} from "./offer";

import type {
  EventExecution,
  MarketEvent,
} from "./simulation";


/**
 * Planned real-time event names for the React/FastAPI WebSocket layer.
 *
 * These are frontend contracts for the WebSocket implementation.
 * They are intentionally separate from Simulation EventType.
 */
export type WebSocketEventType =
  | "connected"
  | "agent_started"
  | "agent_action"
  | "agent_notified"
  | "agent_stopped"
  | "provider_found"
  | "market_updated"
  | "user_online"
  | "user_offline"
  | "negotiation_started"
  | "negotiation_updated"
  | "offer_sent"
  | "counter_offer_sent"
  | "offer_accepted"
  | "offer_rejected"
  | "privacy_check_passed"
  | "privacy_blocked"
  | "coalition_search_started"
  | "coalition_search_completed"
  | "coalition_found"
  | "coalition_selected"
  | "coalition_agent_evaluated"
  | "coalition_rejected"
  | "coalition_human_approval_required"
  | "coalition_human_approved"
  | "coalition_human_rejected"
  | "coalition_approved"
  | "coalition_cancelled"
  | "coalition_exchange_started"
  | "coalition_exchange_completed"
  | "coalition_exchange_failed"
  | "mediation_started"
  | "mediation_suggestion"
  | "llm_thinking"
  | "llm_decision"
  | "llm_shadow_decision"
  | "llm_policy_validated"
  | "llm_fallback"
  | "human_approval_required"
  | "human_approved"
  | "human_rejected"
  | "exchange_started"
  | "exchange_completed"
  | "exchange_failed"
  | "market_event_scheduled"
  | "market_event_executed"
  | "simulation_time_updated"
  | "error";


/**
 * Generic event envelope.
 */
export interface WebSocketEvent<
  TPayload = Metadata,
> {
  event_id: string;

  type: WebSocketEventType;

  timestamp: ISODateTime;

  user_id: string | null;

  entity_id: string | null;

  payload: TPayload;
}


/* ============================================================
 * OPTIONAL TYPED PAYLOADS
 * ============================================================
 */

export interface ConnectedPayload {
  message: string;
}


export interface AgentActionPayload {
  decision: AgentDecision;
}


export interface ProviderFoundPayload {
  provider_id: string;

  display_name?: string;

  reputation?: number;
}


export interface NegotiationPayload {
  negotiation: Negotiation;
}


export interface OfferPayload {
  negotiation_id: string;

  offer: Offer;
}


export interface CoalitionPayload {
  coalition?: RankedCoalition;
  coalition_deal?: CoalitionDeal;
  message?: string;
}


export interface MediationPayload {
  negotiation_id: string;

  result: MediationResult;
}


export interface SimulationTimePayload {
  current_time: ISODateTime;
}


export interface MarketEventScheduledPayload {
  event: MarketEvent;
}


export interface MarketEventExecutedPayload {
  execution: EventExecution;
}


export interface ErrorPayload {
  message: string;

  code?: string;

  details?: unknown;
}
