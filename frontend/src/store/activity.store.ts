import {
  create,
} from "zustand";

import type {
  AgentActivity,
  AgentActivityKind,
} from "../types/agent";

import type {
  WebSocketEvent,
} from "../types/websocket";


const DEFAULT_MAX_ACTIVITIES =
  250;


interface ActivityState {
  activities: AgentActivity[];

  maxActivities: number;

  addActivity: (
    activity: AgentActivity,
  ) => void;

  addActivities: (
    activities: AgentActivity[],
  ) => void;

  addFromWebSocketEvent: (
    event: WebSocketEvent,
  ) => void;

  clearActivities: () => void;

  clearUserActivities: (
    userId: string,
  ) => void;

  setMaxActivities: (
    maxActivities: number,
  ) => void;
}


function trimActivities(
  activities: AgentActivity[],
  maxActivities: number,
): AgentActivity[] {
  if (
    activities.length <=
    maxActivities
  ) {
    return activities;
  }

  return activities.slice(
    activities.length -
      maxActivities,
  );
}


function activityKindFromEvent(
  eventType: WebSocketEvent["type"],
): AgentActivityKind {
  if (
    eventType.startsWith(
      "negotiation",
    ) ||
    eventType.includes(
      "offer",
    )
  ) {
    return "negotiation";
  }

  if (
    eventType.startsWith(
      "privacy",
    )
  ) {
    return "privacy";
  }

  if (
    eventType.startsWith(
      "coalition",
    )
  ) {
    return "coalition";
  }

  if (
    eventType.startsWith(
      "mediation",
    )
  ) {
    return "mediation";
  }

  if (
    eventType.startsWith(
      "human_",
    )
  ) {
    return "approval";
  }

  if (
    eventType.startsWith(
      "exchange",
    )
  ) {
    return "exchange";
  }

  if (
    eventType ===
      "provider_found" ||
    eventType ===
      "market_updated" ||
    eventType ===
      "user_online" ||
    eventType ===
      "user_offline"
  ) {
    return "market_search";
  }

  if (
    eventType.startsWith(
      "agent_",
    )
  ) {
    return "decision";
  }

  return "system";
}


function humanizeEventType(
  value: string,
): string {
  return value
    .replaceAll("_", " ")
    .replace(
      /\b\w/g,
      (character) =>
        character.toUpperCase(),
    );
}


function getMessageFromPayload(
  payload: unknown,
): string {
  if (
    payload &&
    typeof payload === "object"
  ) {
    const object =
      payload as Record<
        string,
        unknown
      >;

    if (
      typeof object.message ===
      "string"
    ) {
      return object.message;
    }

    if (
      typeof object.reason ===
      "string"
    ) {
      return object.reason;
    }

    const decision =
      object.decision;

    if (
      decision &&
      typeof decision === "object"
    ) {
      const decisionObject =
        decision as Record<
          string,
          unknown
        >;

      if (
        typeof decisionObject.reason ===
        "string"
      ) {
        return decisionObject.reason;
      }
    }
  }

  return "Real-time system update.";
}


export const useActivityStore =
  create<ActivityState>(
    (set) => ({
      activities: [],

      maxActivities:
        DEFAULT_MAX_ACTIVITIES,

      addActivity: (
        activity,
      ) => {
        set((state) => ({
          activities:
            trimActivities(
              [
                ...state.activities,
                activity,
              ],
              state.maxActivities,
            ),
        }));
      },

      addActivities: (
        activities,
      ) => {
        set((state) => ({
          activities:
            trimActivities(
              [
                ...state.activities,
                ...activities,
              ],
              state.maxActivities,
            ),
        }));
      },

      addFromWebSocketEvent: (
        event,
      ) => {
        set((state) => {
          const activity:
            AgentActivity = {
            id: event.event_id,

            user_id:
              event.user_id,

            kind:
              activityKindFromEvent(
                event.type,
              ),

            title:
              humanizeEventType(
                event.type,
              ),

            message:
              getMessageFromPayload(
                event.payload,
              ),

            timestamp:
              event.timestamp,

            metadata: {
              entity_id:
                event.entity_id,

              event_type:
                event.type,

              payload:
                event.payload,
            },
          };

          return {
            activities:
              trimActivities(
                [
                  ...state.activities,
                  activity,
                ],
                state.maxActivities,
              ),
          };
        });
      },

      clearActivities: () => {
        set({
          activities: [],
        });
      },

      clearUserActivities: (
        userId,
      ) => {
        set((state) => ({
          activities:
            state.activities.filter(
              (activity) =>
                activity.user_id !==
                userId,
            ),
        }));
      },

      setMaxActivities: (
        maxActivities,
      ) => {
        const safeMax =
          Math.max(
            10,
            maxActivities,
          );

        set((state) => ({
          maxActivities:
            safeMax,

          activities:
            trimActivities(
              state.activities,
              safeMax,
            ),
        }));
      },
    }),
  );


/*
 * ------------------------------------------------------------
 * SELECTORS
 * ------------------------------------------------------------
 */

export const selectActivities = (
  state: ActivityState,
) => state.activities;


export function selectActivitiesForUser(
  userId: string,
) {
  return (
    state: ActivityState,
  ) =>
    state.activities.filter(
      (activity) =>
        activity.user_id === userId,
    );
}
