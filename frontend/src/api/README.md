# `src/api`

HTTP client layer for the Compute Exchange frontend.

## Environment

Create a `.env` file at the frontend root:

```env
VITE_API_BASE_URL=http://localhost:8000
```

## Required package

```bash
npm install axios
```

## Domain types

These files import domain contracts from `src/types/`:

- `resource.ts`
- `user.ts`
- `offer.ts`
- `negotiation.ts`
- `simulation.ts`
- `agent.ts`

## Agent routes

`agents.api.ts` is intentionally isolated because these FastAPI routes must exist before those functions can be called:

- `GET /agents/{user_id}/candidates`
- `POST /agents/{user_id}/pursue`
- `POST /agents/{user_id}/handle-offer`
- `GET /coalitions/{user_id}`
- `POST /negotiations/{id}/mediate`

All other API modules correspond to routes already defined in the current backend / SimulationWorld API design.
