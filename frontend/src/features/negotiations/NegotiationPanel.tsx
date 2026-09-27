import type {
  Negotiation,
} from "../../types/negotiation";

import {
  NegotiationHeader,
} from "./NegotiationHeader";

import {
  NegotiationTimeline,
} from "./NegotiationTimeline";


interface NegotiationPanelProps {
  negotiation?: Negotiation | null;

  resolveUserName?: (
    userId: string,
  ) => string;

  onRequestApproval?: () => void;

  onApprove?: () => void;

  onReject?: () => void;

  onExecute?: () => void;

  busy?: boolean;
}


export function NegotiationPanel({
  negotiation,
  resolveUserName,
  onRequestApproval,
  onApprove,
  onReject,
  onExecute,
  busy = false,
}: NegotiationPanelProps) {
  if (!negotiation) {
    return (
      <section className="rounded-2xl border border-slate-800 bg-slate-950/80 p-6">
        <p className="text-sm font-medium text-slate-300">
          No active negotiation
        </p>

        <p className="mt-1 text-sm text-slate-600">
          Start an agent objective or
          select an existing negotiation.
        </p>
      </section>
    );
  }

  const canRequestApproval =
    negotiation.status ===
    "agreement_found";

  const waitingHuman =
    negotiation.status ===
    "waiting_human";

  const approved =
    negotiation.status ===
    "approved";

  return (
    <section className="rounded-2xl border border-slate-800 bg-slate-950/80 p-5">
      <NegotiationHeader
        negotiation={negotiation}
        resolveUserName={
          resolveUserName
        }
      />

      <div className="mt-5 max-h-[420px] overflow-y-auto pr-1">
        <NegotiationTimeline
          offers={negotiation.offers}
          acceptedOfferId={
            negotiation.accepted_offer_id
          }
          negotiationStatus={
            negotiation.status
          }
          resolveUserName={
            resolveUserName
          }
        />
      </div>

      {negotiation.status === "rejected" && (
        <div className="mt-4 rounded-xl border border-rose-500/30 bg-rose-500/5 p-3 text-xs leading-5 text-rose-200">
          The agents had reached these terms, but the human reviewer rejected the final deal.
          No exchange was executed and the objective may continue with another alternative.
        </div>
      )}

      {(canRequestApproval ||
        waitingHuman ||
        approved) && (
        <div className="mt-5 flex flex-wrap justify-end gap-2 border-t border-slate-800 pt-4">
          {canRequestApproval &&
            onRequestApproval && (
              <button
                type="button"
                disabled={busy}
                onClick={
                  onRequestApproval
                }
                className="rounded-xl bg-amber-400 px-4 py-2 text-sm font-semibold text-slate-950 disabled:opacity-50"
              >
                Request human approval
              </button>
            )}

          {waitingHuman &&
            onReject && (
              <button
                type="button"
                disabled={busy}
                onClick={onReject}
                className="rounded-xl border border-rose-500/40 px-4 py-2 text-sm font-semibold text-rose-300 disabled:opacity-50"
              >
                Reject & find another deal
              </button>
            )}

          {waitingHuman &&
            onApprove && (
              <button
                type="button"
                disabled={busy}
                onClick={onApprove}
                className="rounded-xl bg-emerald-400 px-4 py-2 text-sm font-semibold text-slate-950 disabled:opacity-50"
              >
                Approve
              </button>
            )}

          {approved &&
            onExecute && (
              <button
                type="button"
                disabled={busy}
                onClick={onExecute}
                className="rounded-xl bg-cyan-400 px-4 py-2 text-sm font-semibold text-slate-950 disabled:opacity-50"
              >
                Execute exchange
              </button>
            )}
        </div>
      )}
    </section>
  );
}
