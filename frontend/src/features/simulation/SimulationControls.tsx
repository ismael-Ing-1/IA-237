import {
  useSimulation,
} from "../../hooks/useSimulation";

import {
  VirtualClock,
} from "./VirtualClock";


export function SimulationControls() {
  const {
    currentTime,
    advanceTime,
    isAdvancing,
  } = useSimulation();

  async function advance(
    input: {
      minutes?: number;
      hours?: number;
    },
  ) {
    await advanceTime(input);
  }

  return (
    <section className="rounded-2xl border border-slate-800 bg-slate-950/80 p-4">
      <div className="grid gap-4 md:grid-cols-[180px_1fr]">
        <VirtualClock
          currentTime={currentTime}
        />

        <div>
          <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">
            Simulation controls
          </p>

          <p className="mt-1 text-sm text-slate-400">
            Advance virtual time without
            waiting in real time.
          </p>

          <div className="mt-4 flex flex-wrap gap-2">
            <TimeButton
              disabled={isAdvancing}
              onClick={() =>
                advance({
                  minutes: 1,
                })
              }
            >
              +1 min
            </TimeButton>

            <TimeButton
              disabled={isAdvancing}
              onClick={() =>
                advance({
                  minutes: 5,
                })
              }
            >
              +5 min
            </TimeButton>

            <TimeButton
              disabled={isAdvancing}
              onClick={() =>
                advance({
                  minutes: 10,
                })
              }
            >
              +10 min
            </TimeButton>

            <TimeButton
              disabled={isAdvancing}
              onClick={() =>
                advance({
                  hours: 1,
                })
              }
            >
              +1 hour
            </TimeButton>
          </div>
        </div>
      </div>
    </section>
  );
}


function TimeButton({
  children,
  disabled,
  onClick,
}: {
  children: React.ReactNode;
  disabled?: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      disabled={disabled}
      onClick={onClick}
      className="rounded-xl border border-slate-700 bg-slate-900 px-3 py-2 text-sm font-medium text-slate-300 transition hover:border-cyan-500 hover:text-cyan-300 disabled:cursor-not-allowed disabled:opacity-50"
    >
      {children}
    </button>
  );
}
