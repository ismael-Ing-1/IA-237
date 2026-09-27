import type {
  NegotiationStatus,
} from "../../types/negotiation";


interface NegotiationStatusBadgeProps {
  status: NegotiationStatus;
}


const classes: Record<
  NegotiationStatus,
  string
> = {
  open:
    "border-slate-700 bg-slate-800 text-slate-300",

  negotiating:
    "border-cyan-500/30 bg-cyan-500/10 text-cyan-300",

  agreement_found:
    "border-emerald-500/30 bg-emerald-500/10 text-emerald-300",

  waiting_human:
    "border-amber-500/30 bg-amber-500/10 text-amber-300",

  approved:
    "border-emerald-500/30 bg-emerald-500/10 text-emerald-300",

  rejected:
    "border-rose-500/30 bg-rose-500/10 text-rose-300",

  cancelled:
    "border-slate-700 bg-slate-800 text-slate-400",

  failed:
    "border-rose-500/30 bg-rose-500/10 text-rose-300",
};


export function NegotiationStatusBadge({
  status,
}: NegotiationStatusBadgeProps) {
  return (
    <span
      className={[
        "inline-flex rounded-full border px-2.5 py-1",
        "text-[10px] font-semibold uppercase tracking-wider",
        classes[status],
      ].join(" ")}
    >
      {status.replaceAll(
        "_",
        " ",
      )}
    </span>
  );
}
