import type {
  Resource,
  ResourceRequest,
} from "../../types/resource";


interface TransferRowProps {
  label: string;

  from: string;

  to: string;

  resources:
    | Resource[]
    | ResourceRequest[];
}


export function TransferRow({
  label,
  from,
  to,
  resources,
}: TransferRowProps) {
  return (
    <div className="rounded-xl border border-slate-800 bg-slate-950/60 p-3">
      <div className="flex items-center justify-between gap-3 text-xs">
        <span className="font-semibold uppercase tracking-wider text-slate-500">
          {label}
        </span>

        <span className="text-slate-600">
          {from} → {to}
        </span>
      </div>

      <div className="mt-2 space-y-1">
        {resources.map(
          (resource) => (
            <div
              key={resource.id}
              className="flex items-center justify-between text-sm"
            >
              <span className="font-medium text-slate-200">
                {resource.resource_type}
              </span>

              <span className="text-slate-400">
                {resource.quantity}{" "}
                {resource.unit}
              </span>
            </div>
          ),
        )}
      </div>
    </div>
  );
}
