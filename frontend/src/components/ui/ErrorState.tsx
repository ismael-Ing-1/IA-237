import {
  Button,
} from "./Button";


interface ErrorStateProps {
  title?: string;

  message: string;

  onRetry?: () => void;
}


export function ErrorState({
  title = "Something went wrong",
  message,
  onRetry,
}: ErrorStateProps) {
  return (
    <div className="rounded-2xl border border-rose-500/20 bg-rose-500/5 p-5">
      <p className="font-semibold text-rose-300">
        {title}
      </p>

      <p className="mt-2 text-sm leading-6 text-slate-400">
        {message}
      </p>

      {onRetry && (
        <div className="mt-4">
          <Button
            variant="danger"
            size="sm"
            onClick={onRetry}
          >
            Retry
          </Button>
        </div>
      )}
    </div>
  );
}
