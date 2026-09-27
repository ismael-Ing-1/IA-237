import type {
  MarketEvent,
} from "../../types/simulation";

import {
  EventCard,
} from "./EventCard";


interface UpcomingEventsProps {
  events: MarketEvent[];
}


export function UpcomingEvents({
  events,
}: UpcomingEventsProps) {
  const sorted = [
    ...events,
  ].sort(
    (a, b) =>
      new Date(
        a.scheduled_at,
      ).getTime() -
      new Date(
        b.scheduled_at,
      ).getTime(),
  );

  return (
    <section>
      <div className="mb-3 flex items-center justify-between">
        <div>
          <p className="text-sm font-semibold text-slate-100">
            Upcoming events
          </p>

          <p className="text-xs text-slate-500">
            Scheduled market changes
          </p>
        </div>

        <span className="rounded-full border border-slate-800 px-2 py-1 text-xs text-slate-500">
          {events.length}
        </span>
      </div>

      <div className="space-y-2">
        {sorted.length > 0 ? (
          sorted.map((event) => (
            <EventCard
              key={event.id}
              event={event}
            />
          ))
        ) : (
          <div className="rounded-xl border border-dashed border-slate-800 p-5 text-center text-sm text-slate-600">
            No scheduled events.
          </div>
        )}
      </div>
    </section>
  );
}
