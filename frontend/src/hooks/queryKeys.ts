/**
 * Central TanStack Query keys.
 *
 * Keeping them in one file is important because REST mutations and
 * WebSocket events must invalidate the exact same caches.
 */
export const queryKeys = {
  health: ["health"] as const,

  users: {
    all: ["users"] as const,

    public: (userId: string) =>
      ["users", "public", userId] as const,

    dashboard: (userId: string) =>
      ["users", "dashboard", userId] as const,
  },

  market: {
    root: ["market"] as const,

    providers: (
      resourceType: string,
      requesterId?: string,
    ) =>
      [
        "market",
        "providers",
        resourceType,
        requesterId ?? null,
      ] as const,

    requesters: (
      resourceType: string,
      providerId?: string,
    ) =>
      [
        "market",
        "requesters",
        resourceType,
        providerId ?? null,
      ] as const,
  },

  negotiations: {
    all: ["negotiations"] as const,

    detail: (negotiationId: string) =>
      ["negotiations", negotiationId] as const,
  },

  coalitionDeals: {
    root: ["coalition-deals"] as const,

    detail: (coalitionId: string) =>
      ["coalition-deals", coalitionId] as const,
  },

  simulation: {
    root: ["simulation"] as const,

    state: ["simulation", "state"] as const,

    events: ["simulation", "events"] as const,

    history: ["simulation", "history"] as const,
  },

  agents: {
    root: ["agents"] as const,

    candidates: (
      userId: string,
      resourceType: string,
    ) =>
      [
        "agents",
        userId,
        "candidates",
        resourceType,
      ] as const,

    coalitions: (
      userId: string,
      minSize?: number,
      maxSize?: number,
    ) =>
      [
        "agents",
        userId,
        "coalitions",
        minSize ?? null,
        maxSize ?? null,
      ] as const,
  },
} as const;
