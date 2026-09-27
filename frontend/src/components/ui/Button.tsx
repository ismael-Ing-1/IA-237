import type {
  ButtonHTMLAttributes,
  ReactNode,
} from "react";


export type ButtonVariant =
  | "primary"
  | "secondary"
  | "ghost"
  | "danger"
  | "success"
  | "warning";


export type ButtonSize =
  | "sm"
  | "md"
  | "lg";


interface ButtonProps
  extends ButtonHTMLAttributes<HTMLButtonElement> {
  children: ReactNode;

  variant?: ButtonVariant;

  size?: ButtonSize;

  fullWidth?: boolean;

  loading?: boolean;
}


const variantClasses: Record<
  ButtonVariant,
  string
> = {
  primary:
    "bg-cyan-400 text-slate-950 hover:bg-cyan-300 border-cyan-400",

  secondary:
    "bg-slate-900 text-slate-200 hover:bg-slate-800 border-slate-700",

  ghost:
    "bg-transparent text-slate-300 hover:bg-slate-900 border-transparent",

  danger:
    "bg-rose-500/10 text-rose-300 hover:bg-rose-500/20 border-rose-500/30",

  success:
    "bg-emerald-400 text-slate-950 hover:bg-emerald-300 border-emerald-400",

  warning:
    "bg-amber-400 text-slate-950 hover:bg-amber-300 border-amber-400",
};


const sizeClasses: Record<
  ButtonSize,
  string
> = {
  sm: "px-3 py-1.5 text-xs",
  md: "px-4 py-2 text-sm",
  lg: "px-5 py-3 text-base",
};


export function Button({
  children,
  variant = "primary",
  size = "md",
  fullWidth = false,
  loading = false,
  disabled,
  className = "",
  ...props
}: ButtonProps) {
  return (
    <button
      {...props}
      disabled={
        disabled ||
        loading
      }
      className={[
        "inline-flex items-center justify-center rounded-xl border font-semibold transition",
        "focus:outline-none focus:ring-2 focus:ring-cyan-400/40",
        "disabled:cursor-not-allowed disabled:opacity-50",
        variantClasses[variant],
        sizeClasses[size],
        fullWidth
          ? "w-full"
          : "",
        className,
      ].join(" ")}
    >
      {loading ? (
        <span className="inline-flex items-center gap-2">
          <span className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-current border-r-transparent" />
          <span>Loading...</span>
        </span>
      ) : (
        children
      )}
    </button>
  );
}
