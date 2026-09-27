import {
  useCallback,
  useEffect,
  useRef,
  useState,
} from "react";

import type {
  WebSocketEvent,
} from "../types/websocket";


export type WebSocketStatus =
  | "idle"
  | "connecting"
  | "open"
  | "closed"
  | "error";


export interface UseWebSocketOptions {
  /**
   * Complete WebSocket URL.
   *
   * If omitted, the hook uses:
   *
   * VITE_WS_URL
   *
   * or derives a default from VITE_API_BASE_URL.
   */
  url?: string;

  enabled?: boolean;

  reconnect?: boolean;

  maxReconnectDelayMs?: number;

  maxStoredEvents?: number;

  onEvent?: (
    event: WebSocketEvent,
  ) => void;

  onOpen?: () => void;

  onClose?: () => void;

  onError?: (
    event: Event,
  ) => void;
}


function buildDefaultWebSocketUrl(): string {
  const explicit =
    import.meta.env.VITE_WS_URL;

  if (explicit) {
    return explicit;
  }

  const apiUrl =
    import.meta.env.VITE_API_BASE_URL;

  if (apiUrl) {
    const parsed = new URL(apiUrl);

    parsed.protocol =
      parsed.protocol === "https:"
        ? "wss:"
        : "ws:";

    parsed.pathname = "/ws";
    parsed.search = "";
    parsed.hash = "";

    return parsed.toString();
  }

  if (typeof window !== "undefined") {
    const protocol =
      window.location.protocol === "https:"
        ? "wss:"
        : "ws:";

    return `${protocol}//${window.location.host}/ws`;
  }

  return "ws://localhost:8000/ws";
}


/**
 * Low-level WebSocket hook.
 *
 * The dedicated websocket/eventHandlers.ts layer can consume this hook
 * later to invalidate TanStack Query caches and build the live activity feed.
 */
export function useWebSocket(
  options: UseWebSocketOptions = {},
) {
  const {
    enabled = true,
    reconnect = true,
    maxReconnectDelayMs = 10_000,
    maxStoredEvents = 200,
  } = options;

  const url =
    options.url ??
    buildDefaultWebSocketUrl();

  const socketRef =
    useRef<WebSocket | null>(null);

  const reconnectTimerRef =
    useRef<ReturnType<typeof setTimeout> | null>(
      null,
    );

  const reconnectAttemptRef =
    useRef(0);

  const shouldReconnectRef =
    useRef(true);

  const onEventRef =
    useRef(options.onEvent);

  const onOpenRef =
    useRef(options.onOpen);

  const onCloseRef =
    useRef(options.onClose);

  const onErrorRef =
    useRef(options.onError);

  const [status, setStatus] =
    useState<WebSocketStatus>("idle");

  const [latestEvent, setLatestEvent] =
    useState<WebSocketEvent | null>(
      null,
    );

  const [events, setEvents] =
    useState<WebSocketEvent[]>([]);

  useEffect(() => {
    onEventRef.current =
      options.onEvent;
  }, [options.onEvent]);

  useEffect(() => {
    onOpenRef.current =
      options.onOpen;
  }, [options.onOpen]);

  useEffect(() => {
    onCloseRef.current =
      options.onClose;
  }, [options.onClose]);

  useEffect(() => {
    onErrorRef.current =
      options.onError;
  }, [options.onError]);

  const clearReconnectTimer =
    useCallback(() => {
      if (reconnectTimerRef.current) {
        clearTimeout(
          reconnectTimerRef.current,
        );

        reconnectTimerRef.current = null;
      }
    }, []);

  const disconnect =
    useCallback(() => {
      shouldReconnectRef.current = false;

      clearReconnectTimer();

      const socket =
        socketRef.current;

      socketRef.current = null;

      if (
        socket &&
        socket.readyState !== WebSocket.CLOSED
      ) {
        socket.close(
          1000,
          "Client disconnect",
        );
      }

      setStatus("closed");
    }, [clearReconnectTimer]);

  const send = useCallback(
    (
      data:
        | string
        | Record<string, unknown>,
    ) => {
      const socket =
        socketRef.current;

      if (
        !socket ||
        socket.readyState !== WebSocket.OPEN
      ) {
        return false;
      }

      const payload =
        typeof data === "string"
          ? data
          : JSON.stringify(data);

      socket.send(payload);

      return true;
    },
    [],
  );

  useEffect(() => {
    if (!enabled) {
      disconnect();
      setStatus("idle");

      return;
    }

    shouldReconnectRef.current = true;

    let disposed = false;

    const connect = () => {
      if (
        disposed ||
        !shouldReconnectRef.current
      ) {
        return;
      }

      clearReconnectTimer();

      setStatus("connecting");

      const socket =
        new WebSocket(url);

      socketRef.current = socket;

      socket.onopen = () => {
        reconnectAttemptRef.current = 0;

        setStatus("open");

        onOpenRef.current?.();
      };

      socket.onmessage = (
        messageEvent,
      ) => {
        try {
          const parsed = JSON.parse(
            String(messageEvent.data),
          ) as WebSocketEvent;

          setLatestEvent(parsed);

          setEvents((current) => {
            const next = [
              ...current,
              parsed,
            ];

            if (
              next.length >
              maxStoredEvents
            ) {
              return next.slice(
                next.length -
                  maxStoredEvents,
              );
            }

            return next;
          });

          onEventRef.current?.(
            parsed,
          );
        } catch {
          // Ignore malformed messages.
          // The backend WebSocket contract should only send JSON events.
        }
      };

      socket.onerror = (
        event,
      ) => {
        setStatus("error");

        onErrorRef.current?.(
          event,
        );
      };

      socket.onclose = () => {
        socketRef.current = null;

        if (disposed) {
          return;
        }

        setStatus("closed");

        onCloseRef.current?.();

        if (
          !reconnect ||
          !shouldReconnectRef.current
        ) {
          return;
        }

        const attempt =
          reconnectAttemptRef.current++;

        const delay = Math.min(
          1000 * 2 ** attempt,
          maxReconnectDelayMs,
        );

        reconnectTimerRef.current =
          setTimeout(
            connect,
            delay,
          );
      };
    };

    connect();

    return () => {
      disposed = true;

      shouldReconnectRef.current =
        false;

      clearReconnectTimer();

      const socket =
        socketRef.current;

      socketRef.current = null;

      if (
        socket &&
        socket.readyState !==
          WebSocket.CLOSED
      ) {
        socket.close(
          1000,
          "Component unmounted",
        );
      }
    };
  }, [
    clearReconnectTimer,
    disconnect,
    enabled,
    maxReconnectDelayMs,
    maxStoredEvents,
    reconnect,
    url,
  ]);

  const clearEvents =
    useCallback(() => {
      setEvents([]);
      setLatestEvent(null);
    }, []);

  return {
    url,

    status,

    isConnected:
      status === "open",

    latestEvent,

    events,

    send,

    disconnect,

    clearEvents,
  };
}
