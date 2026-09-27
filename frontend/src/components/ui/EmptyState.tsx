import type {
  ReactNode,
} from "react";


interface EmptyStateProps {
  title: string;

  description?: string;

  action?: ReactNode;
}


export function EmptyState({
  title,
  description,
  action,
}: EmptyStateProps) {
  return (
    <div className="rounded-2xl border border-dashed border-slate-800 bg-slate-950/40 p-8 text-center">
      <div className="mx-auto h-10 w-10 rounded-full border border-slate-800 bg-slate-900" />

      <h3 className="mt-4 text-sm font-semibold text-slate-200">
        {title}
      </h3>

      {description && (
        <p className="mx-auto mt-2 max-w-sm text-sm leading-6 text-slate-500">
          {description}
        </p>
      )}

      {action && (
        <div className="mt-4">
          {action}
        </div>
      )}
    </div>
  );
}
