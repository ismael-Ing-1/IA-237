import {
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";

import {
  createUser,
  getUser,
  getUserDashboard,
  getUsers,
  updateUserStrategy,
} from "../api/users.api";

import type {
  NegotiationStrategy,
  User,
  UserDashboard,
} from "../types/user";

import {
  queryKeys,
} from "./queryKeys";


/**
 * Public marketplace users.
 */
export function useUsers() {
  return useQuery({
    queryKey: queryKeys.users.all,
    queryFn: getUsers,
  });
}


/**
 * Public profile for any marketplace user.
 */
export function usePublicUser(
  userId: string | null | undefined,
) {
  return useQuery({
    queryKey: userId
      ? queryKeys.users.public(userId)
      : ["users", "public", "disabled"],

    queryFn: () => getUser(userId!),

    enabled: Boolean(userId),
  });
}


/**
 * Owner-facing dashboard information.
 *
 * This must only be used for the currently selected/authenticated user.
 */
export function useUserDashboard(
  userId: string | null | undefined,
) {
  return useQuery({
    queryKey: userId
      ? queryKeys.users.dashboard(userId)
      : ["users", "dashboard", "disabled"],

    queryFn: () => getUserDashboard(userId!),

    enabled: Boolean(userId),
  });
}


/**
 * User creation mutation.
 */
export function useCreateUser() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (user: User) =>
      createUser(user),

    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({
          queryKey: queryKeys.users.all,
        }),

        queryClient.invalidateQueries({
          queryKey: queryKeys.simulation.root,
        }),

        queryClient.invalidateQueries({
          queryKey: queryKeys.market.root,
        }),
      ]);
    },
  });
}


/**
 * Updates the selected PersonalAgent policy.
 *
 * The backend User object is shared with PersonalAgent, so the
 * next decision immediately reads the new strategy.
 */
export function useUpdateUserStrategy(
  userId: string | null | undefined,
) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (
      strategy: NegotiationStrategy,
    ) => {
      if (!userId) {
        throw new Error(
          "Missing userId.",
        );
      }

      return updateUserStrategy(
        userId,
        strategy,
      );
    },

    onSuccess: async (
      result,
    ) => {
      if (!userId) {
        return;
      }

      queryClient.setQueryData<UserDashboard>(
        queryKeys.users.dashboard(
          userId,
        ),
        (current) =>
          current
            ? {
                ...current,
                strategy:
                  result.strategy,
              }
            : current,
      );

      await Promise.all([
        queryClient.invalidateQueries({
          queryKey:
            queryKeys.users.dashboard(
              userId,
            ),
        }),

        queryClient.invalidateQueries({
          queryKey:
            queryKeys.simulation.root,
        }),
      ]);
    },
  });
}
