import type {
  AgentAction,
} from "../types/agent";

import type {
  NegotiationStatus,
} from "../types/negotiation";

import type {
  OfferStatus,
} from "../types/offer";

import type {
  NegotiationStrategy,
} from "../types/user";

import type {
  EventType,
} from "../types/simulation";


/* ============================================================
 * APPLICATION
 * ============================================================
 */

export const APP_NAME =
  "Compute Exchange";

export const APP_SUBTITLE =
  "Agentic Resource Market";


/* ============================================================
 * NETWORK / CACHE
 * ============================================================
 */

export const DEFAULT_API_BASE_URL =
  "http://localhost:8000";

export const DEFAULT_WS_URL =
  "ws://localhost:8000/ws";

export const DEFAULT_QUERY_STALE_TIME_MS =
  5_000;

export const DEFAULT_WS_RECONNECT_DELAY_MS =
  1_000;

export const MAX_WS_RECONNECT_DELAY_MS =
  10_000;

export const DEFAULT_ACTIVITY_HISTORY_LIMIT =
  250;


/* ============================================================
 * MARKET GRAPH
 * ============================================================
 */

export const DEFAULT_GRAPH_LAYOUT =
  "radial" as const;

export const MARKET_GRAPH_MIN_ZOOM =
  0.3;

export const MARKET_GRAPH_MAX_ZOOM =
  1.8;


/* ============================================================
 * RESOURCE PRESETS
 * ============================================================
 */

export const COMPUTE_RESOURCE_TYPES = [
  "H100",
  "A100",
  "CPU",
  "STORAGE",
] as const;


export type ComputeResourceType =
  typeof COMPUTE_RESOURCE_TYPES[number];


export const RESOURCE_UNIT_PRESETS: Record<
  ComputeResourceType,
  string
> = {
  H100: "gpu-hour",
  A100: "gpu-hour",
  CPU: "cpu-hour",
  STORAGE: "GB-day",
};


/* ============================================================
 * NEGOTIATION
 * ============================================================
 */

export const NEGOTIATION_STATUS_LABELS:
  Record<
    NegotiationStatus,
    string
  > = {
  open: "Open",

  negotiating:
    "Negotiating",

  agreement_found:
    "Agreement Found",

  waiting_human:
    "Waiting For Approval",

  approved:
    "Approved",

  rejected:
    "Rejected",

  cancelled:
    "Cancelled",

  failed:
    "Failed",
};


export const OFFER_STATUS_LABELS:
  Record<
    OfferStatus,
    string
  > = {
  pending: "Pending",

  accepted: "Accepted",

  rejected: "Rejected",

  countered:
    "Countered",

  expired: "Expired",

  cancelled:
    "Cancelled",
};


/* ============================================================
 * AGENTS
 * ============================================================
 */

export const AGENT_ACTION_LABELS:
  Record<
    AgentAction,
    string
  > = {
  search_market:
    "Searching Market",

  start_negotiation:
    "Negotiating",

  accept:
    "Offer Accepted",
  ask_mediator: 
    "Ask mediator",

  counter:
    "Counter Offer",

  reject:
    "Rejected",

  search_coalition:
    "Searching Coalition",

  wait_human:
    "Waiting For Approval",

  stop:
    "Stopped",
};


export const STRATEGY_LABELS:
  Record<
    NegotiationStrategy,
    string
  > = {
  balanced:
    "Balanced",

  conservative:
    "Conservative",

  aggressive:
    "Aggressive",

  fast:
    "Fast",
};


/* ============================================================
 * SIMULATION EVENTS
 * ============================================================
 */

export const EVENT_TYPE_LABELS:
  Record<
    EventType,
    string
  > = {
  resource_added:
    "Resource Added",

  resource_removed:
    "Resource Removed",

  resource_expired:
    "Resource Expired",

  need_added:
    "Need Added",

  need_removed:
    "Need Removed",

  user_online:
    "User Online",

  user_offline:
    "User Offline",
};


/* ============================================================
 * SIMULATION CONTROL PRESETS
 * ============================================================
 */

export const SIMULATION_TIME_PRESETS = [
  {
    label: "+1 min",
    value: {
      minutes: 1,
    },
  },

  {
    label: "+5 min",
    value: {
      minutes: 5,
    },
  },

  {
    label: "+10 min",
    value: {
      minutes: 10,
    },
  },

  {
    label: "+1 hour",
    value: {
      hours: 1,
    },
  },
] as const;


/* ============================================================
 * UI
 * ============================================================
 */

export const UI_BREAKPOINTS = {
  desktop: 1280,
  tablet: 768,
} as const;
