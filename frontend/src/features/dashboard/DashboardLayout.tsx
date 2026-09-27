import type { ReactNode } from "react";

interface DashboardLayoutProps {
  header: ReactNode;
  left: ReactNode;
  center: ReactNode;
  right: ReactNode;
  bottom?: ReactNode;
}

export function DashboardLayout({
  header,
  left,
  center,
  right,
  bottom,
}: DashboardLayoutProps) {
  return (
    <div className="min-h-screen bg-slate-950 text-slate-100">
      {header}

      <main className="p-3 sm:p-4">
        <div className="grid grid-cols-1 gap-4 xl:h-[clamp(520px,58vh,660px)] xl:grid-cols-[290px_minmax(0,1fr)_320px] xl:items-stretch">
          <aside className="min-h-0 xl:overflow-y-auto xl:overscroll-contain xl:pr-1">
            {left}
          </aside>

          <section className="min-h-0 min-w-0">
            {center}
          </section>

          <aside className="min-h-0">
            {right}
          </aside>
        </div>

        {bottom && (
          <section className="mt-4">
            {bottom}
          </section>
        )}
      </main>
    </div>
  );
}
