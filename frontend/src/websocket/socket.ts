import { parseWebSocketEvent } from "./events";
import type { WebSocketEvent } from "../types/websocket";

export type SocketStatus = "idle" | "connecting" | "open" | "closed" | "error";
export interface SocketOptions {
  url?: string;
  reconnect?: boolean;
  initialReconnectDelayMs?: number;
  maxReconnectDelayMs?: number;
}
export type SocketEventListener = (event: WebSocketEvent) => void;
export type SocketStatusListener = (status: SocketStatus) => void;

function defaultUrl(): string {
  const explicit = import.meta.env.VITE_WS_URL?.trim();
  if (explicit) return explicit;
  const base = import.meta.env.VITE_API_BASE_URL?.trim() || "http://localhost:8000";
  try {
    const url = new URL(base, typeof window === "undefined" ? "http://localhost:8000" : window.location.origin);
    url.protocol = url.protocol === "https:" ? "wss:" : "ws:";
    url.pathname = `${url.pathname.replace(/\/+$/, "")}/ws`;
    url.search = "";
    url.hash = "";
    return url.toString();
  } catch {
    // Ne jamais faire échouer l'import de l'application à cause d'une configuration réseau.
    // connect() présentera l'erreur via le statut de connexion.
    return base;
  }
}

export class ComputeExchangeSocket {
  private socket: WebSocket | null = null;
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private reconnectAttempt = 0;
  private manuallyClosed = false;
  private status: SocketStatus = "idle";
  private generation = 0;
  private readonly eventListeners = new Set<SocketEventListener>();
  private readonly statusListeners = new Set<SocketStatusListener>();
  readonly url: string;
  readonly reconnect: boolean;
  readonly initialReconnectDelayMs: number;
  readonly maxReconnectDelayMs: number;

  constructor(options: SocketOptions = {}) {
    this.url = options.url ?? defaultUrl();
    this.reconnect = options.reconnect ?? true;
    this.initialReconnectDelayMs = options.initialReconnectDelayMs ?? 1000;
    this.maxReconnectDelayMs = options.maxReconnectDelayMs ?? 10000;
  }

  connect(): void {
    if (this.socket && (this.socket.readyState === WebSocket.CONNECTING || this.socket.readyState === WebSocket.OPEN)) return;
    this.manuallyClosed = false;
    this.clearReconnectTimer();
    const generation = ++this.generation;
    this.setStatus("connecting");
    let socket: WebSocket;
    try {
      socket = new WebSocket(this.url);
    } catch (error) {
      this.setStatus("error");
      console.error("Invalid WebSocket configuration; REST remains available.", error);
      return;
    }
    this.socket = socket;
    const current = () => generation === this.generation && this.socket === socket;
    socket.onopen = () => {
      if (!current()) return;
      this.reconnectAttempt = 0;
      this.setStatus("open");
    };
    socket.onmessage = (message) => {
      if (!current() || typeof message.data !== "string") return;
      const event = parseWebSocketEvent(message.data);
      if (event === null) return;
      for (const listener of this.eventListeners) {
        try { listener(event); } catch (error) { console.error("Realtime listener failed.", error); }
      }
    };
    socket.onerror = () => { if (current()) this.setStatus("error"); };
    socket.onclose = () => {
      // Un ancien socket fermé par StrictMode ne peut plus écraser le socket courant.
      if (!current()) return;
      this.socket = null;
      this.setStatus("closed");
      if (!this.manuallyClosed && this.reconnect) this.scheduleReconnect();
    };
  }

  disconnect(): void {
    this.manuallyClosed = true;
    this.generation += 1;
    this.clearReconnectTimer();
    const socket = this.socket;
    this.socket = null;
    if (socket) {
      socket.onopen = null;
      socket.onmessage = null;
      socket.onerror = null;
      socket.onclose = null;
      if (socket.readyState !== WebSocket.CLOSED) socket.close(1000, "Client disconnect");
    }
    this.setStatus("closed");
  }

  send(value: string | Record<string, unknown>): boolean {
    if (!this.socket || this.socket.readyState !== WebSocket.OPEN) return false;
    try {
      this.socket.send(typeof value === "string" ? value : JSON.stringify(value));
      return true;
    } catch { return false; }
  }

  subscribe(listener: SocketEventListener): () => void {
    this.eventListeners.add(listener);
    return () => { this.eventListeners.delete(listener); };
  }

  subscribeStatus(listener: SocketStatusListener): () => void {
    this.statusListeners.add(listener);
    listener(this.status);
    return () => { this.statusListeners.delete(listener); };
  }

  getStatus(): SocketStatus { return this.status; }
  isOpen(): boolean { return this.status === "open"; }

  private scheduleReconnect(): void {
    this.clearReconnectTimer();
    const delay = Math.min(this.initialReconnectDelayMs * 2 ** Math.min(this.reconnectAttempt++, 8), this.maxReconnectDelayMs);
    this.reconnectTimer = setTimeout(() => {
      this.reconnectTimer = null;
      if (!this.manuallyClosed) this.connect();
    }, delay);
  }

  private clearReconnectTimer(): void {
    if (this.reconnectTimer !== null) clearTimeout(this.reconnectTimer);
    this.reconnectTimer = null;
  }

  private setStatus(status: SocketStatus): void {
    this.status = status;
    for (const listener of this.statusListeners) {
      try { listener(status); } catch (error) { console.error("Realtime status listener failed.", error); }
    }
  }
}

export const realtimeSocket = new ComputeExchangeSocket();
if (import.meta.hot) import.meta.hot.dispose(() => realtimeSocket.disconnect());
