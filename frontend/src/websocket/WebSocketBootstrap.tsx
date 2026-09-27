import {
  useEffect,
  useState,
} from "react";

import {
  useQueryClient,
} from "@tanstack/react-query";

import {
  createRealtimeBridge,
} from "./realtime";

import {
  realtimeSocket,
  type SocketStatus,
} from "./socket";


/**
 * Mount once near the root of the app.
 *
 * It starts the shared WebSocket bridge and keeps the connection
 * alive while the React application is mounted.
 */
export function WebSocketBootstrap() {
  const queryClient =
    useQueryClient();

  const [
    status,
    setStatus,
  ] =
    useState<SocketStatus>(
      realtimeSocket.getStatus(),
    );

  useEffect(() => {
    const bridge =
      createRealtimeBridge(
        queryClient,
      );

    const unsubscribeStatus =
      realtimeSocket
        .subscribeStatus(
          setStatus,
        );

    bridge.start();

    return () => {
      unsubscribeStatus();

      bridge.stop();
    };
  }, [queryClient]);

  return (
    <span
      aria-hidden="true"
      data-websocket-status={
        status
      }
      className="hidden"
    />
  );
}
