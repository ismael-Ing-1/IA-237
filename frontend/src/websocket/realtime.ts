import type {
  QueryClient,
} from "@tanstack/react-query";

import {
  realtimeSocket,
  type SocketStatus,
} from "./socket";

import {
  handleRealtimeEvent,
} from "./eventHandlers";


export interface RealtimeBridge {
  start: () => void;

  stop: () => void;

  getStatus: () => SocketStatus;
}


export function createRealtimeBridge(
  queryClient: QueryClient,
): RealtimeBridge {
  let unsubscribe:
    (() => void) | null =
      null;

  function start() {
    if (!unsubscribe) {
      unsubscribe =
        realtimeSocket.subscribe(
          (event) => {
            void handleRealtimeEvent(
              queryClient,
              event,
            );
          },
        );
    }

    realtimeSocket.connect();
  }

  function stop() {
    unsubscribe?.();

    unsubscribe = null;

    realtimeSocket.disconnect();
  }

  return {
    start,

    stop,

    getStatus: () =>
      realtimeSocket.getStatus(),
  };
}
