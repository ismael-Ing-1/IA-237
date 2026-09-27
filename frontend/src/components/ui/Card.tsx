import type {
  HTMLAttributes,
  ReactNode,
} from "react";


interface CardProps
  extends HTMLAttributes<HTMLDivElement> {
  children: ReactNode;

  padded?: boolean;

  interactive?: boolean;
}


export function Card({
  children,
  padded = true,
  interactive = false,
  className = "",
  ...props
}: CardProps) {
  return (
    <div
      {...props}
      className={[
        "rounded-2xl border border-slate-800 bg-slate-950/80 shadow-sm",
        padded
          ? "p-4"
          : "",
        interactive
          ? "transition hover:border-slate-700 hover:bg-slate-950"
          : "",
        className,
      ].join(" ")}
    >
      {children}
    </div>
  );
}
