import type {
  EventExecution,
  MarketEvent,
} from "../../types/simulation";


type EventCardProps =
  | {
      event: MarketEvent;
      execution?: never;
    }
  | {
      event?: never;
      execution: EventExecution;
    };


export function EventCard(
  props: EventCardProps,
) {
  if (props.event) {
    const event =
      props.event;

    return (
      <div className="rounded-xl border border-slate-800 bg-slate-950/60 p-3">
        <div className="flex items-center justify-between gap-3">
          <span className="text-xs font-semibold text-slate-300">
            {event.event_type.replaceAll(
              "_",
              " ",
            )}
          </span>

          <span className="text-[10px] text-slate-600">
            {new Date(
              event.scheduled_at,
            ).toLocaleTimeString()}
          </span>
        </div>

        <p className="mt-1 text-xs text-slate-500">
          User: {event.user_id}
        </p>

        {event.reason && (
          <p className="mt-2 text-xs leading-5 text-slate-500">
            {event.reason}
          </p>
        )}
      </div>
    );
  }

  const execution =
    props.execution;

  return (
    <div className="rounded-xl border border-slate-800 bg-slate-950/60 p-3">
      <div className="flex items-center justify-between gap-3">
        <span
          className={
            execution.success
              ? "text-xs font-semibold text-emerald-300"
              : "text-xs font-semibold text-rose-300"
          }
        >
          {execution.success
            ? "Executed"
            : "Failed"}
        </span>

        <span className="text-[10px] text-slate-600">
          {new Date(
            execution.executed_at,
          ).toLocaleTimeString()}
        </span>
      </div>

      <p className="mt-1 text-xs font-medium text-slate-300">
        {execution.event_type.replaceAll(
          "_",
          " ",
        )}
      </p>

      <p className="mt-2 text-xs leading-5 text-slate-500">
        {execution.message}
      </p>
    </div>
  );
}
