import type {
  ReactNode,
} from "react";


interface PageContainerProps {
  children: ReactNode;

  className?: string;

  maxWidth?: "full" | "7xl" | "6xl";
}


const widths = {
  full: "max-w-none",
  "7xl": "max-w-7xl",
  "6xl": "max-w-6xl",
};


export function PageContainer({
  children,
  className = "",
  maxWidth = "full",
}: PageContainerProps) {
  return (
    <div
      className={[
        "mx-auto w-full px-4 py-4 md:px-5",
        widths[maxWidth],
        className,
      ].join(" ")}
    >
      {children}
    </div>
  );
}
