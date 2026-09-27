# `src/types`

TypeScript domain contracts for the Compute Exchange frontend.

They mirror the current Python/Pydantic backend models and structured
agent outputs.

## Files

- `common.ts` — shared ISO datetime and metadata types
- `resource.ts` — `Resource`, `ResourceRequest`
- `user.ts` — public/private user contracts and dashboard payload
- `offer.ts` — offer model/status
- `negotiation.ts` — negotiation model/status
- `agent.ts` — personal agent, coalition and mediator outputs
- `simulation.ts` — market events, event execution and simulation snapshot
- `websocket.ts` — planned real-time WebSocket event contracts
- `index.ts` — barrel exports

## Privacy note

`User` and `UserConstraints` contain private backend information.
The marketplace UI should normally use `PublicUserProfile`, while the
selected user's owner dashboard uses `UserDashboard`.

## CoalitionProposal

The provided `CoalitionAgent` guarantees `proposal.participant_ids`, but the
full `CoalitionProposal` definition from `coalition_tools.py` was not present
in the supplied source set. The TypeScript interface therefore keeps
`participant_ids` strongly typed and permits additional fields until that
backend model is supplied.

Once `coalition_tools.py` is available, this interface can be made exact.
