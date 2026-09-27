export function MarketLegend() {
  return (
    <div className="flex flex-wrap items-center gap-4 rounded-xl border border-slate-800 bg-slate-950/80 px-3 py-2 text-xs text-slate-400">
      <LegendDot
        className="bg-emerald-400"
        label="Online"
      />

      <LegendLine
        className="bg-cyan-400"
        label="Negotiation"
      />

      <LegendDashed
        label="Coalition"
      />

      <span>
        Green badges = offered resources
      </span>

      <span>
        Amber badges = requested resources
      </span>
    </div>
  );
}


function LegendDot({
  className,
  label,
}: {
  className: string;
  label: string;
}) {
  return (
    <span className="inline-flex items-center gap-2">
      <span
        className={`h-2 w-2 rounded-full ${className}`}
      />
      {label}
    </span>
  );
}


function LegendLine({
  className,
  label,
}: {
  className: string;
  label: string;
}) {
  return (
    <span className="inline-flex items-center gap-2">
      <span
        className={`h-0.5 w-5 ${className}`}
      />
      {label}
    </span>
  );
}


function LegendDashed({
  label,
}: {
  label: string;
}) {
  return (
    <span className="inline-flex items-center gap-2">
      <span className="w-5 border-t-2 border-dashed border-violet-400" />
      {label}
    </span>
  );
}
