# `src/websocket`

Realtime WebSocket layer for the Compute Exchange frontend.

## Structure

```text
src/websocket/
├── events.ts
├── socket.ts
├── eventHandlers.ts
├── realtime.ts
├── WebSocketBootstrap.tsx
├── useRealtimeStatus.ts
├── index.ts
└── README.md
```

## Architecture

The WebSocket layer is deliberately kept separate from REST.

```text
FastAPI WebSocket
        |
        v
   socket.ts
        |
        v
 eventHandlers.ts
    /        \
   v          v
Zustand    TanStack Query
activity   invalidation
   |          |
   v          v
React UI   REST refresh
```

The WebSocket does NOT become a second source of truth.

The authoritative state remains:

```text
FastAPI / SimulationWorld
```

The socket announces what changed, then TanStack Query refreshes
the relevant HTTP state.

## `events.ts`

Contains:

- known WebSocket event names
- runtime validation
- JSON parsing
- cache refresh classification helpers

## `socket.ts`

Contains `ComputeExchangeSocket`.

Features:

- shared WebSocket connection
- automatic reconnect
- exponential backoff
- event subscriptions
- connection status subscriptions
- JSON sending
- default URL detection

Default URL:

```text
ws://localhost:8000/ws
```

Environment override:

```env
VITE_WS_URL=ws://localhost:8000/ws
```

## `eventHandlers.ts`

Maps realtime events to application behavior.

Examples:

```text
offer_sent
    -> add activity item
    -> refresh negotiations

exchange_completed
    -> refresh negotiations
    -> refresh users
    -> refresh market
    -> refresh simulation

human_approval_required
    -> open approval modal
    -> select negotiation
```

## `realtime.ts`

Connects `realtimeSocket` with a TanStack `QueryClient`.

## `WebSocketBootstrap.tsx`

Mount once near the root of React.

Recommended integration in `src/app/providers.tsx`:

```tsx
import {
  WebSocketBootstrap,
} from "../websocket";

export function AppProviders({
  children,
}: PropsWithChildren) {
  return (
    <QueryClientProvider client={queryClient}>
      <ReactFlowProvider>
        <WebSocketBootstrap />
        {children}
      </ReactFlowProvider>
    </QueryClientProvider>
  );
}
```

The backend `/ws` endpoint must exist before the connection can succeed.
Until then, the socket will reconnect automatically.

## `useRealtimeStatus.ts`

Useful for the dashboard header:

```tsx
const connected =
  useRealtimeConnected();

<DashboardHeader
  connected={connected}
/>
```

## Expected event envelope

The backend should emit:

```json
{
  "event_id": "evt-123",
  "type": "agent_action",
  "timestamp": "2026-09-26T15:00:00Z",
  "user_id": "alice",
  "entity_id": "negotiation-42",
  "payload": {
    "decision": {
      "action": "search_market",
      "reason": "Looking for H100 providers."
    }
  }
}
```

The accepted event names are defined in `src/types/websocket.ts`
and mirrored by `events.ts`.
