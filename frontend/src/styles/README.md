# `src/styles`

Global CSS for the Compute Exchange frontend.

## Structure

```text
src/styles/
├── globals.css
├── tokens.css
├── animations.css
├── react-flow.css
└── README.md
```

## `globals.css`

Main stylesheet imported once from `src/main.tsx`.

It includes:

- Tailwind layers
- base document styles
- reusable `cx-*` component utilities
- scrollbar styling
- inputs
- focus states
- grid/radial backgrounds
- accessibility settings

Import it with:

```tsx
import "./styles/globals.css";
```

or, from `src/main.tsx`:

```tsx
import "./styles/globals.css";
```

## `tokens.css`

CSS variables for the global dark "control room" visual language:

- background
- panels
- text
- borders
- cyan / emerald / amber / rose / violet accents
- radius
- shadows
- animation durations

## `animations.css`

Reusable classes:

```text
.cx-animate-pulse-soft
.cx-animate-ring
.cx-animate-slide-up
.cx-animate-fade-in
.cx-skeleton
.cx-edge-flow
```

These can be used later by the live agent activity and graph.

## `react-flow.css`

Central overrides for `@xyflow/react`.

You should still import React Flow's own stylesheet in `main.tsx`:

```tsx
import "@xyflow/react/dist/style.css";
```

Then import `globals.css` afterwards so these overrides win:

```tsx
import "@xyflow/react/dist/style.css";
import "./styles/globals.css";
```

## Tailwind requirement

The project must already have Tailwind CSS configured.

This stylesheet currently uses the classic directives:

```css
@tailwind base;
@tailwind components;
@tailwind utilities;
```

If your frontend uses Tailwind v4 instead, replace those three directives with
the v4 import used by your setup, typically:

```css
@import "tailwindcss";
```

while keeping the local CSS imports and the rest of this file.

## Example page background

For the main dashboard:

```tsx
<div className="min-h-screen bg-slate-950 cx-grid-bg cx-radial-glow">
  ...
</div>
```
