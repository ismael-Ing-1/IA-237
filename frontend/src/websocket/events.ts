import type {
  WebSocketEvent,
  WebSocketEventType,
} from "../types/websocket";


export const KNOWN_WEBSOCKET_EVENT_TYPES:
  WebSocketEventType[] = [
  "connected",
  "agent_started",
  "agent_action",
  "agent_notified",
  "agent_stopped",
  "provider_found",
  "market_updated",
  "user_online",
  "user_offline",
  "negotiation_started",
  "negotiation_updated",
  "offer_sent",
  "counter_offer_sent",
  "offer_accepted",
  "offer_rejected",
  "privacy_check_passed",
  "privacy_blocked",
  "coalition_search_started",
  "coalition_search_completed",
  "coalition_found",
  "coalition_selected",
  "coalition_agent_evaluated",
  "coalition_rejected",
  "coalition_human_approval_required",
  "coalition_human_approved",
  "coalition_human_rejected",
  "coalition_approved",
  "coalition_cancelled",
  "coalition_exchange_started",
  "coalition_exchange_completed",
  "coalition_exchange_failed",
  "mediation_started",
  "mediation_suggestion",
  "llm_thinking",
  "llm_decision",
  "llm_shadow_decision",
  "llm_policy_validated",
  "llm_fallback",
  "human_approval_required",
  "human_approved",
  "human_rejected",
  "exchange_started",
  "exchange_completed",
  "exchange_failed",
  "market_event_scheduled",
  "market_event_executed",
  "simulation_time_updated",
  "error",
];


const KNOWN_EVENT_SET =
  new Set<string>(
    KNOWN_WEBSOCKET_EVENT_TYPES,
  );


export function isKnownWebSocketEventType(
  value: unknown,
): value is WebSocketEventType {
  return (
    typeof value === "string" &&
    KNOWN_EVENT_SET.has(value)
  );
}


export function isWebSocketEvent(
  value: unknown,
): value is WebSocketEvent {
  if (
    !value ||
    typeof value !== "object"
  ) {
    return false;
  }

  const event =
    value as Record<
      string,
      unknown
    >;

  return (
    typeof event.event_id ===
      "string" &&
    isKnownWebSocketEventType(
      event.type,
    ) &&
    typeof event.timestamp ===
      "string" &&
    (
      event.user_id === null ||
      typeof event.user_id ===
        "string"
    ) &&
    (
      event.entity_id === null ||
      typeof event.entity_id ===
        "string"
    ) &&
    "payload" in event
  );
}


export function parseWebSocketEvent(
  raw: string,
): WebSocketEvent | null {
  try {
    const parsed =
      JSON.parse(raw);

    if (
      !isWebSocketEvent(
        parsed,
      )
    ) {
      return null;
    }

    return parsed;
  } catch {
    return null;
  }
}


export function websocketEventNeedsNegotiationRefresh(
  type: WebSocketEventType,
): boolean {
  return [
    "negotiation_started",
    "negotiation_updated",
    "offer_sent",
    "counter_offer_sent",
    "offer_accepted",
    "offer_rejected",
    "human_approval_required",
    "human_approved",
    "human_rejected",
    "exchange_started",
    "exchange_completed",
    "exchange_failed",
    "mediation_started",
    "mediation_suggestion",
  ].includes(type);
}


export function websocketEventNeedsMarketRefresh(
  type: WebSocketEventType,
): boolean {
  return [
    "provider_found",
    "market_updated",
    "user_online",
    "user_offline",
    "exchange_completed",
    "coalition_exchange_completed",
    "market_event_executed",
  ].includes(type);
}


export function websocketEventNeedsSimulationRefresh(
  type: WebSocketEventType,
): boolean {
  if (type.startsWith("coalition_")) return true;

  return [
    "market_updated",
    "user_online",
    "user_offline",
    "exchange_completed",
    "exchange_failed",
    "market_event_scheduled",
    "market_event_executed",
    "simulation_time_updated",
  ].includes(type);
}


export function websocketEventNeedsUserRefresh(
  type: WebSocketEventType,
): boolean {
  return [
    "user_online",
    "user_offline",
    "exchange_completed",
    "coalition_exchange_completed",
    "market_event_executed",
  ].includes(type);
}
