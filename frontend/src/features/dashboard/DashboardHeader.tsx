interface DashboardHeaderProps {
  connected?: boolean;

  currentTime?: string | null;

  usersCount?: number;

  activeNegotiationsCount?: number;
}


export function DashboardHeader({
  connected = false,
  currentTime,
  usersCount = 0,
  activeNegotiationsCount = 0,
}: DashboardHeaderProps) {
  return (
    <header className="flex flex-wrap items-center justify-between gap-4 border-b border-slate-800 bg-slate-950/90 px-5 py-4 backdrop-blur">
      <div>
        <p className="text-xs font-semibold uppercase tracking-[0.2em] text-cyan-400">
          Compute Exchange
        </p>

        <h1 className="mt-1 text-xl font-semibold text-slate-100">
          Agentic Resource Market
        </h1>
      </div>

      <div className="flex flex-wrap items-center gap-2 text-xs">
        <Metric
          label="Users"
          value={String(
            usersCount,
          )}
        />

        <Metric
          label="Active negotiations"
          value={String(
            activeNegotiationsCount,
          )}
        />

        <Metric
          label="Virtual time"
          value={
            currentTime
              ? new Date(
                  currentTime,
                ).toLocaleTimeString()
              : "--:--"
          }
        />

        <div className="inline-flex items-center gap-2 rounded-xl border border-slate-800 bg-slate-900 px-3 py-2">
          <span
            className={[
              "h-2 w-2 rounded-full",
              connected
                ? "bg-emerald-400"
                : "bg-rose-400",
            ].join(" ")}
          />

          <span className="text-slate-400">
            {connected
              ? "Live"
              : "Disconnected"}
          </span>
        </div>
      </div>
    </header>
  );
}


function Metric({
  label,
  value,
}: {
  label: string;
  value: string;
}) {
  return (
    <div className="rounded-xl border border-slate-800 bg-slate-900 px-3 py-2">
      <span className="text-slate-600">
        {label}
      </span>

      <span className="ml-2 font-semibold text-slate-300">
        {value}
      </span>
    </div>
  );
}
