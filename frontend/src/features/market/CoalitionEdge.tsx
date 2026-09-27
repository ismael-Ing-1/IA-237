import {
  BaseEdge,
  getSmoothStepPath,
  type Edge,
  type EdgeProps,
} from "@xyflow/react";


export interface CoalitionEdgeData
  extends Record<string, unknown> {
  coalitionId?: string;

  score?: number;
}


export type CoalitionFlowEdge = Edge<
  CoalitionEdgeData,
  "coalition"
>;


export function CoalitionEdge({
  id,
  sourceX,
  sourceY,
  targetX,
  targetY,
  sourcePosition,
  targetPosition,
  markerEnd,
}: EdgeProps<CoalitionFlowEdge>) {
  const [edgePath] =
    getSmoothStepPath({
      sourceX,
      sourceY,
      sourcePosition,
      targetX,
      targetY,
      targetPosition,
      borderRadius: 18,
    });

  return (
    <BaseEdge
      id={id}
      path={edgePath}
      markerEnd={markerEnd}
      style={{
        strokeWidth: 2,
        stroke: "#a78bfa",
        strokeDasharray: "7 6",
      }}
    />
  );
}
