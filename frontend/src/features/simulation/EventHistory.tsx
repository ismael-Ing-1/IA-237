import type {
  EventExecution,
} from "../../types/simulation";

import {
  EventCard,
} from "./EventCard";


interface EventHistoryProps {
  events: EventExecution[];

  maxItems?: number;
}


export function EventHistory({
  events,
  maxItems = 12,
}: EventHistoryProps) {
  const latest = [
    ...events,
  ]
    .reverse()
    .slice(0, maxItems);

  return (
    <section>
      <div className="mb-3">
        <p className="text-sm font-semibold text-slate-100">
          Event history
        </p>

        <p className="text-xs text-slate-500">
          Latest executed simulation
          events
        </p>
      </div>

      <div className="space-y-2">
        {latest.length > 0 ? (
          latest.map(
            (execution) => (
              <EventCard
                key={
                  execution.event_id
                }
                execution={execution}
              />
            ),
          )
        ) : (
          <div className="rounded-xl border border-dashed border-slate-800 p-5 text-center text-sm text-slate-600">
            No events executed yet.
          </div>
        )}
      </div>
    </section>
  );
}
