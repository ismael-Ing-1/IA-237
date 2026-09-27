import { useMutation, useQueryClient } from "@tanstack/react-query";
import {
  approveCoalition,
  executeCoalition,
  rejectCoalition,
} from "../api/coalitions.api";
import { queryKeys } from "./queryKeys";

export function useCoalitionActions() {
  const queryClient = useQueryClient();

  async function refresh() {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: queryKeys.coalitionDeals.root }),
      queryClient.invalidateQueries({ queryKey: queryKeys.simulation.root }),
      queryClient.invalidateQueries({ queryKey: queryKeys.users.all }),
      queryClient.invalidateQueries({ queryKey: queryKeys.market.root }),
      queryClient.invalidateQueries({ queryKey: queryKeys.agents.root }),
    ]);
  }

  const approve = useMutation({
    mutationFn: ({ coalitionId, userId }: { coalitionId: string; userId: string }) =>
      approveCoalition(coalitionId, userId),
    onSuccess: refresh,
  });

  const reject = useMutation({
    mutationFn: ({ coalitionId, userId }: { coalitionId: string; userId: string }) =>
      rejectCoalition(coalitionId, userId),
    onSuccess: refresh,
  });

  const execute = useMutation({
    mutationFn: (coalitionId: string) => executeCoalition(coalitionId),
    onSuccess: refresh,
  });

  return {
    approve: approve.mutateAsync,
    reject: reject.mutateAsync,
    execute: execute.mutateAsync,
    isApproving: approve.isPending,
    isRejecting: reject.isPending,
    isExecuting: execute.isPending,
    isPending: approve.isPending || reject.isPending || execute.isPending,
  };
}
