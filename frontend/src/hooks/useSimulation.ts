import {
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";

import {
  advanceSimulation,
  getEventHistory,
  getScheduledEvents,
  getSimulationState,
  runSimulationUntil,
  scheduleEvent,
} from "../api/simulation.api";

import type {
  AdvanceSimulationInput,
  RunUntilInput,
} from "../api/simulation.api";

import type {
  MarketEvent,
} from "../types/simulation";

import {
  queryKeys,
} from "./queryKeys";


async function invalidateSimulationRelatedQueries(
  queryClient: ReturnType<typeof useQueryClient>,
) {
  await Promise.all([
    queryClient.invalidateQueries({
      queryKey: queryKeys.simulation.root,
    }),

    queryClient.invalidateQueries({
      queryKey: queryKeys.users.all,
    }),

    queryClient.invalidateQueries({
      queryKey: queryKeys.market.root,
    }),

    queryClient.invalidateQueries({
      queryKey: queryKeys.negotiations.all,
    }),

    queryClient.invalidateQueries({
      queryKey: queryKeys.coalitionDeals.root,
    }),
  ]);
}


/**
 * Main hook used by the dashboard.
 *
 * GET /simulation/state already contains:
 * - current time
 * - users
 * - active negotiations
 * - completed negotiations
 * - scheduled events
 * - event history
 */
export function useSimulation() {
  const queryClient = useQueryClient();

  const stateQuery = useQuery({
    queryKey: queryKeys.simulation.state,
    queryFn: getSimulationState,
  });

  const advanceMutation = useMutation({
    mutationFn: (
      input: AdvanceSimulationInput,
    ) => advanceSimulation(input),

    onSuccess: async () => {
      await invalidateSimulationRelatedQueries(
        queryClient,
      );
    },
  });

  const runUntilMutation = useMutation({
    mutationFn: (
      input: RunUntilInput,
    ) => runSimulationUntil(input),

    onSuccess: async () => {
      await invalidateSimulationRelatedQueries(
        queryClient,
      );
    },
  });

  const scheduleEventMutation = useMutation({
    mutationFn: (
      event: MarketEvent,
    ) => scheduleEvent(event),

    onSuccess: async () => {
      await queryClient.invalidateQueries({
        queryKey: queryKeys.simulation.root,
      });
    },
  });

  const state = stateQuery.data;

  return {
    ...stateQuery,

    state,

    currentTime:
      state?.current_time ?? null,

    users:
      state?.users ?? [],

    activeNegotiations:
      state?.active_negotiations ?? [],

    completedNegotiations:
      state?.completed_negotiations ?? [],

    scheduledEvents:
      state?.scheduled_events ?? [],

    eventHistory:
      state?.event_history ?? [],

    coalitions:
      state?.coalitions ?? [],

    coalitionDeals:
      state?.coalition_deals ?? [],

    advanceTime: advanceMutation.mutateAsync,

    runUntil: runUntilMutation.mutateAsync,

    scheduleEvent:
      scheduleEventMutation.mutateAsync,

    isAdvancing:
      advanceMutation.isPending,

    isRunningUntil:
      runUntilMutation.isPending,

    isSchedulingEvent:
      scheduleEventMutation.isPending,

    advanceError:
      advanceMutation.error,

    runUntilError:
      runUntilMutation.error,

    scheduleEventError:
      scheduleEventMutation.error,
  };
}


/**
 * Dedicated query for components that only need upcoming events.
 */
export function useScheduledEvents() {
  return useQuery({
    queryKey: queryKeys.simulation.events,
    queryFn: getScheduledEvents,
  });
}


/**
 * Dedicated query for components that only need simulation history.
 */
export function useEventHistory() {
  return useQuery({
    queryKey: queryKeys.simulation.history,
    queryFn: getEventHistory,
  });
}
