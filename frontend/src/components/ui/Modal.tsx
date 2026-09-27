import {
  useEffect,
  type ReactNode,
} from "react";


interface ModalProps {
  open: boolean;

  title?: string;

  description?: string;

  children: ReactNode;

  footer?: ReactNode;

  onClose?: () => void;

  maxWidthClass?: string;
}


export function Modal({
  open,
  title,
  description,
  children,
  footer,
  onClose,
  maxWidthClass = "max-w-xl",
}: ModalProps) {
  useEffect(() => {
    if (!open) {
      return;
    }

    function handleKeyDown(
      event: KeyboardEvent,
    ) {
      if (
        event.key ===
          "Escape" &&
        onClose
      ) {
        onClose();
      }
    }

    window.addEventListener(
      "keydown",
      handleKeyDown,
    );

    return () => {
      window.removeEventListener(
        "keydown",
        handleKeyDown,
      );
    };
  }, [open, onClose]);

  if (!open) {
    return null;
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/80 p-4 backdrop-blur-sm"
      onMouseDown={(event) => {
        if (
          event.target ===
            event.currentTarget &&
          onClose
        ) {
          onClose();
        }
      }}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-label={title}
        className={[
          "w-full rounded-2xl border border-slate-700 bg-slate-900 shadow-2xl",
          maxWidthClass,
        ].join(" ")}
      >
        {(title ||
          description ||
          onClose) && (
          <div className="flex items-start justify-between gap-4 border-b border-slate-800 px-5 py-4">
            <div>
              {title && (
                <h2 className="text-lg font-semibold text-slate-100">
                  {title}
                </h2>
              )}

              {description && (
                <p className="mt-1 text-sm text-slate-500">
                  {description}
                </p>
              )}
            </div>

            {onClose && (
              <button
                type="button"
                onClick={onClose}
                className="rounded-lg border border-slate-700 px-2.5 py-1.5 text-xs text-slate-400 transition hover:bg-slate-800"
              >
                Close
              </button>
            )}
          </div>
        )}

        <div className="px-5 py-4">
          {children}
        </div>

        {footer && (
          <div className="border-t border-slate-800 px-5 py-4">
            {footer}
          </div>
        )}
      </div>
    </div>
  );
}
