import type {
  AgentAction,
} from "../../types/agent";


interface AgentStatusProps {
  action?: AgentAction | null;

  online?: boolean;
}


const labels: Record<
  AgentAction,
  string
> = {
  search_market: "Searching market",
  start_negotiation: "Negotiating",
  accept: "Offer accepted",
  counter: "Counter-offer",
  reject: "Rejected",
  ask_mediator: "Requesting mediator",
  search_coalition: "Searching coalition",
  wait_human: "Waiting for approval",
  stop: "Stopped",
};


export function AgentStatus({
  action,
  online = true,
}: AgentStatusProps) {
  if (!online) {
    return (
      <StatusPill
        dotClass="bg-slate-500"
        label="Offline"
      />
    );
  }

  if (!action) {
    return (
      <StatusPill
        dotClass="bg-emerald-400"
        label="Idle"
      />
    );
  }

  const dotClass =
    action === "reject" ||
    action === "stop"
      ? "bg-rose-400"
      : action === "wait_human"
        ? "bg-amber-400"
        : "bg-cyan-400";

  return (
    <StatusPill
      dotClass={dotClass}
      label={labels[action]}
    />
  );
}


function StatusPill({
  dotClass,
  label,
}: {
  dotClass: string;
  label: string;
}) {
  return (
    <span className="inline-flex items-center gap-2 rounded-full border border-slate-700 bg-slate-900 px-2.5 py-1 text-xs font-medium text-slate-300">
      <span
        className={`h-2 w-2 rounded-full ${dotClass}`}
      />
      {label}
    </span>
  );
}
