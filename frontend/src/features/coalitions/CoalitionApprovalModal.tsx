import type {
  CoalitionDeal,
} from "../../types/agent";

interface CoalitionApprovalModalProps {
  open: boolean;
  deal: CoalitionDeal | null;
  selectedUserId: string | null;
  resolveUserName: (userId: string) => string;
  busy?: boolean;
  onApprove: () => void | Promise<void>;
  onReject: () => void | Promise<void>;
  onClose: () => void;
}

export function CoalitionApprovalModal({
  open,
  deal,
  selectedUserId,
  resolveUserName,
  busy = false,
  onApprove,
  onReject,
  onClose,
}: CoalitionApprovalModalProps) {
  if (
    !open ||
    !deal ||
    !selectedUserId ||
    !deal.proposal.participant_ids.includes(selectedUserId)
  ) {
    return null;
  }

  const evaluation =
    deal.agent_evaluations[selectedUserId];

  return (
    <div
      className="fixed inset-0 z-[110] flex items-center justify-center overflow-y-auto bg-slate-950/85 p-4 backdrop-blur-sm"
      role="dialog"
      aria-modal="true"
      aria-labelledby="coalition-approval-title"
    >
      <div className="my-auto max-h-[calc(100vh-2rem)] w-full max-w-2xl overflow-y-auto rounded-2xl border border-violet-400/30 bg-slate-900 p-5 shadow-2xl">
        <div className="flex items-start justify-between gap-4">
          <div>
            <p className="text-xs font-semibold uppercase tracking-wider text-violet-300">
              Human approval required
            </p>
            <h2
              id="coalition-approval-title"
              className="mt-1 text-xl font-semibold text-slate-100"
            >
              Review multi-agent coalition
            </h2>
            <p className="mt-2 text-sm leading-6 text-slate-400">
              {resolveUserName(selectedUserId)}'s PersonalAgent has already
              checked its private constraints. The coalition still requires
              an explicit human decision before any transfer can execute.
            </p>
          </div>

          <button
            type="button"
            onClick={onClose}
            disabled={busy}
            className="rounded-lg border border-slate-700 px-2.5 py-1.5 text-xs text-slate-400 hover:text-slate-200 disabled:opacity-50"
          >
            Close
          </button>
        </div>

        <div className="mt-5 rounded-xl border border-slate-800 bg-slate-950/70 p-4">
          <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">
            Coalition transfers
          </p>

          <div className="mt-3 space-y-2">
            {deal.proposal.transfers.map((transfer, index) => (
              <div
                key={`${transfer.from_user_id}-${transfer.to_user_id}-${transfer.resource_type}-${index}`}
                className="rounded-lg border border-slate-800 bg-slate-900/70 px-3 py-2 text-sm"
              >
                <span className="font-medium text-slate-200">
                  {resolveUserName(transfer.from_user_id)}
                </span>
                <span className="mx-2 text-violet-300">→</span>
                <span className="font-medium text-slate-200">
                  {resolveUserName(transfer.to_user_id)}
                </span>
                <span className="ml-2 text-slate-400">
                  {transfer.quantity} {transfer.resource_type} {transfer.unit}
                </span>
              </div>
            ))}
          </div>
        </div>

        <div className="mt-4 grid gap-3 sm:grid-cols-2">
          <div className="rounded-xl border border-slate-800 bg-slate-950/60 p-3">
            <p className="text-xs uppercase tracking-wider text-slate-500">
              Your agent
            </p>
            <p className="mt-2 text-sm font-medium text-slate-200">
              {evaluation?.accepted
                ? "✓ Private validation passed"
                : "Validation completed"}
            </p>
            <p className="mt-1 text-xs leading-5 text-slate-500">
              Private limits remain local to the PersonalAgent.
            </p>
          </div>

          <div className="rounded-xl border border-slate-800 bg-slate-950/60 p-3">
            <p className="text-xs uppercase tracking-wider text-slate-500">
              Execution
            </p>
            <p className="mt-2 text-sm font-medium text-slate-200">
              Atomic and still locked
            </p>
            <p className="mt-1 text-xs leading-5 text-slate-500">
              Approval alone does not transfer resources. Every human must
              approve before the separate execute action is enabled.
            </p>
          </div>
        </div>

        <div className="mt-5 flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
          <button
            type="button"
            disabled={busy}
            onClick={() => {
              void onReject();
            }}
            className="rounded-lg border border-rose-400/30 bg-rose-500/10 px-4 py-2.5 text-sm font-semibold text-rose-300 disabled:opacity-50"
          >
            Reject coalition
          </button>

          <button
            type="button"
            disabled={busy}
            onClick={() => {
              void onApprove();
            }}
            className="rounded-lg border border-emerald-400/30 bg-emerald-500/15 px-4 py-2.5 text-sm font-semibold text-emerald-300 disabled:opacity-50"
          >
            Approve coalition
          </button>
        </div>
      </div>
    </div>
  );
}
