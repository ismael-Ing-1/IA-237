import type {
  Offer,
} from "../../types/offer";

import {
  ResourceBadge,
} from "../market/ResourceBadge";


interface OfferCardProps {
  offer: Offer;

  resolveUserName?: (
    userId: string,
  ) => string;

  selected?: boolean;

  statusLabel?: string;

  statusTone?: "neutral" | "danger" | "success";
}


export function OfferCard({
  offer,
  resolveUserName = (id) => id,
  selected = false,
  statusLabel,
  statusTone = "neutral",
}: OfferCardProps) {
  const statusClass =
    statusTone === "danger"
      ? "border-rose-500/40 bg-rose-500/5 text-rose-300"
      : statusTone === "success"
        ? "border-emerald-500/40 bg-emerald-500/5 text-emerald-300"
        : "border-slate-700 text-slate-400";

  return (
    <article
      className={[
        "rounded-xl border p-4",
        selected
          ? "border-cyan-500/40 bg-cyan-500/5"
          : "border-slate-800 bg-slate-950/60",
      ].join(" ")}
    >
      <div className="flex items-center justify-between gap-3">
        <div>
          <p className="text-sm font-medium text-slate-200">
            {resolveUserName(
              offer.sender_id,
            )}
            <span className="mx-2 text-slate-600">
              →
            </span>
            {resolveUserName(
              offer.receiver_id,
            )}
          </p>

          <p className="mt-1 text-xs text-slate-600">
            {new Date(
              offer.created_at,
            ).toLocaleString()}
          </p>
        </div>

        <span className={`rounded-full border px-2 py-1 text-[10px] uppercase tracking-wider ${statusClass}`}>
          {statusLabel ?? offer.status}
        </span>
      </div>

      <div className="mt-4 grid gap-4 md:grid-cols-2">
        <div>
          <p className="mb-2 text-[10px] font-semibold uppercase tracking-wider text-slate-500">
            Gives
          </p>

          <div className="flex flex-wrap gap-2">
            {offer.offered_resources.map(
              (resource) => (
                <ResourceBadge
                  key={resource.id}
                  resourceType={
                    resource.resource_type
                  }
                  quantity={
                    resource.quantity
                  }
                  unit={resource.unit}
                  variant="offer"
                />
              ),
            )}
          </div>
        </div>

        <div>
          <p className="mb-2 text-[10px] font-semibold uppercase tracking-wider text-slate-500">
            Wants
          </p>

          <div className="flex flex-wrap gap-2">
            {offer.requested_resources.map(
              (resource) => (
                <ResourceBadge
                  key={resource.id}
                  resourceType={
                    resource.resource_type
                  }
                  quantity={
                    resource.quantity
                  }
                  unit={resource.unit}
                  variant="need"
                />
              ),
            )}
          </div>
        </div>
      </div>

      {offer.message && (
        <p className="mt-4 rounded-lg bg-slate-900/70 p-3 text-xs leading-5 text-slate-400">
          {offer.message}
        </p>
      )}
    </article>
  );
}
