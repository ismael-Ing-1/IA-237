import { apiClient } from "./client";

import type {
  EventExecution,
  MarketEvent,
  SimulationState,
} from "../types/simulation";


export interface AdvanceSimulationInput {
  seconds?: number;
  minutes?: number;
  hours?: number;
  days?: number;
}


export interface AdvanceSimulationResponse {
  current_time: string;
  executions: EventExecution[];
}


export interface RunUntilInput {
  target_time: string;
}


export async function getSimulationState(): Promise<SimulationState> {
  const response = await apiClient.get<SimulationState>(
    "/simulation/state",
  );

  return response.data;
}


export async function getScheduledEvents(): Promise<MarketEvent[]> {
  const response = await apiClient.get<MarketEvent[]>(
    "/simulation/events",
  );

  return response.data;
}


export async function getEventHistory(): Promise<EventExecution[]> {
  const response = await apiClient.get<EventExecution[]>(
    "/simulation/history",
  );

  return response.data;
}


export async function scheduleEvent(
  event: MarketEvent,
): Promise<MarketEvent> {
  const response = await apiClient.post<MarketEvent>(
    "/simulation/events",
    event,
  );

  return response.data;
}


export async function advanceSimulation(
  input: AdvanceSimulationInput,
): Promise<AdvanceSimulationResponse> {
  const response = await apiClient.post<AdvanceSimulationResponse>(
    "/simulation/advance",
    input,
  );

  return response.data;
}


export async function runSimulationUntil(
  input: RunUntilInput,
): Promise<AdvanceSimulationResponse> {
  const response = await apiClient.post<AdvanceSimulationResponse>(
    "/simulation/run-until",
    input,
  );

  return response.data;
}
