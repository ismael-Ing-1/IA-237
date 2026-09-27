import type {
  Negotiation,
} from "../../types/negotiation";

import {
  DealSummary,
} from "./DealSummary";


interface ApprovalModalProps {
  open: boolean;

  negotiation?: Negotiation | null;

  resolveUserName?: (
    userId: string,
  ) => string;

  onApprove: () => void;

  onReject: () => void;

  onClose?: () => void;

  busy?: boolean;
}


export function ApprovalModal({
  open,
  negotiation,
  resolveUserName,
  onApprove,
  onReject,
  onClose,
  busy = false,
}: ApprovalModalProps) {
  if (
    !open ||
    !negotiation
  ) {
    return null;
  }

  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center overflow-y-auto bg-slate-950/85 p-4 backdrop-blur-sm">
      <div className="my-auto max-h-[calc(100vh-2rem)] w-full max-w-xl overflow-y-auto rounded-2xl border border-slate-700 bg-slate-900 p-5 shadow-2xl">
        <div className="flex items-start justify-between gap-4">
          <div>
            <p className="text-xs font-semibold uppercase tracking-wider text-amber-300">
              Human approval required
            </p>

            <h2 className="mt-1 text-xl font-semibold text-slate-100">
              Deal ready
            </h2>

            <p className="mt-1 text-sm text-slate-500">
              Review the final public
              terms before execution.
            </p>
          </div>

          {onClose && (
            <button
              type="button"
              onClick={onClose}
              className="rounded-lg border border-slate-700 px-2.5 py-1.5 text-xs text-slate-400"
            >
              Close
            </button>
          )}
        </div>

        <div className="mt-5">
          <DealSummary
            negotiation={negotiation}
            resolveUserName={
              resolveUserName
            }
          />
        </div>

        <div className="mt-5 flex justify-end gap-2">
          <button
            type="button"
            disabled={busy}
            onClick={onReject}
            className="rounded-xl border border-rose-500/40 px-4 py-2 text-sm font-semibold text-rose-300 disabled:opacity-50"
          >
            Reject
          </button>

          <button
            type="button"
            disabled={busy}
            onClick={onApprove}
            className="rounded-xl bg-emerald-400 px-4 py-2 text-sm font-semibold text-slate-950 disabled:opacity-50"
          >
            Approve deal
          </button>
        </div>
      </div>
    </div>
  );
}
