import {
  useEffect,
  useMemo,
  useState,
} from "react";

import type {
  Resource,
  ResourceRequest,
} from "../../types/resource";

import type {
  UserDashboard,
} from "../../types/user";


export interface GoalComposerValue {
  request: ResourceRequest;

  offered_resources: Resource[];

  message?: string | null;
}


interface GoalComposerProps {
  onSubmit: (
    value: GoalComposerValue,
  ) => Promise<unknown> | void;

  dashboard?: UserDashboard | null;

  onRequestDraftChange?: (
    request: ResourceRequest | null,
  ) => void;

  isSubmitting?: boolean;
}


function newId() {
  if (
    typeof crypto !== "undefined" &&
    "randomUUID" in crypto
  ) {
    return crypto.randomUUID();
  }

  return `${Date.now()}-${Math.random()}`;
}


function toLocalDateTimeInput(
  value: string | null | undefined,
): string {
  if (!value) return "";

  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";

  const local = new Date(
    date.getTime() -
      date.getTimezoneOffset() * 60_000,
  );

  return local
    .toISOString()
    .slice(0, 16);
}


export function GoalComposer({
  onSubmit,
  dashboard,
  onRequestDraftChange,
  isSubmitting = false,
}: GoalComposerProps) {
  const [resourceType, setResourceType] =
    useState("");

  const [quantity, setQuantity] =
    useState(1);

  const [unit, setUnit] =
    useState("");

  const [
    offeredResourceType,
    setOfferedResourceType,
  ] = useState("");

  const [
    offeredQuantity,
    setOfferedQuantity,
  ] = useState(1);

  const [offeredUnit, setOfferedUnit] =
    useState("");

  const [deadline, setDeadline] =
    useState("");

  const [message, setMessage] =
    useState(
      "Find a safe deal while preserving my private constraints.",
    );

  const seedNeed = dashboard?.needs[0];
  const seedResource = dashboard?.resources[0];

  const seedKey = [
    dashboard?.id ?? "",
    seedNeed?.id ?? "",
    seedNeed?.resource_type ?? "",
    seedNeed?.quantity ?? "",
    seedNeed?.unit ?? "",
    seedResource?.id ?? "",
    seedResource?.quantity ?? "",
  ].join("|");

  /*
   * The previous form kept Alice's H100/STORAGE values after selecting Bob.
   * That made Bob try to offer STORAGE he did not own, which correctly caused
   * the backend to reject Start agent. Re-seed the form when the selected
   * owner changes.
   */
  useEffect(() => {
    if (!dashboard) {
      setResourceType("");
      setQuantity(1);
      setUnit("");
      setOfferedResourceType("");
      setOfferedQuantity(1);
      setOfferedUnit("");
      setDeadline("");
      return;
    }

    const need = dashboard.needs[0];
    const resource = dashboard.resources[0];

    setResourceType(
      need?.resource_type ?? "",
    );
    setQuantity(
      need?.quantity ?? 1,
    );
    setUnit(
      need?.unit ?? "",
    );
    setDeadline(
      toLocalDateTimeInput(
        need?.deadline,
      ),
    );

    setOfferedResourceType(
      resource?.resource_type ?? "",
    );
    setOfferedUnit(
      resource?.unit ?? "",
    );

    // The frontend deliberately does not know max_quantity_to_give.
    // Start with a small inventory-safe quantity; the agents can negotiate
    // upward/downward while the backend enforces the private limit.
    setOfferedQuantity(
      resource
        ? Math.max(
            0.001,
            Math.min(
              resource.quantity,
              1,
            ),
          )
        : 1,
    );

    setMessage(
      "Find a safe deal while preserving my private constraints.",
    );
  }, [seedKey]);

  // Reflect what the user is currently asking for in the Personal Agent
  // "Needs" panel immediately, before the objective is submitted.
  useEffect(() => {
    if (
      !dashboard ||
      resourceType.trim().length === 0 ||
      unit.trim().length === 0 ||
      quantity <= 0
    ) {
      onRequestDraftChange?.(null);
      return;
    }

    onRequestDraftChange?.({
      id: seedNeed?.id ?? newId(),
      resource_type: resourceType.trim(),
      quantity,
      unit: unit.trim(),
      deadline:
        deadline.length > 0
          ? new Date(deadline).toISOString()
          : null,
      attributes: {
        ...(seedNeed?.attributes ?? {}),
      },
    });
  }, [
    dashboard?.id,
    deadline,
    onRequestDraftChange,
    quantity,
    resourceType,
    seedNeed?.id,
    unit,
  ]);

  const canSubmit = useMemo(
    () =>
      Boolean(dashboard) &&
      resourceType.trim().length > 0 &&
      quantity > 0 &&
      unit.trim().length > 0 &&
      offeredResourceType.trim()
        .length > 0 &&
      offeredQuantity > 0 &&
      offeredUnit.trim().length > 0,
    [
      dashboard,
      offeredQuantity,
      offeredResourceType,
      offeredUnit,
      quantity,
      resourceType,
      unit,
    ],
  );

  async function handleSubmit(
    event: React.FormEvent,
  ) {
    event.preventDefault();

    if (!canSubmit) {
      return;
    }

    const request: ResourceRequest =
      {
        id:
          seedNeed?.id ??
          newId(),

        resource_type:
          resourceType.trim(),

        quantity,

        unit: unit.trim(),

        deadline:
          deadline.length > 0
            ? new Date(
                deadline,
              ).toISOString()
            : null,

        attributes: {
          ...(seedNeed?.attributes ?? {}),
        },
      };

    const offeredResource: Resource =
      {
        id: newId(),

        resource_type:
          offeredResourceType.trim(),

        quantity: offeredQuantity,

        unit: offeredUnit.trim(),

        available_from: null,

        available_until: null,

        attributes: {},
      };

    await onSubmit({
      request,

      offered_resources: [
        offeredResource,
      ],

      message:
        message.trim().length > 0
          ? message.trim()
          : null,
    });
  }

  return (
    <form
      onSubmit={handleSubmit}
      className="rounded-2xl border border-slate-800 bg-slate-950/80 p-4"
    >
      <div>
        <p className="text-xs uppercase tracking-wider text-slate-500">
          New objective
        </p>

        <h3 className="mt-1 font-semibold text-slate-100">
          Ask your agent to negotiate
        </h3>

        <p className="mt-1 text-[11px] leading-4 text-slate-600">
          Prefilled from the selected agent&apos;s current need and inventory.
        </p>
      </div>

      <div className="mt-4 grid grid-cols-3 gap-2">
        <Field
          label="Need"
          value={resourceType}
          onChange={setResourceType}
        />

        <NumberField
          label="Quantity"
          value={quantity}
          onChange={setQuantity}
        />

        <Field
          label="Unit"
          value={unit}
          onChange={setUnit}
        />
      </div>

      <div className="mt-4">
        <p className="mb-2 text-xs font-semibold uppercase tracking-wider text-slate-500">
          Can offer
        </p>

        <div className="grid grid-cols-3 gap-2">
          <Field
            label="Resource"
            value={
              offeredResourceType
            }
            onChange={
              setOfferedResourceType
            }
          />

          <NumberField
            label="Quantity"
            value={offeredQuantity}
            onChange={
              setOfferedQuantity
            }
          />

          <Field
            label="Unit"
            value={offeredUnit}
            onChange={
              setOfferedUnit
            }
          />
        </div>
      </div>

      <label className="mt-4 block">
        <span className="mb-1 block text-xs text-slate-500">
          Deadline
        </span>

        <input
          type="datetime-local"
          value={deadline}
          onChange={(event) =>
            setDeadline(
              event.target.value,
            )
          }
          className="w-full rounded-xl border border-slate-800 bg-slate-900 px-3 py-2 text-sm text-slate-200 outline-none transition focus:border-cyan-500"
        />
      </label>

      <label className="mt-4 block">
        <span className="mb-1 block text-xs text-slate-500">
          Objective / instructions
        </span>

        <textarea
          value={message}
          onChange={(event) =>
            setMessage(
              event.target.value,
            )
          }
          rows={3}
          className="w-full resize-none rounded-xl border border-slate-800 bg-slate-900 px-3 py-2 text-sm text-slate-200 outline-none transition focus:border-cyan-500"
        />
      </label>

      <button
        type="submit"
        disabled={
          !canSubmit ||
          isSubmitting
        }
        className="mt-4 w-full rounded-xl bg-cyan-500 px-4 py-2.5 text-sm font-semibold text-slate-950 transition hover:bg-cyan-400 disabled:cursor-not-allowed disabled:opacity-50"
      >
        {isSubmitting
          ? "Agent working..."
          : "Start agent"}
      </button>
    </form>
  );
}


function Field({
  label,
  value,
  onChange,
}: {
  label: string;
  value: string;
  onChange: (
    value: string,
  ) => void;
}) {
  return (
    <label>
      <span className="mb-1 block text-xs text-slate-500">
        {label}
      </span>

      <input
        value={value}
        onChange={(event) =>
          onChange(
            event.target.value,
          )
        }
        className="w-full rounded-xl border border-slate-800 bg-slate-900 px-3 py-2 text-sm text-slate-200 outline-none transition focus:border-cyan-500"
      />
    </label>
  );
}


function NumberField({
  label,
  value,
  onChange,
}: {
  label: string;
  value: number;
  onChange: (
    value: number,
  ) => void;
}) {
  return (
    <label>
      <span className="mb-1 block text-xs text-slate-500">
        {label}
      </span>

      <input
        type="number"
        min="0.001"
        step="any"
        value={value}
        onChange={(event) =>
          onChange(
            Number(
              event.target.value,
            ),
          )
        }
        className="w-full rounded-xl border border-slate-800 bg-slate-900 px-3 py-2 text-sm text-slate-200 outline-none transition focus:border-cyan-500"
      />
    </label>
  );
}
