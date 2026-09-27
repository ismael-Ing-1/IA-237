import type {
  ReactNode,
} from "react";


interface SidebarSectionProps {
  title?: string;

  children: ReactNode;

  className?: string;
}


export function SidebarSection({
  title,
  children,
  className = "",
}: SidebarSectionProps) {
  return (
    <section
      className={[
        "p-4",
        className,
      ].join(" ")}
    >
      {title && (
        <p className="mb-3 text-[10px] font-semibold uppercase tracking-[0.18em] text-slate-600">
          {title}
        </p>
      )}

      {children}
    </section>
  );
}
