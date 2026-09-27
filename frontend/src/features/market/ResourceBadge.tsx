interface ResourceBadgeProps {
  resourceType: string;
  quantity?: number;
  unit?: string;
  variant?: "offer" | "need" | "neutral";
}

export function ResourceBadge({
  resourceType,
  quantity,
  unit,
  variant = "neutral",
}: ResourceBadgeProps) {
  const variantClass = {
    offer:
      "border-emerald-500/30 bg-emerald-500/10 text-emerald-300",
    need:
      "border-amber-500/30 bg-amber-500/10 text-amber-300",
    neutral:
      "border-slate-700 bg-slate-800 text-slate-200",
  }[variant];

  return (
    <span
      className={[
        "inline-flex items-center gap-1 rounded-full border px-2 py-1",
        "text-xs font-medium",
        variantClass,
      ].join(" ")}
    >
      <span>{resourceType}</span>

      {quantity !== undefined && (
        <span className="opacity-80">
          {quantity}
          {unit ? ` ${unit}` : ""}
        </span>
      )}
    </span>
  );
}
