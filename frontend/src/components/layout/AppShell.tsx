import type {
  ReactNode,
} from "react";


interface AppShellProps {
  header?: ReactNode;

  sidebar?: ReactNode;

  children: ReactNode;

  sidebarCollapsed?: boolean;
}


export function AppShell({
  header,
  sidebar,
  children,
  sidebarCollapsed = false,
}: AppShellProps) {
  return (
    <div className="min-h-screen bg-slate-950 text-slate-100">
      {header}

      <div
        className={[
          "grid min-h-[calc(100vh-72px)]",
          sidebar
            ? sidebarCollapsed
              ? "grid-cols-[72px_minmax(0,1fr)]"
              : "grid-cols-[260px_minmax(0,1fr)]"
            : "grid-cols-1",
        ].join(" ")}
      >
        {sidebar && (
          <aside className="border-r border-slate-800 bg-slate-950/80">
            {sidebar}
          </aside>
        )}

        <main className="min-w-0">
          {children}
        </main>
      </div>
    </div>
  );
}
