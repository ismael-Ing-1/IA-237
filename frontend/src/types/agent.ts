import type {
  Metadata,
} from "./common";

import type {
  Negotiation,
} from "./negotiation";

import type {
  Offer,
} from "./offer";

import type {
  Resource,
  ResourceRequest,
} from "./resource";


/**
 * Mirrors app.agents.personal_agent.AgentAction.
 */
export type AgentAction =
  | "search_market"
  | "start_negotiation"
  | "accept"
  | "counter"
  | "reject"
  | "ask_mediator"
  | "search_coalition"
  | "wait_human"
  | "stop";


/**
 * Mirrors app.agents.personal_agent.CandidatePartner.
 */
export interface CandidatePartner {
  user_id: string;

  display_name: string;

  reputation: number;

  preference_rank: number | null;

  offered_resource_types: string[];

  requested_resource_types: string[];
}


/**
 * Mirrors app.agents.personal_agent.AgentDecision.
 */
export interface AgentDecision {
  action: AgentAction;

  reason: string;

  partner_id: string | null;

  negotiation_id: string | null;

  offer_id: string | null;
}


/**
 * Mirrors app.agents.personal_agent.AgentStepResult.
 */
export interface AgentStepResult {
  decision: AgentDecision;

  negotiation: Negotiation | null;

  offer: Offer | null;
}


/* ============================================================
 * COALITIONS
 * ============================================================
 */

export interface CoalitionTransfer {
  from_user_id: string;
  to_user_id: string;
  resource_type: string;
  quantity: number;
  unit: string;
}

export interface CoalitionProposal {
  id: string;
  participant_ids: string[];
  transfers: CoalitionTransfer[];
}

export type CoalitionStatus =
  | "agent_validating"
  | "waiting_humans"
  | "approved"
  | "rejected"
  | "cancelled"
  | "executing"
  | "completed"
  | "failed";

export interface CoalitionAgentEvaluation {
  user_id: string;
  accepted: boolean;
  reason: string;
}

export interface CoalitionDeal {
  id: string;
  target_user_id: string;
  source_negotiation_id: string | null;
  proposal: CoalitionProposal;
  score: number;
  average_reputation: number;
  status: CoalitionStatus;
  agent_evaluations: Record<string, CoalitionAgentEvaluation>;
  human_approvals: Record<string, boolean | null>;
  rejected_by: string | null;
  created_at: string;
  updated_at: string;
}

export interface RankedCoalition {
  proposal: CoalitionProposal;
  average_reputation: number;
  participant_count: number;
  score: number;
}


/* ============================================================
 * MEDIATION
 * ============================================================
 */

/**
 * Mirrors app.agents.mediator_agent.MediationAction.
 */
export type MediationAction =
  | "no_action"
  | "suggest_counter"
  | "suggest_coalition";


/**
 * Mirrors app.agents.mediator_agent.MediationProposal.
 */
export interface MediationProposal {
  sender_id: string;

  receiver_id: string;

  offered_resources: Resource[];

  requested_resources: ResourceRequest[];
}


/**
 * Mirrors app.agents.mediator_agent.MediationResult.
 */
export interface MediationResult {
  action: MediationAction;

  reason: string;

  proposal: MediationProposal | null;
}


/* ============================================================
 * FRONTEND-SIDE AGENT ACTIVITY
 * ============================================================
 *
 * These are presentation contracts for the React activity feed.
 * They do not replace the backend's AgentDecision model.
 */

export type AgentActivityKind =
  | "decision"
  | "market_search"
  | "provider_found"
  | "negotiation"
  | "privacy"
  | "coalition"
  | "mediation"
  | "approval"
  | "exchange"
  | "system";


export interface AgentActivity {
  id: string;

  user_id: string | null;

  kind: AgentActivityKind;

  title: string;

  message: string;

  timestamp: string;

  metadata?: Metadata;
}
