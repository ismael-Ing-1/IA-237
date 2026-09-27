interface VirtualClockProps {
  currentTime?: string | null;
}


export function VirtualClock({
  currentTime,
}: VirtualClockProps) {
  const date = currentTime
    ? new Date(currentTime)
    : null;

  return (
    <div className="rounded-xl border border-slate-800 bg-slate-950/80 px-4 py-3">
      <p className="text-[10px] font-semibold uppercase tracking-wider text-slate-500">
        Virtual time
      </p>

      <p className="mt-1 font-mono text-lg font-semibold text-slate-100">
        {date
          ? date.toLocaleTimeString(
              [],
              {
                hour: "2-digit",
                minute: "2-digit",
                second: "2-digit",
              },
            )
          : "--:--:--"}
      </p>

      {date && (
        <p className="mt-0.5 text-xs text-slate-600">
          {date.toLocaleDateString()}
        </p>
      )}
    </div>
  );
}
