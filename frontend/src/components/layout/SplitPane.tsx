import type {
  ReactNode,
} from "react";


interface SplitPaneProps {
  left: ReactNode;

  right: ReactNode;

  leftClassName?: string;

  rightClassName?: string;

  className?: string;
}


export function SplitPane({
  left,
  right,
  leftClassName = "",
  rightClassName = "",
  className = "",
}: SplitPaneProps) {
  return (
    <div
      className={[
        "grid grid-cols-1 gap-4 lg:grid-cols-2",
        className,
      ].join(" ")}
    >
      <div className={leftClassName}>
        {left}
      </div>

      <div className={rightClassName}>
        {right}
      </div>
    </div>
  );
}
