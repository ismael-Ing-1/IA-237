import type {
  ReactNode,
} from "react";


interface PanelProps {
  children: ReactNode;

  title?: string;

  description?: string;

  headerAction?: ReactNode;

  className?: string;
}


export function Panel({
  children,
  title,
  description,
  headerAction,
  className = "",
}: PanelProps) {
  return (
    <section
      className={[
        "rounded-2xl border border-slate-800 bg-slate-950/80",
        className,
      ].join(" ")}
    >
      {(title ||
        description ||
        headerAction) && (
        <div className="flex items-start justify-between gap-4 border-b border-slate-800 px-4 py-3">
          <div>
            {title && (
              <h2 className="text-sm font-semibold text-slate-100">
                {title}
              </h2>
            )}

            {description && (
              <p className="mt-1 text-xs text-slate-500">
                {description}
              </p>
            )}
          </div>

          {headerAction}
        </div>
      )}

      <div className="p-4">
        {children}
      </div>
    </section>
  );
}
