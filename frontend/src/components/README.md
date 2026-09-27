# `src/components`

Shared reusable React components for the Compute Exchange frontend.

This folder contains **generic UI and layout primitives** only.

Business-specific components remain in:

```text
src/features/
```

## Structure

```text
components/
├── ui/
│   ├── Button.tsx
│   ├── Card.tsx
│   ├── Badge.tsx
│   ├── Modal.tsx
│   ├── EmptyState.tsx
│   ├── LoadingSpinner.tsx
│   ├── ErrorState.tsx
│   ├── SectionHeader.tsx
│   ├── StatCard.tsx
│   ├── Divider.tsx
│   ├── Panel.tsx
│   └── index.ts
│
├── layout/
│   ├── AppShell.tsx
│   ├── PageContainer.tsx
│   ├── SplitPane.tsx
│   ├── ThreeColumnLayout.tsx
│   ├── StickyHeader.tsx
│   ├── SidebarSection.tsx
│   └── index.ts
│
├── index.ts
└── README.md
```

## Dependencies

No additional component library is required.

These components use:

- React
- Tailwind CSS

This is intentional: the project does not require shadcn/ui yet.

## Separation rule

Use `components/` for generic reusable pieces:

- buttons
- cards
- modal shells
- loaders
- layout helpers

Use `features/` for domain components:

- MarketGraph
- AgentPanel
- GoalComposer
- NegotiationPanel
- ApprovalModal
- SimulationControls

## Example

```tsx
import {
  Button,
  Panel,
  ThreeColumnLayout,
} from "../components";
```
