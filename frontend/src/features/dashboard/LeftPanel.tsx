import type { ReactNode } from "react";

export function LeftPanel({
  children,
}: {
  children: ReactNode;
}) {
  return (
    <div className="space-y-4 pb-1">
      {children}
    </div>
  );
}
