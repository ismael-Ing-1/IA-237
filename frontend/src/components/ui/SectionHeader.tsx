import type {
  ReactNode,
} from "react";


interface SectionHeaderProps {
  title: string;

  description?: string;

  action?: ReactNode;
}


export function SectionHeader({
  title,
  description,
  action,
}: SectionHeaderProps) {
  return (
    <div className="flex flex-wrap items-start justify-between gap-3">
      <div>
        <h2 className="text-sm font-semibold text-slate-100">
          {title}
        </h2>

        {description && (
          <p className="mt-1 text-xs text-slate-500">
            {description}
          </p>
        )}
      </div>

      {action}
    </div>
  );
}
