# `src/lib`

Shared utility functions, formatters and frontend constants for the
Compute Exchange React application.

## Structure

```text
src/lib/
├── utils.ts
├── formatters.ts
├── constants.ts
├── index.ts
└── README.md
```

## `utils.ts`

Generic helpers with no React or external-library dependency:

- `cn()`
- `clamp()`
- `normalizeScore()`
- `createLocalId()`
- `assertNever()`
- `compactObject()`
- `lastItem()`
- `sortedCopy()`
- `capitalize()`
- `humanize()`
- `isNonEmptyString()`

Example:

```ts
import {
  cn,
} from "../lib";

const className = cn(
  "rounded-xl",
  active &&
    "border-cyan-400",
);
```

## `formatters.ts`

UI-friendly formatting helpers:

- resource quantities
- dates
- times
- durations
- reputation scores
- entity IDs
- negotiation statuses
- offer statuses
- agent actions
- simulation events
- relative time

Example:

```ts
formatResource(resource);
// H100 · 8 gpu-hour

formatScore(0.92);
// 92%
```

## `constants.ts`

Shared application constants:

- application name
- network defaults
- cache timing
- graph defaults
- compute resource presets
- status labels
- agent action labels
- simulation event labels
- simulation time presets

## Architecture

`lib/` must remain generic.

It should not:

- make HTTP requests
- access Zustand stores
- run React hooks
- modify TanStack Query caches
- contain agent business logic

Those responsibilities belong respectively to:

```text
api/
store/
hooks/
websocket/
features/
```
