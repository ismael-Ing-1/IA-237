import type {
  CoalitionDeal,
  RankedCoalition,
} from "./agent";

import type {
  ISODateTime,
  Metadata,
} from "./common";

import type {
  Negotiation,
} from "./negotiation";

import type {
  Resource,
  ResourceRequest,
} from "./resource";

import type {
  PublicUserProfile,
} from "./user";


/**
 * Mirrors app.simulation.events.EventType.
 */
export type EventType =
  | "resource_added"
  | "resource_removed"
  | "resource_expired"
  | "need_added"
  | "need_removed"
  | "user_online"
  | "user_offline";


/**
 * Mirrors app.simulation.events.MarketEvent.
 */
export interface MarketEvent {
  id: string;

  event_type: EventType;

  user_id: string;

  scheduled_at: ISODateTime;

  resource: Resource | null;

  resource_id: string | null;

  quantity: number | null;

  need: ResourceRequest | null;

  need_id: string | null;

  reason: string | null;

  metadata: Metadata;
}


/**
 * Mirrors app.simulation.events.EventExecution.
 */
export interface EventExecution {
  event_id: string;

  event_type: EventType;

  user_id: string;

  executed_at: ISODateTime;

  success: boolean;

  message: string;
}


/**
 * Exact public snapshot returned by:
 *
 * GET /simulation/state
 */
export interface SimulationState {
  current_time: ISODateTime;

  users: PublicUserProfile[];

  active_negotiations: Negotiation[];

  completed_negotiations: Negotiation[];

  scheduled_events: MarketEvent[];

  event_history: EventExecution[];

  coalitions: RankedCoalition[];

  coalition_deals: CoalitionDeal[];
}


/**
 * Returned by POST /simulation/advance
 * and POST /simulation/run-until in the current FastAPI API.
 */
export interface SimulationAdvanceResult {
  current_time: ISODateTime;

  executed_events: EventExecution[];

  scheduled_events: MarketEvent[];
}
