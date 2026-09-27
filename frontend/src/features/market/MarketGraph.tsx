import {
  Background,
  Controls,
  MiniMap,
  ReactFlow,
  MarkerType,
  useReactFlow,
  type Edge,
  type Node,
} from "@xyflow/react";

import {
  useEffect,
  useMemo,
} from "react";

import type {
  RankedCoalition,
} from "../../types/agent";

import type {
  Negotiation,
} from "../../types/negotiation";

import type {
  PublicUserProfile,
} from "../../types/user";

import {
  CoalitionEdge,
  type CoalitionEdgeData,
} from "./CoalitionEdge";

import {
  NegotiationEdge,
  type NegotiationEdgeData,
} from "./NegotiationEdge";

import {
  UserNode,
  type UserNodeData,
} from "./UserNode";


const nodeTypes = {
  user: UserNode,
};


const edgeTypes = {
  negotiation: NegotiationEdge,
  coalition: CoalitionEdge,
};



function AutoFitGraph({
  signature,
}: {
  signature: string;
}) {
  const { fitView } = useReactFlow();

  useEffect(() => {
    const frame = window.requestAnimationFrame(() => {
      void fitView({
        padding: 0.18,
        duration: 280,
        maxZoom: 1.15,
      });
    });

    return () => {
      window.cancelAnimationFrame(frame);
    };
  }, [fitView, signature]);

  return null;
}


interface MarketGraphProps {
  users: PublicUserProfile[];

  negotiations?: Negotiation[];

  coalitions?: RankedCoalition[];

  selectedUserId?: string | null;

  reputations?: Record<string, number>;

  onSelectUser?: (
    userId: string,
  ) => void;
}


export function MarketGraph({
  users,
  negotiations = [],
  coalitions = [],
  selectedUserId,
  reputations = {},
  onSelectUser,
}: MarketGraphProps) {
  const nodes =
    useMemo<Node<UserNodeData>[]>(
      () => {
        const radius = Math.max(
          220,
          users.length * 42,
        );

        const centerX = 420;
        const centerY = 280;

        return users.map(
          (user, index) => {
            const angle =
              (index / Math.max(
                users.length,
                1,
              )) *
              Math.PI *
              2;

            return {
              id: user.user_id,

              type: "user",

              position: {
                x:
                  centerX +
                  Math.cos(angle) * radius,
                y:
                  centerY +
                  Math.sin(angle) * radius,
              },

              data: {
                profile: user,

                reputation:
                  reputations[
                    user.user_id
                  ],

                isSelected:
                  selectedUserId ===
                  user.user_id,
              },
            };
          },
        );
      },
      [
        users,
        reputations,
        selectedUserId,
      ],
    );

  const negotiationEdges =
    useMemo<
      Edge<NegotiationEdgeData>[]
    >(
      () =>
        negotiations.flatMap(
          (negotiation) => {
            if (
              negotiation
                .participant_ids
                .length < 2
            ) {
              return [];
            }

            const [
              source,
              ...targets
            ] =
              negotiation.participant_ids;

            return targets.map(
              (target, index) => ({
                id: `neg-${negotiation.id}-${index}`,

                source,
                target,

                type: "negotiation",

                markerEnd: {
                  type: MarkerType.ArrowClosed,
                },

                data: {
                  status:
                    negotiation.status,

                  negotiationId:
                    negotiation.id,
                },
              }),
            );
          },
        ),
      [negotiations],
    );

  const coalitionEdges =
    useMemo<Edge<CoalitionEdgeData>[]>(
      () =>
        coalitions.flatMap(
          (coalition) => {
            const transfers =
              coalition.proposal.transfers;

            if (transfers.length === 0) {
              return [];
            }

            return transfers.map(
              (transfer, index) => {
                return {
                  id: `coalition-${coalition.proposal.id}-${index}`,

                  source: transfer.from_user_id,
                  target: transfer.to_user_id,

                  type: "coalition",

                  markerEnd: {
                    type:
                      MarkerType
                        .ArrowClosed,
                  },

                  data: {
                    coalitionId:
                      coalition.proposal.id,

                    score:
                      coalition.score,
                  },
                };
              },
            );
          },
        ),
      [coalitions],
    );

  const edges = [
    ...negotiationEdges,
    ...coalitionEdges,
  ];

  const graphSignature = [
    users.map((user) => user.user_id).join(","),
    edges.map((edge) => edge.id).join(","),
  ].join("|");

  return (
    <div className="relative h-[520px] min-h-0 overflow-hidden rounded-2xl border border-slate-800 bg-slate-950 xl:h-full">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        nodeTypes={nodeTypes}
        edgeTypes={edgeTypes}
        fitView
        minZoom={0.3}
        maxZoom={1.8}
        onNodeClick={(
          _event,
          node,
        ) => {
          onSelectUser?.(node.id);
        }}
      >
        <AutoFitGraph signature={graphSignature} />

        <Background
          gap={24}
          size={1}
        />

        <Controls
          position="bottom-right"
        />

        <MiniMap
          pannable
          zoomable
          nodeStrokeWidth={2}
        />
      </ReactFlow>
    </div>
  );
}
