import type { SimulationState } from "./simulation";

export type AgentRuntimeStatus =
  | "idle" | "searching" | "negotiating" | "waiting_human" | "approved"
  | "searching_coalition" | "coalition_proposed" | "coalition_validating"
  | "coalition_waiting_humans" | "coalition_approved" | "exhausted"
  | "cancelled" | "completed" | "failed";

export interface AgentRuntimeState {
  user_id: string;
  status: AgentRuntimeStatus;
  reason: string;
  negotiation_id: string | null;
  objective_id: string | null;
  updated_at: string | null;
}

export type RuntimeSimulationState = SimulationState & {
  agent_states?: AgentRuntimeState[];
};
