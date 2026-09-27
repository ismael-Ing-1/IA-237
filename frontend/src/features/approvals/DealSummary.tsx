import type {
  Negotiation,
} from "../../types/negotiation";

import {
  TransferRow,
} from "./TransferRow";


interface DealSummaryProps {
  negotiation: Negotiation;

  resolveUserName?: (
    userId: string,
  ) => string;
}


export function DealSummary({
  negotiation,
  resolveUserName = (id) => id,
}: DealSummaryProps) {
  const acceptedOffer =
    negotiation.offers.find(
      (offer) =>
        offer.id ===
        negotiation.accepted_offer_id,
    );

  if (!acceptedOffer) {
    return (
      <div className="rounded-xl border border-amber-500/30 bg-amber-500/5 p-4 text-sm text-amber-200">
        No accepted offer is available
        for this negotiation.
      </div>
    );
  }

  return (
    <div className="space-y-3">
      <TransferRow
        label="Offered"
        from={resolveUserName(
          acceptedOffer.sender_id,
        )}
        to={resolveUserName(
          acceptedOffer.receiver_id,
        )}
        resources={
          acceptedOffer.offered_resources
        }
      />

      <TransferRow
        label="Requested"
        from={resolveUserName(
          acceptedOffer.receiver_id,
        )}
        to={resolveUserName(
          acceptedOffer.sender_id,
        )}
        resources={
          acceptedOffer.requested_resources
        }
      />

      <div className="rounded-xl border border-emerald-500/20 bg-emerald-500/5 p-3">
        <p className="text-xs font-medium text-emerald-300">
          Private constraints remain
          server-side.
        </p>

        <p className="mt-1 text-xs leading-5 text-slate-500">
          The frontend only displays the
          negotiated public deal.
        </p>
      </div>
    </div>
  );
}
