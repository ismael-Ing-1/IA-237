# Compute Exchange Network

> **Privacy-aware multi-agent marketplace for compute resources**

Compute Exchange Network is a hackathon-oriented multi-agent marketplace in which autonomous agents negotiate exchanges of compute resources such as GPU time, CPU capacity and storage.

Each user owns a **PersonalAgent** that represents their interests, protects private constraints, searches the market, negotiates with other agents, may request mediation, may participate in multi-party coalitions, and always keeps the human in the approval loop before execution.

The system combines:

- deterministic business rules for safety and correctness;
- LLM-based strategic decision-making;
- bilateral negotiation with counter-offers;
- mediator-assisted negotiation;
- multi-agent coalition discovery and atomic execution;
- privacy-aware local policy enforcement;
- reputation-aware partner selection;
- human approval checkpoints;
- real-time WebSocket activity;
- virtual-time simulation;
- an interactive React dashboard.

---

## 1. Core idea

A user should not need to manually inspect every provider, negotiate every price/resource trade, or reason about multi-party exchanges.

Instead:

```text
User defines objective
        ↓
PersonalAgent searches market
        ↓
LLM chooses among locally safe actions
        ↓
bilateral negotiation
        ↓
mediator if useful
        ↓
different provider if needed
        ↓
coalition if bilateral paths fail
        ↓
human approval
        ↓
atomic execution
```

The key architectural rule is:

> **The LLM decides WHAT to do. Python decides what is allowed and HOW it is executed.**

The LLM never directly changes inventories, bypasses privacy rules, approves a transaction, or executes a settlement.

---

# 2. Example

Alice owns storage and needs H100 GPU hours.

```text
Alice
offers: STORAGE
wants: H100
```

Bob owns H100 but wants A100:

```text
Bob
offers: H100
wants: A100
```

Charlie owns A100 but wants storage:

```text
Charlie
offers: A100
wants: STORAGE
```

A bilateral Alice ↔ Bob exchange may fail because Bob does not want Alice's storage.

The system can then discover:

```text
Alice   ── STORAGE ──▶ Charlie
Charlie ── A100 ─────▶ Bob
Bob     ── H100 ─────▶ Alice
```

Every PersonalAgent checks the coalition against its own private policy. Then every human approves. Only after all approvals does the atomic settlement execute.

---

# 3. Architecture

```text
                         React Frontend
                               │
                               │ REST commands + snapshots
                               │ WebSocket realtime events
                               ▼
                            FastAPI
                               │
                               ▼
                       AgentOrchestrator
                               │
       ┌───────────────────────┼────────────────────────┐
       │                       │                        │
       ▼                       ▼                        ▼
 PersonalAgent          MediatorAgent            CoalitionAgent
       │                       │                        │
       │                       │                        │
       ├─────────────── LLM Policy Layer ──────────────┤
       │                       │                        │
       ▼                       ▼                        ▼
 PrivacyGuard           Public compromise       Graph / cycle search
 Reputation             suggestions              ranking
 Constraints                                     feasibility
       │                                                │
       └───────────────────────┬────────────────────────┘
                               ▼
                         SimulationWorld
                               │
                               ▼
                     Human approval checkpoints
                               │
                               ▼
                        Settlement engines
                     bilateral / atomic coalition
```

---

# 4. Project structure

The project is organized around the following backend architecture:

```text
compute-exchange/
├── app/
│   ├── agents/
│   │   ├── personal_agent.py
│   │   ├── mediator_agent.py
│   │   ├── coalition_agent.py
│   │   └── orchestrator.py
│   │
│   ├── llm/
│   │   ├── __init__.py
│   │   ├── config.py
│   │   ├── context.py
│   │   ├── factory.py
│   │   ├── openai_provider.py
│   │   ├── policy.py
│   │   ├── prompts.py
│   │   ├── provider.py
│   │   └── schemas.py
│   │
│   ├── tools/
│   │   ├── market_tools.py
│   │   ├── negotiation_tools.py
│   │   ├── privacy_tools.py
│   │   ├── coalition_tools.py
│   │   ├── coalition_execution.py
│   │   └── need_tools.py
│   │
│   ├── models/
│   │   ├── user.py
│   │   ├── resource.py
│   │   ├── offer.py
│   │   └── negotiation.py
│   │
│   ├── market/
│   │   ├── registry.py
│   │   └── exchange.py
│   │
│   ├── privacy/
│   │   └── guard.py
│   │
│   ├── reputation/
│   │   └── reputation.py
│   │
│   ├── simulation/
│   │   ├── world.py
│   │   ├── events.py
│   │   └── scenario_loader.py
│   │
│   └── api/
│       ├── main.py
│       └── websocket.py
│
├── frontend/
│   └── src/
│       ├── api/
│       ├── features/
│       ├── hooks/
│       ├── pages/
│       ├── store/
│       ├── types/
│       └── websocket/
│
├── scenarios/
├── tests/
├── docs/
└── README.md
```

---

# 5. PersonalAgent

Every marketplace participant is represented by a `PersonalAgent`.

A PersonalAgent is responsible for:

- discovering eligible providers;
- selecting a partner;
- creating safe initial offers;
- evaluating incoming offers;
- accepting, rejecting or countering;
- asking for mediation;
- trying another provider;
- participating in coalition validation;
- requesting human approval;
- protecting all private constraints.

## Negotiation strategies

Users can choose one of four strategies:

| Strategy | General behavior |
|---|---|
| `fast` | favors rapid safe agreements |
| `balanced` | balances preferences, reputation and deal quality |
| `conservative` | preserves capacity and favors higher-confidence partners |
| `aggressive` | pushes harder for improved public terms |

The strategy is visible to the LLM policy, while private constraints remain local.

---

# 6. Full LLM negotiation

When `LLM_MODE=active`, the LLM participates in the complete strategic negotiation flow.

It can decide:

1. which eligible provider to approach;
2. which safe initial offer to send;
3. whether to accept an incoming offer;
4. whether to reject;
5. whether to request a mediator;
6. which safe counter-offer to send;
7. which alternative provider to try;
8. which mediator proposal to prefer;
9. which already-feasible coalition to try first.

## Safe action generation

The LLM does **not** generate arbitrary transactions.

Python first builds a menu of locally valid choices.

Example:

```text
counter_cautious
  GIVE 11.5 STORAGE
  REQUEST 8.8 H100

counter_firm
  GIVE 13.4 STORAGE
  REQUEST 8.56 H100

counter_balanced
  GIVE 15 STORAGE
  REQUEST 8.24 H100

counter_bridge
  GIVE 16 STORAGE
  REQUEST 8 H100

accept
reject
ask_mediator
```

The LLM chooses one `choice_id`.

Python then revalidates the selected option before mutating live state.

This provides agentic negotiation without giving the model unrestricted control.

---

# 7. LLM modes

Three runtime modes are available.

## `disabled`

```bash
export LLM_MODE=disabled
```

No LLM API call is performed.

The deterministic PersonalAgent policy controls the marketplace.

## `shadow`

```bash
export LLM_MODE=shadow
```

The LLM receives safe public context and makes decisions, but its decisions are only observed.

The deterministic policy remains authoritative.

Typical realtime events:

```text
LLM THINKING
LLM SHADOW DECISION
```

This is the recommended mode when validating a new model.

## `active`

```bash
export LLM_MODE=active
```

The LLM selects the effective action among Python-generated safe choices.

Typical events:

```text
LLM THINKING
LLM DECISION
LLM POLICY VALIDATED
```

If the model call fails or returns an invalid choice:

```text
LLM FALLBACK
```

and the deterministic policy continues automatically.

---

# 8. Privacy model

The MVP implements **application-level privacy**, not cryptographic privacy.

Private data remains inside the PersonalAgent/server-side policy layer.

Examples of private information that should not be sent to the LLM or other agents:

- exact private inventory when not publicly revealed;
- `max_quantity_to_give`;
- blocked partner lists;
- preferred partner lists;
- private budgets;
- additional private constraints.

Instead, the LLM receives safe derived information such as:

```text
Allowed choices:
- counter_cautious
- counter_balanced
- reject
- ask_mediator
```

The `PrivacyGuard` remains authoritative.

The LLM cannot override it.

---

# 9. Bilateral negotiation

A typical bilateral flow is:

```text
AliceAgent searches providers
        ↓
provider selected
        ↓
Alice sends initial offer
        ↓
BobAgent evaluates
        ↓
accept / reject / counter / mediator
        ↓
AliceAgent evaluates response
        ↓
...
        ↓
agreement found
        ↓
WAITING_HUMAN
        ↓
approve or reject
```

Counter-offers are linked to previous offers and the negotiation is bounded by `max_negotiation_rounds`.

## Human rejection

Human rejection closes that exact deal permanently.

The represented agent then continues the original objective:

```text
human_rejected
      ↓
counterparty notified
      ↓
search another eligible provider
      ↓
new bilateral negotiation
      ↓
coalition fallback if necessary
```

A rejected deal is never reopened.

---

# 10. MediatorAgent

The mediator is a public-information-only agent.

It may intervene after repeated counter-offers or when the round limit approaches.

It sees:

```text
Alice → Bob
10 STORAGE for 8 H100

Bob → Alice
8 H100 for 16 STORAGE
```

It does **not** see:

```text
Alice private STORAGE limit = 20
Bob private H100 limit = 10
```

The mediator may suggest a compromise.

In active LLM mode the model can generate a public compromise, but Python verifies that the quantities remain inside the latest publicly revealed bargaining interval.

Then both PersonalAgents independently validate the suggestion using their own private policies.

The mediator cannot approve or execute anything.

---

# 11. Coalition workflow

Coalition discovery is graph-based.

`CoalitionAgent` searches exchange cycles such as:

```text
Alice → Charlie → Bob → Alice
```

The LLM does not replace this algorithm.

The workflow is:

```text
bilateral alternatives exhausted
        ↓
CoalitionAgent discovers feasible cycles
        ↓
LLM may rank the already-feasible candidates
        ↓
each PersonalAgent privately validates
        ↓
WAITING_HUMANS
        ↓
every participant approves
        ↓
APPROVED
        ↓
explicit Execute
        ↓
atomic settlement
```

## Atomic execution

A coalition is all-or-nothing.

Before execution the backend rechecks:

- users are still available;
- resources are still available;
- private limits are still valid;
- all human approvals exist.

The resource state is snapshotted before settlement.

If any transfer fails, the whole operation is rolled back.

There is no valid state where only part of the coalition remains executed.

---

# 12. Needs synchronization

`User.needs` represents the **remaining active demand**.

If Alice changes:

```text
H100 8
```

to:

```text
H100 5
```

in the objective composer, the selected user's current need is synchronized rather than duplicated.

After actual settlement:

```text
need = 8 H100
receive 3 H100
remaining need = 5 H100
```

If the need is fully fulfilled, it is removed from active needs and the frontend displays:

```text
0 remaining · all current needs satisfied
```

Human approval alone does not satisfy a need.

The need changes only after real successful execution.

---

# 13. Reputation

The reputation layer tracks transaction history and delivery behavior.

The score combines transaction success and delivery quality.

Reputation influences:

- candidate eligibility;
- candidate ranking;
- coalition feasibility/ranking;
- PersonalAgent trust policy.

Private minimum reputation thresholds remain local to each user.

---

# 14. SimulationWorld

`SimulationWorld` is the in-memory source of truth.

It contains:

- users;
- marketplace registry;
- active negotiations;
- completed negotiations;
- scheduled events;
- event history;
- virtual time.

Virtual time does not move automatically.

The frontend can advance it manually:

```text
+1 min
+5 min
+10 min
+1 hour
```

Scheduled events can change:

- resources;
- needs;
- user online/offline state.

---

# 15. Real-time system

REST is the authoritative state source.

WebSocket is the real-time observation channel.

```text
React
  │
  ├── REST commands / snapshots
  │
  ▼
FastAPI
  │
  ├── SimulationWorld
  └── AgentOrchestrator
           │
           ▼
       WebSocket
           │
           ▼
Agent Activity / graph / approval UI
```

Important event families include:

```text
agent_started
agent_action
agent_notified
agent_stopped

provider_found

negotiation_started
negotiation_updated
offer_sent
counter_offer_sent
offer_accepted
offer_rejected

mediation_started
mediation_suggestion

coalition_search_started
coalition_found
coalition_agent_evaluated
coalition_selected
coalition_human_approval_required
coalition_human_approved
coalition_human_rejected
coalition_approved
coalition_exchange_started
coalition_exchange_completed
coalition_exchange_failed

human_approval_required
human_approved
human_rejected

exchange_started
exchange_completed
exchange_failed

llm_thinking
llm_decision
llm_shadow_decision
llm_policy_validated
llm_fallback

market_event_scheduled
market_event_executed
simulation_time_updated
market_updated
```

The UI intentionally paces event presentation so the demo remains readable.

---

# 16. Frontend

The frontend is a React/Vite control room for the market.

Main areas:

```text
┌──────────────┬────────────────────────────┬─────────────────┐
│ Personal     │ Market graph               │ Agent Activity  │
│ Agent        │                            │                 │
│              │ agents / negotiations /    │ realtime events │
│ resources    │ coalition edges            │                 │
│ needs        │                            │                 │
│ strategy     │                            │                 │
└──────────────┴────────────────────────────┴─────────────────┘

┌───────────────────────────────────────────┬─────────────────┐
│ Negotiation / Coalition                   │ Simulation      │
│ timeline / approvals / execution          │ clock / events  │
└───────────────────────────────────────────┴─────────────────┘
```

Frontend stack:

- React
- TypeScript
- Vite
- Tailwind CSS
- TanStack Query
- Zustand
- Axios
- React Router
- React Flow
- native browser WebSocket

TanStack Query stores authoritative HTTP state.

Zustand stores presentation/UI state only.

---

# 17. Scenarios

## `bilateral`

Simple direct exchange.

Purpose:

- provider search;
- bilateral offer;
- agent agreement;
- human approval;
- execution.

## `negociation`

Negotiation-focused scenario.

Purpose:

- multiple rounds;
- different agent strategies;
- mediator;
- human rejection;
- alternative-provider search.

## `coalition`

Three-agent circular exchange.

Purpose:

- bilateral failure;
- coalition discovery;
- private validation;
- multiple human approvals;
- atomic settlement.

## `showcase`

Broader dynamic market demonstration with virtual-time events.

---

# 18. Open-ended LLM scenarios

These scenarios intentionally have:

```text
no seed_negotiation
no expected_result
no expected_coalition
```

They define the market and then let the agents choose the path.

## `llm_playground`

Several genuinely compatible H100 providers.

Tests:

- provider selection;
- initial-offer generation;
- full multi-round LLM negotiation;
- acceptance/rejection;
- mediation if useful.

This is the clearest scenario for demonstrating autonomous LLM bargaining.

## `llm_market_choice`

Tests strategic provider selection.

Some providers have excellent reputation but poor public compatibility with Alice's offered resource.

Another provider may have weaker reputation but better economic compatibility.

The LLM must balance public compatibility, reputation and strategy.

## `llm_open_coalition`

A difficult market with several bilateral and multi-party possibilities.

The system may naturally follow:

```text
bilateral
→ mediator
→ alternate provider
→ coalition
```

No coalition is prescribed in the scenario file.

---

# 19. Negotiation states

Important negotiation states include:

```text
negotiating
agreement_found
waiting_human
approved
rejected
cancelled
failed
```

One current implementation detail is worth noting:

`FAILED` may be used when a particular bilateral attempt closes without agreement before the objective continues to another provider/coalition, and it may also represent an internal processing failure.

Therefore:

```text
negotiation FAILED
```

does not necessarily mean:

```text
entire user objective failed
```

The agent runtime separately tracks objective-level states such as:

```text
searching
negotiating
waiting_human
searching_coalition
coalition_proposed
exhausted
cancelled
completed
failed
```

---

# 20. Installation

## Backend

Create/activate a Python virtual environment and install the project dependencies.

For the LLM layer:

```bash
python -m pip install -r requirements-llm.txt
```

Start FastAPI from the project root:

```bash
python -m uvicorn app.api.main:app \
  --reload \
  --host 127.0.0.1 \
  --port 8000
```

Backend:

```text
http://127.0.0.1:8000
```

API docs:

```text
http://127.0.0.1:8000/docs
```

---

## Frontend

Requirements:

- Node.js 20.19+ recommended

Run:

```bash
cd frontend
npm install
npm run dev
```

Frontend:

```text
http://localhost:5173
```

Useful checks:

```bash
npm run typecheck
npm run build
```

---

# 21. LLM configuration

Never expose the API key to Vite or the browser.

Configure it only in the backend environment:

```bash
export OPENAI_API_KEY='...'
export LLM_MODE=active
export OPENAI_MODEL='<model-id>'
export OPENAI_TIMEOUT_SECONDS=6
export OPENAI_MAX_RETRIES=0
export LLM_MAX_CANDIDATES=6
```

Check the integration:

```text
GET /llm/status
```

Example:

```json
{
  "mode": "active",
  "model": "<model-id>",
  "available": true,
  "provider": "openai",
  "unavailable_reason": null
}
```

The API key is never returned.

---

# 22. Important API routes

## Health / LLM

```text
GET /health
GET /llm/status
WS  /ws
```

## Users

```text
POST  /users
GET   /users
GET   /users/{user_id}
GET   /users/{user_id}/dashboard
PATCH /users/{user_id}/strategy
```

## Market

```text
GET /market/providers/{resource_type}
GET /market/requesters/{resource_type}
```

## Agents

```text
POST /agents/{user_id}/pursue
GET  /agents/{user_id}/candidates
GET  /agents/{user_id}/state
POST /agents/{user_id}/stop
POST /agents/{user_id}/handle-offer
```

## Negotiations

```text
POST /negotiations
GET  /negotiations
GET  /negotiations/{id}

POST /negotiations/{id}/offers
POST /negotiations/{id}/counter-offers
POST /negotiations/{id}/offers/{offer_id}/accept
POST /negotiations/{id}/offers/{offer_id}/reject

POST /negotiations/{id}/resume
POST /negotiations/{id}/mediate

POST /negotiations/{id}/request-approval
POST /negotiations/{id}/approve
POST /negotiations/{id}/reject
POST /negotiations/{id}/cancel
POST /negotiations/{id}/execute
```

## Coalitions

```text
GET  /coalitions/{user_id}

GET  /coalition-deals
GET  /coalition-deals/{coalition_id}

POST /coalition-deals/{coalition_id}/approve
POST /coalition-deals/{coalition_id}/reject
POST /coalition-deals/{coalition_id}/execute
```

## Simulation

```text
GET  /simulation/state
GET  /simulation/events
GET  /simulation/history

POST /simulation/events
POST /simulation/advance
POST /simulation/run-until
```

## Development scenarios

```text
GET    /dev/scenarios
POST   /dev/scenarios/{name}/load
POST   /dev/scenarios/{name}/run
DELETE /dev/reset
```

---

# 23. Quick demo

## Full LLM negotiation

Backend:

```bash
export LLM_MODE=active
export OPENAI_API_KEY='...'
python -m uvicorn app.api.main:app --reload --port 8000
```

Then:

```text
POST /dev/scenarios/llm_playground/run
```

Watch Agent Activity.

A possible run:

```text
LLM THINKING
↓
LLM DECISION — choose Emma

LLM THINKING
↓
LLM DECISION — initial_balanced

Alice → Emma
offer

LLM THINKING
↓
LLM DECISION — counter_firm

Emma → Alice
counter

LLM THINKING
↓
LLM DECISION — counter_bridge

Alice → Emma
counter

LLM THINKING
↓
LLM DECISION — accept

Human approval required
↓
Approve
↓
Execute
↓
Resources + needs update
```

The exact path is intentionally not predetermined.

---

# 24. Testing checklist

## Bilateral

Verify:

- provider found;
- negotiation starts;
- several counter-offers can occur;
- rounds remain bounded;
- safe agreement reaches human approval;
- execution changes inventories;
- needs update after settlement.

## Human rejection

Verify:

- rejected deal remains closed;
- counterparty receives notification;
- objective owner searches again;
- a new provider may be selected;
- old negotiation is never reopened.

## Mediator

Verify:

- no premature intervention;
- only public offer terms are used;
- mediator proposal is privately checked by both agents;
- failed mediation continues to alternatives.

## Coalition

Verify:

- graph cycle is discovered;
- every PersonalAgent validates;
- every human approves independently;
- Execute appears only when approved;
- settlement is atomic;
- rollback restores all inventories on failure.

## LLM

Run first in `shadow`, then `active`.

Verify:

- `LLM THINKING`;
- `LLM SHADOW DECISION`;
- `LLM DECISION`;
- `LLM POLICY VALIDATED`;
- `LLM FALLBACK`;
- invalid/unavailable model never breaks the market.

## Realtime

Verify:

- WebSocket reconnects;
- REST resynchronizes authoritative state;
- no old approval checkpoint is permanently lost;
- graph and activity remain coherent.

---

# 25. Design principles

## Human agency

Agents negotiate and coordinate, but humans approve before real settlement.

## Safety before intelligence

The LLM cannot override deterministic rules.

## Privacy by architecture

Private constraints stay local to PersonalAgents.

## REST is authoritative

WebSocket activity improves responsiveness and observability but is not the database.

## Atomic multi-party settlement

Coalitions either execute completely or not at all.

## Graceful AI fallback

The marketplace still works when the LLM is unavailable.

---

# 26. Current limitations

This project is a hackathon MVP.

Current limitations include:

- in-memory state;
- one-process local simulation;
- no production authentication/authorization;
- no database transaction layer;
- privacy is application-level rather than MPC/ZKP/FHE;
- no cryptographically private agent-to-agent protocol;
- coalition search is designed for small demo graphs;
- LLM output quality depends on model/API availability;
- production-grade observability, persistence and distributed execution remain future work.

---

# 27. Future directions

Potential extensions:

- persistent PostgreSQL state;
- authenticated users / organizations;
- reservations and resource locking;
- real cloud/GPU provider integrations;
- SLA-aware negotiation;
- deadline-sensitive strategies;
- cost/currency pricing;
- richer reputation signals;
- larger coalition optimization;
- cryptographic private negotiation;
- audit logs;
- model evaluation and negotiation benchmarks;
- multi-model agent personalities;
- production deployment.

---

# 28. Summary

Compute Exchange Network demonstrates a hybrid approach to agentic systems:

```text
LLM
→ strategy and negotiation

Python
→ safety, privacy and validation

Graph algorithms
→ coalition discovery

Humans
→ final authorization

Atomic engines
→ execution
```

The result is a marketplace where autonomous agents can negotiate dynamically while the important guarantees remain outside the model.
