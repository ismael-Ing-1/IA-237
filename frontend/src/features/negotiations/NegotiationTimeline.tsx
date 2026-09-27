import type {
  NegotiationStatus,
} from "../../types/negotiation";

import type {
  Offer,
} from "../../types/offer";

import {
  OfferCard,
} from "./OfferCard";


interface NegotiationTimelineProps {
  offers: Offer[];

  acceptedOfferId?: string | null;

  negotiationStatus?: NegotiationStatus;

  resolveUserName?: (
    userId: string,
  ) => string;
}


export function NegotiationTimeline({
  offers,
  acceptedOfferId,
  negotiationStatus,
  resolveUserName,
}: NegotiationTimelineProps) {
  if (offers.length === 0) {
    return (
      <div className="rounded-xl border border-dashed border-slate-800 p-8 text-center text-sm text-slate-500">
        No offers yet.
      </div>
    );
  }

  return (
    <div className="relative space-y-3">
      <div className="absolute bottom-0 left-3 top-0 w-px bg-slate-800" />

      {offers.map(
        (offer, index) => {
          const wasAccepted =
            acceptedOfferId === offer.id;

          let statusLabel:
            string | undefined;
          let statusTone:
            "neutral" | "danger" | "success" =
              "neutral";

          if (
            wasAccepted &&
            negotiationStatus === "rejected"
          ) {
            statusLabel =
              "human rejected";
            statusTone = "danger";
          } else if (
            wasAccepted &&
            negotiationStatus === "cancelled"
          ) {
            statusLabel =
              "deal cancelled";
            statusTone = "danger";
          } else if (
            wasAccepted &&
            negotiationStatus === "failed"
          ) {
            statusLabel = "deal failed";
            statusTone = "danger";
          } else if (
            wasAccepted &&
            [
              "agreement_found",
              "waiting_human",
              "approved",
            ].includes(
              negotiationStatus ?? "",
            )
          ) {
            statusTone = "success";
          }

          return (
            <div
              key={offer.id}
              className="relative pl-8"
            >
              <div className="absolute left-[7px] top-5 h-3 w-3 rounded-full border-2 border-slate-950 bg-cyan-400" />

              <p className="mb-1 text-[10px] font-semibold uppercase tracking-wider text-slate-600">
                Round {index + 1}
              </p>

              <OfferCard
                offer={offer}
                resolveUserName={
                  resolveUserName
                }
                selected={wasAccepted}
                statusLabel={statusLabel}
                statusTone={statusTone}
              />
            </div>
          );
        },
      )}
    </div>
  );
}
