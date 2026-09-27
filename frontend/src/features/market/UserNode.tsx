import {
  Handle,
  Position,
  type Node,
  type NodeProps,
} from "@xyflow/react";

import type {
  PublicUserProfile,
} from "../../types/user";

import {
  ResourceBadge,
} from "./ResourceBadge";


export interface UserNodeData
  extends Record<string, unknown> {
  profile: PublicUserProfile;

  reputation?: number;

  isSelected?: boolean;
}


export type UserFlowNode = Node<
  UserNodeData,
  "user"
>;


export function UserNode({
  data,
}: NodeProps<UserFlowNode>) {
  const {
    profile,
    reputation,
    isSelected,
  } = data;

  return (
    <div
      className={[
        "min-w-56 rounded-2xl border bg-slate-950/95 p-4 shadow-xl",
        "transition-all duration-200",
        isSelected
          ? "border-cyan-400 ring-2 ring-cyan-400/20"
          : "border-slate-800",
      ].join(" ")}
    >
      <Handle
        type="target"
        position={Position.Left}
        className="!h-2.5 !w-2.5 !border-0 !bg-cyan-400"
      />

      <Handle
        type="source"
        position={Position.Right}
        className="!h-2.5 !w-2.5 !border-0 !bg-cyan-400"
      />

      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="flex items-center gap-2">
            <span
              className={[
                "h-2.5 w-2.5 rounded-full",
                profile.online
                  ? "bg-emerald-400"
                  : "bg-slate-600",
              ].join(" ")}
            />

            <h3 className="font-semibold text-slate-100">
              {profile.display_name}
            </h3>
          </div>

          <p className="mt-1 max-w-36 truncate text-xs text-slate-500">
            {profile.user_id}
          </p>
        </div>

        {reputation !== undefined && (
          <div className="rounded-lg bg-slate-900 px-2 py-1 text-xs text-slate-300">
            Trust {reputation.toFixed(2)}
          </div>
        )}
      </div>

      <div className="mt-4">
        <p className="mb-2 text-[10px] font-semibold uppercase tracking-wider text-slate-500">
          Offers
        </p>

        <div className="flex max-w-48 flex-wrap gap-1.5">
          {profile.offered_resource_types.length > 0 ? (
            profile.offered_resource_types.map(
              (resourceType) => (
                <ResourceBadge
                  key={resourceType}
                  resourceType={resourceType}
                  variant="offer"
                />
              ),
            )
          ) : (
            <span className="text-xs text-slate-600">
              None
            </span>
          )}
        </div>
      </div>

      <div className="mt-3">
        <p className="mb-2 text-[10px] font-semibold uppercase tracking-wider text-slate-500">
          Wants
        </p>

        <div className="flex max-w-48 flex-wrap gap-1.5">
          {profile.requested_resource_types.length > 0 ? (
            profile.requested_resource_types.map(
              (resourceType) => (
                <ResourceBadge
                  key={resourceType}
                  resourceType={resourceType}
                  variant="need"
                />
              ),
            )
          ) : (
            <span className="text-xs text-slate-600">
              None
            </span>
          )}
        </div>
      </div>
    </div>
  );
}
