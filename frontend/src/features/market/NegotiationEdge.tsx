import {
  BaseEdge,
  EdgeLabelRenderer,
  getBezierPath,
  type Edge,
  type EdgeProps,
} from "@xyflow/react";

import type {
  NegotiationStatus,
} from "../../types/negotiation";


export interface NegotiationEdgeData
  extends Record<string, unknown> {
  status: NegotiationStatus;

  negotiationId: string;
}


export type NegotiationFlowEdge = Edge<
  NegotiationEdgeData,
  "negotiation"
>;


export function NegotiationEdge({
  id,
  sourceX,
  sourceY,
  targetX,
  targetY,
  sourcePosition,
  targetPosition,
  markerEnd,
  data,
}: EdgeProps<NegotiationFlowEdge>) {
  const [
    edgePath,
    labelX,
    labelY,
  ] = getBezierPath({
    sourceX,
    sourceY,
    sourcePosition,
    targetX,
    targetY,
    targetPosition,
  });

  const active =
    data?.status === "negotiating" ||
    data?.status === "agreement_found" ||
    data?.status === "waiting_human";

  return (
    <>
      <BaseEdge
        id={id}
        path={edgePath}
        markerEnd={markerEnd}
        style={{
          strokeWidth: active ? 2.5 : 1.5,
          stroke: active
            ? "#22d3ee"
            : "#475569",
        }}
      />

      <EdgeLabelRenderer>
        <div
          className="pointer-events-none absolute rounded-full border border-slate-700 bg-slate-950/95 px-2 py-1 text-[10px] font-semibold uppercase tracking-wider text-slate-300 shadow-lg"
          style={{
            transform: `translate(-50%, -50%) translate(${labelX}px, ${labelY}px)`,
          }}
        >
          {data?.status ?? "negotiation"}
        </div>
      </EdgeLabelRenderer>
    </>
  );
}
