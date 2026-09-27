import type {
  ReactNode,
} from "react";


export type BadgeVariant =
  | "neutral"
  | "info"
  | "success"
  | "warning"
  | "danger"
  | "purple";


interface BadgeProps {
  children: ReactNode;

  variant?: BadgeVariant;

  className?: string;
}


const variants: Record<
  BadgeVariant,
  string
> = {
  neutral:
    "border-slate-700 bg-slate-800 text-slate-300",

  info:
    "border-cyan-500/30 bg-cyan-500/10 text-cyan-300",

  success:
    "border-emerald-500/30 bg-emerald-500/10 text-emerald-300",

  warning:
    "border-amber-500/30 bg-amber-500/10 text-amber-300",

  danger:
    "border-rose-500/30 bg-rose-500/10 text-rose-300",

  purple:
    "border-violet-500/30 bg-violet-500/10 text-violet-300",
};


export function Badge({
  children,
  variant = "neutral",
  className = "",
}: BadgeProps) {
  return (
    <span
      className={[
        "inline-flex items-center rounded-full border px-2.5 py-1",
        "text-[10px] font-semibold uppercase tracking-wider",
        variants[variant],
        className,
      ].join(" ")}
    >
      {children}
    </span>
  );
}
