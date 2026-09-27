# `src/store`

Local frontend state for the Compute Exchange React application.

The store layer uses **Zustand**.

## Install

```bash
npm install zustand
```

## Important architecture rule

This folder stores only **client/UI state**.

It must NOT become a second copy of backend state.

Do **not** put these in Zustand:

- users
- resources
- negotiations
- market state
- simulation state
- scheduled backend events

Those remain in **TanStack Query**, because FastAPI / `SimulationWorld`
is the source of truth.

## Files

### `ui.store.ts`

Stores local UI selections and presentation state:

- selected user
- selected negotiation
- selected coalition
- approval modal visibility
- panel visibility
- sidebar state
- graph layout
- graph auto-fit

Example:

```tsx
const selectedUserId =
  useUIStore(
    (state) =>
      state.selectedUserId,
  );

const selectUser =
  useUIStore(
    (state) =>
      state.selectUser,
  );
```

### `activity.store.ts`

Stores the ephemeral live activity feed produced by WebSocket events.

It contains:

- `activities`
- `addActivity()`
- `addActivities()`
- `addFromWebSocketEvent()`
- `clearActivities()`
- `clearUserActivities()`

This is UI state rather than domain state, because the activity feed is a
presentation of backend events, not the authoritative marketplace state.

Example:

```tsx
const activities =
  useActivityStore(
    (state) =>
      state.activities,
  );
```

Later, `src/websocket/eventHandlers.ts` can call:

```ts
useActivityStore
  .getState()
  .addFromWebSocketEvent(event);
```

while simultaneously invalidating the relevant TanStack Query caches.

## Data flow

```text
FastAPI / SimulationWorld
          |
          | HTTP
          v
    TanStack Query
    authoritative state


FastAPI WebSocket
          |
          v
    eventHandlers
       /      \
      v        v
Query cache   Zustand
invalidate    activity/UI
```

This avoids duplicating server state in multiple frontend stores.
