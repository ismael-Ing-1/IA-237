import type { ReactNode } from "react";

export function BottomPanel({
  children,
}: {
  children: ReactNode;
}) {
  return (
    <div className="grid items-start gap-4 xl:grid-cols-[minmax(0,2fr)_minmax(300px,1fr)]">
      {children}
    </div>
  );
}
