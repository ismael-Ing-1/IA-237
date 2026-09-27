import type {
  ReactNode,
} from "react";


interface StickyHeaderProps {
  children: ReactNode;

  className?: string;
}


export function StickyHeader({
  children,
  className = "",
}: StickyHeaderProps) {
  return (
    <header
      className={[
        "sticky top-0 z-40 border-b border-slate-800 bg-slate-950/90 backdrop-blur",
        className,
      ].join(" ")}
    >
      {children}
    </header>
  );
}
