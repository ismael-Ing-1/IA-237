interface DividerProps {
  className?: string;
}


export function Divider({
  className = "",
}: DividerProps) {
  return (
    <div
      className={[
        "h-px w-full bg-slate-800",
        className,
      ].join(" ")}
    />
  );
}
