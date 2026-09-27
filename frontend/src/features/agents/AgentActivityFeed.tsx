import {
  useEffect,
  useRef,
} from "react";

import type {
  AgentActivity,
} from "../../types/agent";


interface AgentActivityFeedProps {
  activities: AgentActivity[];

  emptyMessage?: string;
  pendingCount?: number;
  onCatchUp?: () => void;
}


export function AgentActivityFeed({
  activities,
  pendingCount = 0,
  onCatchUp,
  emptyMessage =
    "No agent activity yet.",
}: AgentActivityFeedProps) {
  const scrollRef =
    useRef<HTMLDivElement | null>(
      null,
    );

  const followRef = useRef(true);
  const lastId = activities[activities.length - 1]?.id;
  useEffect(() => {
    const element =
      scrollRef.current;

    if (!element || !followRef.current) {
      return;
    }

    element.scrollTo({
      top: element.scrollHeight,
      behavior: "auto",
    });
  }, [lastId]);

  return (
    <div className="flex h-full min-h-0 flex-col overflow-hidden">
      <div className="mb-3 flex shrink-0 items-center justify-between">
        <div>
          <p className="text-sm font-semibold text-slate-100">
            Agent activity
          </p>

          <p className="text-xs text-slate-500">
            Live reception · paced event playback
          </p>
        </div>

        <span className="rounded-full border border-slate-800 bg-slate-900 px-2 py-1 text-xs text-slate-500">
          {activities.length}
        </span>
      </div>

      {pendingCount > 0 && (
        <div className="mb-2 flex shrink-0 items-center justify-between gap-2 text-xs text-amber-200">
          <span>{pendingCount} events to reveal</span>
          {onCatchUp && <button type="button" onClick={onCatchUp} className="underline">Catch up</button>}
        </div>
      )}
      <div
        ref={scrollRef}
        onScroll={(event) => {
          const element = event.currentTarget;
          followRef.current = element.scrollHeight - element.scrollTop - element.clientHeight < 64;
        }}
        className="cx-scrollbar min-h-0 flex-1 space-y-2 overflow-y-auto overscroll-contain pr-1"
      >
        {activities.length === 0 ? (
          <div className="rounded-xl border border-dashed border-slate-800 p-6 text-center text-sm text-slate-500">
            {emptyMessage}
          </div>
        ) : (
          activities.map(
            (activity) => (
              <ActivityRow
                key={activity.id}
                activity={activity}
              />
            ),
          )
        )}
      </div>
    </div>
  );
}


function ActivityRow({
  activity,
}: {
  activity: AgentActivity;
}) {
  const time = new Date(
    activity.timestamp,
  ).toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });

  return (
    <div className="cx-animate-slide-up rounded-xl border border-slate-800 bg-slate-950/60 p-3">
      <div className="flex items-center justify-between gap-3">
        <span className="text-[10px] font-semibold uppercase tracking-wider text-cyan-300">
          {activity.title}
        </span>

        <span title="Time emitted by the backend" className="text-[10px] text-slate-600">
          {time}
        </span>
      </div>

      <p className="mt-1.5 text-xs leading-5 text-slate-400">
        {activity.message}
      </p>

      {activity.user_id && (
        <p className="mt-2 text-[10px] text-slate-600">
          Agent {activity.user_id}
        </p>
      )}
    </div>
  );
}
