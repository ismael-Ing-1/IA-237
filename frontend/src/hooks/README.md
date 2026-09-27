# `src/hooks`

React hooks for the Compute Exchange frontend.

## Included hooks

### `useUsers.ts`
- `useUsers()`
- `usePublicUser(userId)`
- `useUserDashboard(userId)`
- `useCreateUser()`

### `useSimulation.ts`
- `useSimulation()`
- `useScheduledEvents()`
- `useEventHistory()`

### `useMarket.ts`
- `useProviders(resourceType, options)`
- `useRequesters(resourceType, options)`
- `useMarket(resourceType, options)`

### `useNegotiation.ts`
- `useNegotiations()`
- `useCreateNegotiation()`
- `useNegotiation(negotiationId)`

### `useAgent.ts`
- `useAgent(userId)`
- `useAgentCandidates(userId, resourceType)`
- `useCoalitions(userId, options)`
- `useMediator(negotiationId)`

### `useWebSocket.ts`
Low-level auto-reconnecting WebSocket hook with:
- connection status
- latest event
- bounded event history
- `send()`
- `disconnect()`
- `clearEvents()`

## Packages required

```bash
npm install @tanstack/react-query
```

`useWebSocket` uses the browser's native WebSocket API and needs no extra
WebSocket package.

## Environment

REST:

```env
VITE_API_BASE_URL=http://localhost:8000
```

WebSocket:

```env
VITE_WS_URL=ws://localhost:8000/ws
```

If `VITE_WS_URL` is omitted, the hook derives `/ws` from
`VITE_API_BASE_URL`.

## Important backend note

The functions in `useAgent.ts` depend on the planned FastAPI agent routes:

- `GET /agents/{user_id}/candidates`
- `POST /agents/{user_id}/pursue`
- `POST /agents/{user_id}/handle-offer`
- `GET /coalitions/{user_id}`
- `POST /negotiations/{id}/mediate`

Until these routes are exposed, the rest of the frontend hooks continue to
work, but these agent mutations/queries will return HTTP 404 if called.

## WebSocket note

`useWebSocket.ts` assumes the future backend WebSocket endpoint is `/ws`
unless `VITE_WS_URL` specifies another URL.

The next frontend layer should add `src/websocket/eventHandlers.ts` to map
incoming WebSocket events to TanStack Query invalidations and activity-feed
entries.
