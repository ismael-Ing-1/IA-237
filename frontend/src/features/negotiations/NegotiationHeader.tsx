import type {
  Negotiation,
} from "../../types/negotiation";

import {
  NegotiationStatusBadge,
} from "./NegotiationStatusBadge";


interface NegotiationHeaderProps {
  negotiation: Negotiation;

  resolveUserName?: (
    userId: string,
  ) => string;
}


export function NegotiationHeader({
  negotiation,
  resolveUserName = (id) => id,
}: NegotiationHeaderProps) {
  return (
    <header className="flex flex-wrap items-start justify-between gap-4">
      <div>
        <div className="flex items-center gap-2">
          <h2 className="text-lg font-semibold text-slate-100">
            Negotiation
          </h2>

          <NegotiationStatusBadge
            status={negotiation.status}
          />
        </div>

        <p className="mt-1 text-xs text-slate-500">
          {negotiation.participant_ids
            .map(resolveUserName)
            .join(" ↔ ")}
        </p>
      </div>

      <div className="text-right">
        <p className="text-xs text-slate-500">
          Round
        </p>

        <p className="text-sm font-medium text-slate-300">
          {negotiation.current_round}
          {" / "}
          {negotiation.max_rounds}
        </p>
      </div>
    </header>
  );
}
