# Compute Exchange Frontend

React frontend for **Compute Exchange Network**, a privacy-aware multi-agent marketplace where autonomous agents negotiate access to compute resources such as GPU time, CPU capacity and storage.

The frontend is designed as a live control room for the agentic market:

- users and resources are visualized as a network;
- active negotiations appear in real time;
- agent decisions are streamed through WebSocket events;
- bilateral exchanges and coalitions can be inspected visually;
- private constraints remain server-side;
- humans retain final approval before an exchange is executed;
- the virtual simulation clock can be advanced directly from the dashboard.

---

## Stack

- React
- TypeScript
- Vite
- Tailwind CSS
- TanStack Query
- Zustand
- Axios
- React Router
- React Flow (`@xyflow/react`)
- Native browser WebSocket API

The application uses **REST for commands and authoritative snapshots** and **WebSockets for live events**.

```text
React
  |
  | REST commands / queries
  v
FastAPI
  |
  v
SimulationWorld
  |
  | realtime events
  v
WebSocket
  |
  v
React activity feed + query invalidation
```

---

## Requirements

Use Node.js **20.19+**.

The backend is expected to run on:

```text
http://localhost:8000
```

and the frontend development server on:

```text
http://localhost:5173
```

---

## Installation

From the frontend project root:

```bash
npm install
```

Then start the development server:

```bash
npm run dev
```

Open:

```text
http://localhost:5173
```

---

## Environment

The included `.env` contains:

```env
VITE_API_BASE_URL=http://localhost:8000
VITE_WS_URL=ws://localhost:8000/ws
```

Change these values if the FastAPI backend is running elsewhere.

Only variables prefixed with `VITE_` are exposed to browser code by Vite.

---

## Available commands

### Development

```bash
npm run dev
```

### Type checking

```bash
npm run typecheck
```

### Production build

```bash
npm run build
```

The production bundle is written to:

```text
dist/
```

### Preview the production build

```bash
npm run preview
```

---

## Expected project structure

```text
frontend/
├── .env
├── package.json
├── tsconfig.json
├── vite.config.ts
├── README.md
├── index.html
│
└── src/
    ├── main.tsx
    │
    ├── app/
    │   ├── App.tsx
    │   ├── providers.tsx
    │   └── router.tsx
    │
    ├── api/
    │
    ├── components/
    │   ├── layout/
    │   └── ui/
    │
    ├── features/
    │   ├── agents/
    │   ├── approvals/
    │   ├── dashboard/
    │   ├── market/
    │   ├── negotiations/
    │   └── simulation/
    │
    ├── hooks/
    │
    ├── lib/
    │
    ├── store/
    │
    ├── styles/
    │
    ├── types/
    │
    └── websocket/
```

`index.html` can be kept from the standard Vite React template.

---

## Frontend architecture

### `src/api`

REST client layer.

It contains the Axios client and endpoints for:

- users;
- market discovery;
- negotiations;
- simulation;
- agents;
- development utilities.

Do not call `fetch()` or Axios directly from feature components.

---

### `src/types`

TypeScript contracts matching the Python/Pydantic backend models.

Important distinction:

```text
PublicUserProfile
```

is safe for marketplace display, while the full:

```text
User
UserConstraints
```

contains private information and should not be rendered for arbitrary users.

---

### `src/hooks`

TanStack Query hooks and frontend orchestration.

Examples:

```text
useSimulation
useMarket
useNegotiation
useAgent
useUsers
useWebSocket
```

TanStack Query stores the authoritative HTTP representation of server state.

---

### `src/store`

Zustand stores only local UI state.

It intentionally does **not** duplicate server state.

It currently stores things such as:

- selected user;
- selected negotiation;
- selected coalition;
- approval modal visibility;
- graph preferences;
- live activity feed.

---

### `src/features`

Business-specific UI components.

Important features include:

```text
MarketGraph
AgentPanel
GoalComposer
AgentActivityFeed
NegotiationPanel
ApprovalModal
SimulationControls
```

---

### `src/components`

Generic reusable UI and layout primitives.

Examples:

```text
Button
Card
Badge
Modal
Panel
ThreeColumnLayout
AppShell
```

No compute-market business logic belongs here.

---

### `src/websocket`

Realtime infrastructure.

The shared WebSocket layer:

1. receives events from FastAPI;
2. validates/parses the event envelope;
3. adds entries to the agent activity feed;
4. updates UI state when necessary;
5. invalidates TanStack Query caches;
6. lets REST refresh the authoritative state.

This prevents WebSocket state from becoming a second database in the browser.

---

## Expected WebSocket endpoint

The frontend expects:

```text
ws://localhost:8000/ws
```

with events shaped approximately like:

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

The connection automatically retries if the backend WebSocket is unavailable.

If `/ws` has not yet been implemented, the REST-based application can still load, but the live connection will remain disconnected/reconnecting.

---

## Agent API routes

The frontend agent layer expects routes similar to:

```text
GET  /agents/{user_id}/candidates
POST /agents/{user_id}/pursue
POST /agents/{user_id}/handle-offer

GET  /coalitions/{user_id}

POST /negotiations/{negotiation_id}/mediate
```

The rest of the frontend can operate before these endpoints are available, but agent-specific UI actions will fail if the corresponding FastAPI routes have not yet been added.

---

## Simulation API

The dashboard is built around `SimulationWorld`.

The most important endpoint is:

```text
GET /simulation/state
```

which should return a snapshot containing:

```text
current_time
users
active_negotiations
completed_negotiations
scheduled_events
event_history
```

The simulation controls also use endpoints such as:

```text
POST /simulation/advance
POST /simulation/run-until
POST /simulation/events
```

---

## Styling

The application uses the styles in:

```text
src/styles/
```

`src/main.tsx` should import React Flow first, then the project styles:

```tsx
import "@xyflow/react/dist/style.css";
import "./styles/globals.css";
```

The current CSS is written for **Tailwind CSS 3.4**, and `vite.config.ts` configures Tailwind/PostCSS inline, so no separate `tailwind.config.js` or `postcss.config.js` is required.

---

## Backend development mode

For local development, the FastAPI backend should allow the frontend origin.

The existing hackathon backend configuration allowing CORS from all origins is sufficient for local use.

For production, restrict CORS to the deployed frontend URL.

---

## Recommended startup order

Terminal 1 — backend:

```bash
uvicorn app.api.main:app --reload --port 8000
```

Terminal 2 — frontend:

```bash
npm run dev
```

Then open:

```text
http://localhost:5173
```

---

## First integration milestone

Before implementing the complete demo flow, verify these steps in order:

1. the frontend loads;
2. `GET /simulation/state` succeeds;
3. users appear in the market graph;
4. active negotiations appear as graph edges;
5. simulation controls can advance virtual time;
6. WebSocket shows `Live`;
7. an agent event appears in the activity feed;
8. `human_approval_required` opens the approval modal;
9. approving and executing an exchange refreshes user resources.

Once these work, the visual hackathon demo is connected end-to-end.
