import type { ReactNode } from "react";

export function RightPanel({
  children,
}: {
  children: ReactNode;
}) {
  return (
    <div className="h-[520px] min-h-0 overflow-hidden rounded-2xl border border-slate-800 bg-slate-950/80 p-4 xl:h-full">
      {children}
    </div>
  );
}
