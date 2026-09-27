interface StatCardProps {
  label: string;

  value: string | number;

  hint?: string;
}


export function StatCard({
  label,
  value,
  hint,
}: StatCardProps) {
  return (
    <div className="rounded-xl border border-slate-800 bg-slate-950/70 p-3">
      <p className="text-[10px] font-semibold uppercase tracking-wider text-slate-500">
        {label}
      </p>

      <p className="mt-1 text-xl font-semibold text-slate-100">
        {value}
      </p>

      {hint && (
        <p className="mt-1 text-xs text-slate-600">
          {hint}
        </p>
      )}
    </div>
  );
}
