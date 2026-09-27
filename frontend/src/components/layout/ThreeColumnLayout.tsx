import type {
  ReactNode,
} from "react";


interface ThreeColumnLayoutProps {
  left: ReactNode;

  center: ReactNode;

  right: ReactNode;

  bottom?: ReactNode;

  className?: string;
}


export function ThreeColumnLayout({
  left,
  center,
  right,
  bottom,
  className = "",
}: ThreeColumnLayoutProps) {
  return (
    <div
      className={[
        "grid grid-cols-1 gap-4 xl:grid-cols-[300px_minmax(0,1fr)_340px]",
        className,
      ].join(" ")}
    >
      <aside className="min-w-0">
        {left}
      </aside>

      <section className="min-w-0">
        {center}
      </section>

      <aside className="min-w-0">
        {right}
      </aside>

      {bottom && (
        <section className="xl:col-span-3">
          {bottom}
        </section>
      )}
    </div>
  );
}
