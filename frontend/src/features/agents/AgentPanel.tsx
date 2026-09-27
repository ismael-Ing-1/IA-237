import type {
  AgentAction,
} from "../../types/agent";

import type {
  PublicUserProfile,
  UserDashboard,
} from "../../types/user";

import type {
  ResourceRequest,
} from "../../types/resource";

import {
  ResourceBadge,
} from "../market/ResourceBadge";

import {
  AgentStatus,
} from "./AgentStatus";


interface AgentPanelProps {
  profile?: PublicUserProfile | null;

  dashboard?: UserDashboard | null;

  reputation?: number;

  currentAction?: AgentAction | null;

  needPreview?: ResourceRequest | null;
}


export function AgentPanel({
  profile,
  dashboard,
  reputation,
  currentAction,
  needPreview,
}: AgentPanelProps) {
  const name =
    dashboard?.name ??
    profile?.display_name ??
    "Select an agent";

  const online =
    dashboard?.online ??
    profile?.online ??
    false;

  const displayedNeeds = dashboard
    ? (
        needPreview
          ? [
              needPreview,
              ...dashboard.needs.filter(
                (need) =>
                  need.id !== needPreview.id &&
                  !(
                    need.resource_type === needPreview.resource_type &&
                    need.unit === needPreview.unit
                  ),
              ),
            ]
          : dashboard.needs
      )
    : [];

  return (
    <section className="rounded-2xl border border-slate-800 bg-slate-950/80 p-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-xs uppercase tracking-wider text-slate-500">
            Personal agent
          </p>

          <h2 className="mt-1 text-xl font-semibold text-slate-100">
            {name}
          </h2>
        </div>

        <AgentStatus
          action={currentAction}
          online={online}
        />
      </div>

      {reputation !== undefined && (
        <div className="mt-4 rounded-xl border border-slate-800 bg-slate-900/60 p-3">
          <p className="text-xs text-slate-500">
            Reputation
          </p>

          <p className="mt-1 text-2xl font-semibold text-slate-100">
            {reputation.toFixed(2)}
          </p>
        </div>
      )}

      {dashboard ? (
        <>
          <div className="mt-5">
            <p className="mb-2 text-xs font-semibold uppercase tracking-wider text-slate-500">
              Resources
            </p>

            <div className="flex flex-wrap gap-2">
              {dashboard.resources.length >
              0 ? (
                dashboard.resources.map(
                  (resource) => (
                    <ResourceBadge
                      key={resource.id}
                      resourceType={
                        resource.resource_type
                      }
                      quantity={
                        resource.quantity
                      }
                      unit={resource.unit}
                      variant="offer"
                    />
                  ),
                )
              ) : (
                <span className="text-sm text-slate-600">
                  No resources
                </span>
              )}
            </div>
          </div>

          <div className="mt-5">
            <p className="mb-2 text-xs font-semibold uppercase tracking-wider text-slate-500">
              Needs
            </p>

            <div className="flex flex-wrap gap-2">
              {displayedNeeds.length >
              0 ? (
                displayedNeeds.map(
                  (need) => (
                    <ResourceBadge
                      key={need.id}
                      resourceType={
                        need.resource_type
                      }
                      quantity={need.quantity}
                      unit={need.unit}
                      variant="need"
                    />
                  ),
                )
              ) : (
                <span className="text-sm text-emerald-400/80">
                  0 remaining · all current needs satisfied
                </span>
              )}
            </div>
          </div>

          <div className="mt-5 border-t border-slate-800 pt-4">
            <p className="text-xs text-slate-500">
              Strategy
            </p>

            <p className="mt-1 capitalize text-sm font-medium text-slate-300">
              {dashboard.strategy}
            </p>
          </div>
        </>
      ) : (
        <p className="mt-5 text-sm leading-6 text-slate-500">
          Select a user to inspect their
          public profile or owner
          dashboard.
        </p>
      )}
    </section>
  );
}
