import type {
  AgentDecision,
} from "../../types/agent";

import {
  AgentStatus,
} from "./AgentStatus";


interface AgentDecisionCardProps {
  decision: AgentDecision;
}


export function AgentDecisionCard({
  decision,
}: AgentDecisionCardProps) {
  return (
    <div className="rounded-xl border border-slate-800 bg-slate-950/70 p-4">
      <div className="flex items-center justify-between gap-3">
        <AgentStatus
          action={decision.action}
        />

        {decision.partner_id && (
          <span className="text-xs text-slate-500">
            Partner:{" "}
            {decision.partner_id}
          </span>
        )}
      </div>

      <p className="mt-3 text-sm leading-6 text-slate-300">
        {decision.reason}
      </p>

      {(decision.negotiation_id ||
        decision.offer_id) && (
        <div className="mt-3 space-y-1 text-xs text-slate-500">
          {decision.negotiation_id && (
            <p>
              Negotiation:{" "}
              {decision.negotiation_id}
            </p>
          )}

          {decision.offer_id && (
            <p>
              Offer:{" "}
              {decision.offer_id}
            </p>
          )}
        </div>
      )}
    </div>
  );
}
