import { useMutation, useQueryClient } from "@tanstack/react-query";
import { stopAgentObjective } from "../api/agentRuntime.api";
import { queryKeys } from "./queryKeys";
export function useStopAgentObjective() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: stopAgentObjective,
    onSuccess: async () => { await Promise.all([
      client.invalidateQueries({ queryKey: queryKeys.simulation.root }),
      client.invalidateQueries({ queryKey: queryKeys.negotiations.all }),
    ]); },
  });
}
