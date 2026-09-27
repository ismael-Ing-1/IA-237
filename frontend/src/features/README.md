# `src/features`

Feature-level React components for the Compute Exchange frontend.

## Structure

```text
features/
├── dashboard/
├── market/
├── agents/
├── negotiations/
├── approvals/
└── simulation/
```

## Dependencies

These components expect:

```bash
npm install @xyflow/react @tanstack/react-query
```

Tailwind CSS should also be configured in the project.

No shadcn/ui components are required by this folder yet. This is deliberate:
the feature layer can compile before the shared `components/ui/` design system
is added.

## Backend assumptions

The components are based on the current frontend contracts:

- `src/types/`
- `src/hooks/`
- `src/api/`

Agent-triggering UI (`GoalComposer`) requires the agent FastAPI endpoints used
by `agents.api.ts`.

`SimulationControls` uses the SimulationWorld endpoints.

## Recommended dashboard composition

```tsx
<DashboardLayout
  header={<DashboardHeader />}
  left={
    <>
      <AgentPanel />
      <GoalComposer />
    </>
  }
  center={<MarketGraph />}
  right={<AgentActivityFeed />}
  bottom={
    <>
      <NegotiationPanel />
      <SimulationControls />
    </>
  }
/>
```

## WebSocket

This folder is WebSocket-ready, but the real-time event orchestration belongs
in `src/websocket/`. Incoming events should be converted into:

- TanStack Query cache invalidations
- `AgentActivity[]` entries for `AgentActivityFeed`
- selection/modal state for the dashboard
