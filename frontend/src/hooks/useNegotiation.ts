import {
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";

import {
  acceptOffer,
  approveNegotiation,
  cancelNegotiation,
  createNegotiation,
  executeNegotiation,
  getNegotiation,
  getNegotiations,
  rejectNegotiation,
  rejectOffer,
  requestHumanApproval,
  sendCounterOffer,
  sendOffer,
} from "../api/negotiations.api";

import type {
  CounterOfferInput,
  CreateNegotiationInput,
  OfferInput,
  RejectOfferInput,
} from "../api/negotiations.api";

import {
  queryKeys,
} from "./queryKeys";


async function invalidateNegotiationQueries(
  queryClient: ReturnType<typeof useQueryClient>,
  negotiationId?: string,
) {
  const invalidations = [
    queryClient.invalidateQueries({
      queryKey: queryKeys.negotiations.all,
    }),

    queryClient.invalidateQueries({
      queryKey: queryKeys.simulation.root,
    }),
  ];

  if (negotiationId) {
    invalidations.push(
      queryClient.invalidateQueries({
        queryKey:
          queryKeys.negotiations.detail(
            negotiationId,
          ),
      }),
    );
  }

  await Promise.all(invalidations);
}


/**
 * Query all negotiations.
 */
export function useNegotiations() {
  return useQuery({
    queryKey: queryKeys.negotiations.all,
    queryFn: getNegotiations,
  });
}


/**
 * Create a manual negotiation.
 *
 * PersonalAgent-driven negotiations normally use the agent API instead.
 */
export function useCreateNegotiation() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (
      input: CreateNegotiationInput,
    ) => createNegotiation(input),

    onSuccess: async (negotiation) => {
      queryClient.setQueryData(
        queryKeys.negotiations.detail(
          negotiation.id,
        ),
        negotiation,
      );

      await invalidateNegotiationQueries(
        queryClient,
      );
    },
  });
}


/**
 * Full hook for a single negotiation.
 */
export function useNegotiation(
  negotiationId: string | null | undefined,
) {
  const queryClient = useQueryClient();

  const query = useQuery({
    queryKey: negotiationId
      ? queryKeys.negotiations.detail(
          negotiationId,
        )
      : ["negotiations", "disabled"],

    queryFn: () =>
      getNegotiation(negotiationId!),

    enabled: Boolean(negotiationId),
  });

  const sendOfferMutation = useMutation({
    mutationFn: (
      input: OfferInput,
    ) => {
      if (!negotiationId) {
        throw new Error(
          "Missing negotiationId.",
        );
      }

      return sendOffer(
        negotiationId,
        input,
      );
    },

    onSuccess: async () => {
      await invalidateNegotiationQueries(
        queryClient,
        negotiationId ?? undefined,
      );
    },
  });

  const counterOfferMutation = useMutation({
    mutationFn: (
      input: CounterOfferInput,
    ) => {
      if (!negotiationId) {
        throw new Error(
          "Missing negotiationId.",
        );
      }

      return sendCounterOffer(
        negotiationId,
        input,
      );
    },

    onSuccess: async () => {
      await invalidateNegotiationQueries(
        queryClient,
        negotiationId ?? undefined,
      );
    },
  });

  const acceptOfferMutation = useMutation({
    mutationFn: (
      offerId: string,
    ) => {
      if (!negotiationId) {
        throw new Error(
          "Missing negotiationId.",
        );
      }

      return acceptOffer(
        negotiationId,
        offerId,
      );
    },

    onSuccess: async () => {
      await invalidateNegotiationQueries(
        queryClient,
        negotiationId ?? undefined,
      );
    },
  });

  const rejectOfferMutation = useMutation({
    mutationFn: (
      variables: {
        offerId: string;
        input?: RejectOfferInput;
      },
    ) => {
      if (!negotiationId) {
        throw new Error(
          "Missing negotiationId.",
        );
      }

      return rejectOffer(
        negotiationId,
        variables.offerId,
        variables.input,
      );
    },

    onSuccess: async () => {
      await invalidateNegotiationQueries(
        queryClient,
        negotiationId ?? undefined,
      );
    },
  });

  const requestApprovalMutation =
    useMutation({
      mutationFn: () => {
        if (!negotiationId) {
          throw new Error(
            "Missing negotiationId.",
          );
        }

        return requestHumanApproval(
          negotiationId,
        );
      },

      onSuccess: async () => {
        await invalidateNegotiationQueries(
          queryClient,
          negotiationId ?? undefined,
        );
      },
    });

  const approveMutation = useMutation({
    mutationFn: () => {
      if (!negotiationId) {
        throw new Error(
          "Missing negotiationId.",
        );
      }

      return approveNegotiation(
        negotiationId,
      );
    },

    onSuccess: async () => {
      await invalidateNegotiationQueries(
        queryClient,
        negotiationId ?? undefined,
      );
    },
  });

  const rejectMutation = useMutation({
    mutationFn: () => {
      if (!negotiationId) {
        throw new Error(
          "Missing negotiationId.",
        );
      }

      return rejectNegotiation(
        negotiationId,
      );
    },

    onSuccess: async () => {
      await invalidateNegotiationQueries(
        queryClient,
        negotiationId ?? undefined,
      );
    },
  });

  const cancelMutation = useMutation({
    mutationFn: () => {
      if (!negotiationId) {
        throw new Error(
          "Missing negotiationId.",
        );
      }

      return cancelNegotiation(
        negotiationId,
      );
    },

    onSuccess: async () => {
      await invalidateNegotiationQueries(
        queryClient,
        negotiationId ?? undefined,
      );
    },
  });

  const executeMutation = useMutation({
    mutationFn: () => {
      if (!negotiationId) {
        throw new Error(
          "Missing negotiationId.",
        );
      }

      return executeNegotiation(
        negotiationId,
      );
    },

    onSuccess: async () => {
      await Promise.all([
        invalidateNegotiationQueries(
          queryClient,
          negotiationId ?? undefined,
        ),

        queryClient.invalidateQueries({
          queryKey: queryKeys.users.all,
        }),

        queryClient.invalidateQueries({
          queryKey: queryKeys.market.root,
        }),
      ]);
    },
  });

  return {
    ...query,

    negotiation: query.data ?? null,

    sendOffer:
      sendOfferMutation.mutateAsync,

    counterOffer:
      counterOfferMutation.mutateAsync,

    acceptOffer:
      acceptOfferMutation.mutateAsync,

    rejectOffer:
      rejectOfferMutation.mutateAsync,

    requestHumanApproval:
      requestApprovalMutation.mutateAsync,

    approve:
      approveMutation.mutateAsync,

    reject:
      rejectMutation.mutateAsync,

    cancel:
      cancelMutation.mutateAsync,

    execute:
      executeMutation.mutateAsync,

    isSendingOffer:
      sendOfferMutation.isPending,

    isCountering:
      counterOfferMutation.isPending,

    isAcceptingOffer:
      acceptOfferMutation.isPending,

    isRejectingOffer:
      rejectOfferMutation.isPending,

    isRequestingApproval:
      requestApprovalMutation.isPending,

    isApproving:
      approveMutation.isPending,

    isRejecting:
      rejectMutation.isPending,

    isCancelling:
      cancelMutation.isPending,

    isExecuting:
      executeMutation.isPending,
  };
}
