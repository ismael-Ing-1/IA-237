import type { QueryClient } from "@tanstack/react-query";
import { queryKeys } from "../hooks/queryKeys";
import { useActivityStore } from "../store/activity.store";
import { useUIStore } from "../store/ui.store";
import { eventNegotiationId, isUrgentEvent, usePresentationStore } from "../store/presentation.store";
import type { WebSocketEvent } from "../types/websocket";
import type { AgentRuntimeState, RuntimeSimulationState } from "../types/runtime";
import { activityPresentationQueue } from "./activityQueue";
import {
  websocketEventNeedsMarketRefresh, websocketEventNeedsNegotiationRefresh,
  websocketEventNeedsSimulationRefresh, websocketEventNeedsUserRefresh,
} from "./events";

const seen = new Set<string>();
const object = (v: unknown): Record<string, unknown> | null =>
  v !== null && typeof v === "object" && !Array.isArray(v) ? v as Record<string, unknown> : null;

export async function handleRealtimeEvent(client: QueryClient, event: WebSocketEvent): Promise<void> {
  if (seen.has(event.event_id)) return;
  seen.add(event.event_id);
  if (seen.size > 2000) seen.delete(seen.values().next().value!);
  const tasks: Promise<unknown>[] = [];
  const payload = object(event.payload);
  const reset = event.type === "market_updated" && payload?.reset === true;

  if (reset || event.type === "connected") {
    activityPresentationQueue.clear();
    usePresentationStore.getState().reset();
    useUIStore.getState().closeApprovalModal();
  }
  if (reset) {
    useUIStore.getState().resetUI();
    useActivityStore.getState().clearActivities();
    for (const queryKey of [queryKeys.simulation.root, queryKeys.users.all,
      queryKeys.negotiations.all, queryKeys.agents.root, queryKeys.market.root]) {
      tasks.push(client.resetQueries({ queryKey }));
    }
  }

  const id = eventNegotiationId(event);
  // Verrouillage immédiat d'un deal devenu non-actionnable, AVANT de rejouer le journal.
  usePresentationStore.getState().observe(event);
  if (isUrgentEvent(event) && id === useUIStore.getState().selectedNegotiationId) {
    useUIStore.getState().closeApprovalModal();
  }

  // L'état de l'agent n'est plus calculé à partir d'un vieux message WAIT_HUMAN.
  const runtime = object(payload?.agent_state);
  if (runtime && typeof runtime.user_id === "string" && typeof runtime.status === "string") {
    client.setQueryData<RuntimeSimulationState>(queryKeys.simulation.state, (current) => current ? {
      ...current, agent_states: [...(current.agent_states ?? []).filter((s) => s.user_id !== runtime.user_id),
        runtime as unknown as AgentRuntimeState],
    } : current);
  }

  activityPresentationQueue.enqueue(event, isUrgentEvent(event));
  const resync = event.type === "connected" || event.type === "market_updated";
  const negotiationChanged = websocketEventNeedsNegotiationRefresh(event.type);
  const invalidate = (queryKey: readonly unknown[]) => {
    tasks.push(client.invalidateQueries({ queryKey }, { cancelRefetch: false }));
  };
  if (resync || negotiationChanged) invalidate(queryKeys.negotiations.all);
  if (resync || negotiationChanged || websocketEventNeedsSimulationRefresh(event.type) || runtime)
    invalidate(queryKeys.simulation.root);
  if (resync || websocketEventNeedsMarketRefresh(event.type)) invalidate(queryKeys.market.root);
  if (resync || websocketEventNeedsUserRefresh(event.type)) invalidate(queryKeys.users.all);
  if (event.user_id && typeof payload?.strategy === "string") invalidate(queryKeys.users.dashboard(event.user_id));
  if (resync || event.type.startsWith("coalition_") || event.type === "market_event_executed")
    invalidate(queryKeys.agents.root);
  await Promise.allSettled(tasks);
}
