# `src/pages`

Top-level route pages for the Compute Exchange frontend.

## Files

```text
src/pages/
├── DashboardPage.tsx
├── index.ts
└── README.md
```

`DashboardPage.tsx` is the main hackathon interface. It connects the REST
SimulationWorld snapshot, the PersonalAgent hooks, React Flow market graph,
live activity store, negotiation workflow, human approval modal and
simulation controls.

The existing `src/app/router.tsx` already imports:

```tsx
import DashboardPage from "../pages/DashboardPage";
```

so replacing the placeholder file with this generated version activates
the complete dashboard.

The page requires `GET /simulation/state` for its initial state. If that
endpoint is unavailable, a visible error panel is shown instead of a blank
page.

Agent actions from `GoalComposer` require the planned agent-facing backend
route used by `useAgent()`:

```text
POST /agents/{user_id}/pursue
```

If that route is not available yet, the dashboard itself still loads.
