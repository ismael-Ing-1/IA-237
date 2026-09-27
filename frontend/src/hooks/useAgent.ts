import {
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";

import {
  discoverAgentCandidates,
  getCoalitions,
  handleAgentOffer,
  mediateNegotiation,
  pursueAgentRequest,
} from "../api/agents.api";

import type {
  HandleOfferInput,
  PursueRequestInput,
} from "../api/agents.api";

import {
  queryKeys,
} from "./queryKeys";


async function invalidateAgentRelatedQueries(
  queryClient: ReturnType<typeof useQueryClient>,
) {
  await Promise.all([
    queryClient.invalidateQueries({
      queryKey: queryKeys.agents.root,
    }),

    queryClient.invalidateQueries({
      queryKey: queryKeys.negotiations.all,
    }),

    queryClient.invalidateQueries({
      queryKey: queryKeys.simulation.root,
    }),

    queryClient.invalidateQueries({
      queryKey: queryKeys.market.root,
    }),

    queryClient.invalidateQueries({
      queryKey: queryKeys.users.all,
    }),
  ]);
}


/**
 * PersonalAgent command mutations.
 *
 * The FastAPI agent endpoints must exist for these mutations to work.
 */
export function useAgent(
  userId: string | null | undefined,
) {
  const queryClient = useQueryClient();

  const pursueMutation = useMutation({
    mutationFn: (
      input: PursueRequestInput,
    ) => {
      if (!userId) {
        throw new Error(
          "Missing userId.",
        );
      }

      return pursueAgentRequest(
        userId,
        input,
      );
    },

    onSuccess: async () => {
      await invalidateAgentRelatedQueries(
        queryClient,
      );
    },
  });

  const handleOfferMutation = useMutation({
    mutationFn: (
      input: HandleOfferInput,
    ) => {
      if (!userId) {
        throw new Error(
          "Missing userId.",
        );
      }

      return handleAgentOffer(
        userId,
        input,
      );
    },

    onSuccess: async () => {
      await invalidateAgentRelatedQueries(
        queryClient,
      );
    },
  });

  return {
    pursueRequest:
      pursueMutation.mutateAsync,

    handleOffer:
      handleOfferMutation.mutateAsync,

    pursueResult:
      pursueMutation.data ?? null,

    handleOfferResult:
      handleOfferMutation.data ?? null,

    isPursuing:
      pursueMutation.isPending,

    isHandlingOffer:
      handleOfferMutation.isPending,

    pursueError:
      pursueMutation.error,

    handleOfferError:
      handleOfferMutation.error,
  };
}


/**
 * Public candidate discovery for a PersonalAgent.
 */
export function useAgentCandidates(
  userId: string | null | undefined,
  resourceType: string | null | undefined,
) {
  const enabled =
    Boolean(userId) &&
    Boolean(resourceType);

  return useQuery({
    queryKey:
      userId && resourceType
        ? queryKeys.agents.candidates(
            userId,
            resourceType,
          )
        : [
            "agents",
            "candidates",
            "disabled",
          ],

    queryFn: () =>
      discoverAgentCandidates(
        userId!,
        resourceType!,
      ),

    enabled,
  });
}


/**
 * Coalition discovery for an agent.
 */
export function useCoalitions(
  userId: string | null | undefined,
  options: {
    minSize?: number;
    maxSize?: number;
    enabled?: boolean;
  } = {},
) {
  const enabled =
    Boolean(userId) &&
    (options.enabled ?? true);

  return useQuery({
    queryKey: userId
      ? queryKeys.agents.coalitions(
          userId,
          options.minSize,
          options.maxSize,
        )
      : [
          "agents",
          "coalitions",
          "disabled",
        ],

    queryFn: () =>
      getCoalitions(
        userId!,
        {
          minSize: options.minSize,
          maxSize: options.maxSize,
        },
      ),

    enabled,
  });
}


/**
 * MediatorAgent action for a negotiation.
 */
export function useMediator(
  negotiationId: string | null | undefined,
) {
  const queryClient = useQueryClient();

  const mutation = useMutation({
    mutationFn: () => {
      if (!negotiationId) {
        throw new Error(
          "Missing negotiationId.",
        );
      }

      return mediateNegotiation(
        negotiationId,
      );
    },

    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({
          queryKey: queryKeys.negotiations.all,
        }),

        negotiationId
          ? queryClient.invalidateQueries({
              queryKey:
                queryKeys.negotiations.detail(
                  negotiationId,
                ),
            })
          : Promise.resolve(),

        queryClient.invalidateQueries({
          queryKey: queryKeys.simulation.root,
        }),
      ]);
    },
  });

  return {
    mediate: mutation.mutateAsync,

    result:
      mutation.data ?? null,

    isMediating:
      mutation.isPending,

    error:
      mutation.error,

    reset:
      mutation.reset,
  };
}
