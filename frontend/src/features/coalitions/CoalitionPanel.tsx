import type { CoalitionDeal } from "../../types/agent";

interface CoalitionPanelProps {
  deal: CoalitionDeal | null;
  selectedUserId: string | null;
  resolveUserName: (userId: string) => string;
  approvalRevealed: boolean;
  executionRevealed: boolean;
  busy?: boolean;
  onApprove?: () => void;
  onReject?: () => void;
  onExecute?: () => void;
}

const terminal = new Set(["rejected", "cancelled", "completed", "failed"]);

function statusClass(status: CoalitionDeal["status"]): string {
  if (status === "completed") return "border-emerald-500/30 bg-emerald-500/10 text-emerald-300";
  if (status === "rejected" || status === "failed" || status === "cancelled")
    return "border-rose-500/30 bg-rose-500/10 text-rose-300";
  if (status === "approved") return "border-cyan-500/30 bg-cyan-500/10 text-cyan-300";
  return "border-violet-500/30 bg-violet-500/10 text-violet-300";
}

export function CoalitionPanel({
  deal,
  selectedUserId,
  resolveUserName,
  approvalRevealed,
  executionRevealed,
  busy = false,
  onApprove,
  onReject,
  onExecute,
}: CoalitionPanelProps) {
  if (!deal) {
    return (
      <section className="rounded-2xl border border-slate-800 bg-slate-950/80 p-4">
        <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">Coalition</p>
        <p className="mt-2 text-sm text-slate-500">No coalition proposal is currently visible.</p>
      </section>
    );
  }

  const selectedApproval = selectedUserId ? deal.human_approvals[selectedUserId] : undefined;
  const selectedIsParticipant = !!selectedUserId && deal.proposal.participant_ids.includes(selectedUserId);
  const canReview = deal.status === "waiting_humans" && selectedIsParticipant && selectedApproval == null;
  // Execution is a single explicit atomic command after ALL humans approved.
  // It is not a private per-user decision anymore, so any selected participant
  // may trigger it in this local operator dashboard.
  const canExecute = deal.status === "approved";

  return (
    <section className="rounded-2xl border border-violet-500/20 bg-slate-950/90 p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-xs font-semibold uppercase tracking-wider text-violet-300">Coalition proposal</p>
          <p className="mt-1 text-sm text-slate-400">
            {deal.proposal.participant_ids.length} agents · score {deal.score.toFixed(2)}
          </p>
        </div>
        <span className={`rounded-full border px-2.5 py-1 text-[11px] font-semibold uppercase ${statusClass(deal.status)}`}>
          {deal.status.replaceAll("_", " ")}
        </span>
      </div>

      <div className="mt-4 space-y-2">
        {deal.proposal.transfers.map((transfer, index) => (
          <div key={`${transfer.from_user_id}-${transfer.to_user_id}-${transfer.resource_type}-${index}`}
            className="rounded-xl border border-slate-800 bg-slate-900/60 px-3 py-2 text-sm">
            <span className="font-medium text-slate-200">{resolveUserName(transfer.from_user_id)}</span>
            <span className="mx-2 text-violet-300">→</span>
            <span className="font-medium text-slate-200">{resolveUserName(transfer.to_user_id)}</span>
            <span className="ml-2 text-slate-400">
              {transfer.quantity} {transfer.resource_type} <span className="text-slate-600">{transfer.unit}</span>
            </span>
          </div>
        ))}
      </div>

      <div className="mt-4 grid gap-3 md:grid-cols-2">
        <div className="rounded-xl border border-slate-800 bg-slate-900/40 p-3">
          <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">Agent validation</p>
          <div className="mt-2 space-y-1.5 text-xs">
            {deal.proposal.participant_ids.map((userId) => {
              const evaluation = deal.agent_evaluations[userId];
              return <div key={userId} className="flex items-center justify-between gap-2">
                <span className="text-slate-300">{resolveUserName(userId)}</span>
                <span className={evaluation?.accepted ? "text-emerald-300" : evaluation ? "text-rose-300" : "text-slate-500"}>
                  {evaluation ? (evaluation.accepted ? "✓ accepted" : "✕ rejected") : "pending"}
                </span>
              </div>;
            })}
          </div>
        </div>

        <div className="rounded-xl border border-slate-800 bg-slate-900/40 p-3">
          <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">Human approval</p>
          <div className="mt-2 space-y-1.5 text-xs">
            {deal.proposal.participant_ids.map((userId) => {
              const approval = deal.human_approvals[userId];
              return <div key={userId} className="flex items-center justify-between gap-2">
                <span className="text-slate-300">{resolveUserName(userId)}</span>
                <span className={approval === true ? "text-emerald-300" : approval === false ? "text-rose-300" : "text-amber-300"}>
                  {approval === true ? "✓ approved" : approval === false ? "✕ rejected" : "pending"}
                </span>
              </div>;
            })}
          </div>
        </div>
      </div>

      {canReview && approvalRevealed && (
        <div className="mt-4 rounded-xl border border-amber-500/20 bg-amber-500/5 p-3">
          <p className="text-sm font-medium text-amber-200">
            {resolveUserName(selectedUserId!)} must review this coalition.
          </p>
          <p className="mt-1 text-xs leading-5 text-slate-400">
            Every PersonalAgent already validated its own private constraints. Human approval still cannot execute anything by itself.
          </p>
          <div className="mt-3 flex gap-2">
            <button type="button" disabled={busy} onClick={onApprove}
              className="rounded-lg bg-emerald-500/15 px-3 py-2 text-xs font-semibold text-emerald-300 disabled:opacity-50">
              Approve coalition
            </button>
            <button type="button" disabled={busy} onClick={onReject}
              className="rounded-lg bg-rose-500/15 px-3 py-2 text-xs font-semibold text-rose-300 disabled:opacity-50">
              Reject coalition
            </button>
          </div>
        </div>
      )}

      {canReview && !approvalRevealed && (
        <p className="mt-4 text-xs text-cyan-200">Reading agent events before revealing this human checkpoint…</p>
      )}

      {canExecute && executionRevealed && (
        <div className="mt-4 rounded-xl border border-cyan-500/20 bg-cyan-500/5 p-3">
          <p className="text-sm font-medium text-cyan-200">All humans approved.</p>
          <p className="mt-1 text-xs leading-5 text-slate-400">
            Execution is explicit and atomic: either every transfer commits, or every inventory is rolled back.
          </p>
          <button type="button" disabled={busy} onClick={onExecute}
            className="mt-3 rounded-lg bg-cyan-500/15 px-3 py-2 text-xs font-semibold text-cyan-300 disabled:opacity-50">
            Execute atomic coalition
          </button>
        </div>
      )}

      {deal.status === "completed" && (
        <p className="mt-4 rounded-xl border border-emerald-500/20 bg-emerald-500/5 p-3 text-sm text-emerald-300">
          Coalition exchange completed atomically.
        </p>
      )}
      {terminal.has(deal.status) && deal.status !== "completed" && (
        <p className="mt-4 rounded-xl border border-rose-500/20 bg-rose-500/5 p-3 text-sm text-rose-300">
          Coalition closed without executing any partial transfer.
        </p>
      )}
    </section>
  );
}
