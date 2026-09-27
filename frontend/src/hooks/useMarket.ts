import {
  useQuery,
} from "@tanstack/react-query";

import {
  getProviders,
  getRequesters,
} from "../api/market.api";

import {
  queryKeys,
} from "./queryKeys";


export interface UseProvidersOptions {
  requesterId?: string;

  enabled?: boolean;
}


export interface UseRequestersOptions {
  providerId?: string;

  enabled?: boolean;
}


/**
 * Finds public providers for a resource.
 */
export function useProviders(
  resourceType: string | null | undefined,
  options: UseProvidersOptions = {},
) {
  const enabled =
    Boolean(resourceType) &&
    (options.enabled ?? true);

  return useQuery({
    queryKey: resourceType
      ? queryKeys.market.providers(
          resourceType,
          options.requesterId,
        )
      : ["market", "providers", "disabled"],

    queryFn: () =>
      getProviders(
        resourceType!,
        {
          requesterId: options.requesterId,
        },
      ),

    enabled,
  });
}


/**
 * Finds public requesters for a resource.
 */
export function useRequesters(
  resourceType: string | null | undefined,
  options: UseRequestersOptions = {},
) {
  const enabled =
    Boolean(resourceType) &&
    (options.enabled ?? true);

  return useQuery({
    queryKey: resourceType
      ? queryKeys.market.requesters(
          resourceType,
          options.providerId,
        )
      : ["market", "requesters", "disabled"],

    queryFn: () =>
      getRequesters(
        resourceType!,
        {
          providerId: options.providerId,
        },
      ),

    enabled,
  });
}


/**
 * Convenience composite hook for market exploration.
 */
export function useMarket(
  resourceType: string | null | undefined,
  options: {
    requesterId?: string;
    providerId?: string;
    includeProviders?: boolean;
    includeRequesters?: boolean;
  } = {},
) {
  const providersQuery = useProviders(
    resourceType,
    {
      requesterId: options.requesterId,
      enabled:
        options.includeProviders ?? true,
    },
  );

  const requestersQuery = useRequesters(
    resourceType,
    {
      providerId: options.providerId,
      enabled:
        options.includeRequesters ?? true,
    },
  );

  return {
    providers:
      providersQuery.data ?? [],

    requesters:
      requestersQuery.data ?? [],

    providersQuery,

    requestersQuery,

    isLoading:
      providersQuery.isLoading ||
      requestersQuery.isLoading,

    isFetching:
      providersQuery.isFetching ||
      requestersQuery.isFetching,

    error:
      providersQuery.error ??
      requestersQuery.error ??
      null,
  };
}
