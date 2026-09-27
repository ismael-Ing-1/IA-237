interface LoadingSpinnerProps {
  label?: string;

  size?: "sm" | "md" | "lg";
}


const sizes = {
  sm: "h-4 w-4",
  md: "h-6 w-6",
  lg: "h-10 w-10",
};


export function LoadingSpinner({
  label,
  size = "md",
}: LoadingSpinnerProps) {
  return (
    <div className="inline-flex items-center gap-3 text-sm text-slate-400">
      <span
        className={[
          "animate-spin rounded-full border-2 border-cyan-400 border-r-transparent",
          sizes[size],
        ].join(" ")}
      />

      {label && (
        <span>{label}</span>
      )}
    </div>
  );
}
