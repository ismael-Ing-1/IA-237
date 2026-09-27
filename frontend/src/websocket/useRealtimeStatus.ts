import {
  useEffect,
  useState,
} from "react";

import {
  realtimeSocket,
  type SocketStatus,
} from "./socket";


export function useRealtimeStatus():
  SocketStatus {
  const [
    status,
    setStatus,
  ] =
    useState<SocketStatus>(
      realtimeSocket.getStatus(),
    );

  useEffect(() => {
    return realtimeSocket
      .subscribeStatus(
        setStatus,
      );
  }, []);

  return status;
}


export function useRealtimeConnected():
  boolean {
  return (
    useRealtimeStatus() ===
    "open"
  );
}
