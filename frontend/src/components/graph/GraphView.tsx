import { useMemo } from "react";
import { Background, Controls, MarkerType, ReactFlow, type Edge, type Node } from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { useRunStore } from "../../state/runStore";
import type { GraphNode } from "../../types";
import { AgentNode, type AgentNodeData } from "./AgentNode";

/**
 * The graph topology is fixed at build time (it mirrors backend/app/graph/build.py
 * exactly) — hardcoding the layout here is far simpler than building a
 * graph-introspection API for a shape that never changes at runtime.
 */
const LAYOUT: Record<GraphNode, { x: number; y: number; label: string }> = {
  supervisor: { x: 380, y: 0, label: "Supervisor" },
  planner: { x: 20, y: 160, label: "Planner" },
  researcher: { x: 240, y: 160, label: "Researcher" },
  analyst: { x: 460, y: 160, label: "Analyst" },
  coder: { x: 680, y: 160, label: "Coder" },
  join_research: { x: 350, y: 300, label: "Join research" },
  reviewer: { x: 680, y: 300, label: "Reviewer" },
  revise_router: { x: 680, y: 430, label: "Revise router" },
  human_review: { x: 380, y: 550, label: "Human review" },
  finalize: { x: 380, y: 680, label: "Finalize" },
};

interface EdgeDef {
  id: string;
  source: GraphNode;
  target: GraphNode;
  conditional?: boolean;
}

const EDGE_DEFS: EdgeDef[] = [
  { id: "sup-planner", source: "supervisor", target: "planner", conditional: true },
  { id: "sup-researcher", source: "supervisor", target: "researcher", conditional: true },
  { id: "sup-analyst", source: "supervisor", target: "analyst", conditional: true },
  { id: "sup-coder", source: "supervisor", target: "coder", conditional: true },
  { id: "sup-reviewer", source: "supervisor", target: "reviewer", conditional: true },
  { id: "sup-human", source: "supervisor", target: "human_review", conditional: true },
  { id: "planner-sup", source: "planner", target: "supervisor" },
  { id: "researcher-join", source: "researcher", target: "join_research" },
  { id: "analyst-join", source: "analyst", target: "join_research" },
  { id: "join-sup", source: "join_research", target: "supervisor" },
  { id: "coder-reviewer", source: "coder", target: "reviewer" },
  { id: "reviewer-revise", source: "reviewer", target: "revise_router" },
  { id: "revise-planner", source: "revise_router", target: "planner", conditional: true },
  { id: "revise-researcher", source: "revise_router", target: "researcher", conditional: true },
  { id: "revise-analyst", source: "revise_router", target: "analyst", conditional: true },
  { id: "revise-coder", source: "revise_router", target: "coder", conditional: true },
  { id: "revise-human", source: "revise_router", target: "human_review", conditional: true },
  { id: "human-finalize", source: "human_review", target: "finalize", conditional: true },
  { id: "human-sup", source: "human_review", target: "supervisor", conditional: true },
];

const nodeTypes = { agent: AgentNode };

export function GraphView() {
  const nodeStatuses = useRunStore((s) => s.nodeStatuses);

  const nodes = useMemo<Node<AgentNodeData>[]>(
    () =>
      (Object.keys(LAYOUT) as GraphNode[]).map((id) => ({
        id,
        type: "agent",
        position: { x: LAYOUT[id].x, y: LAYOUT[id].y },
        data: { label: LAYOUT[id].label, status: nodeStatuses[id] ?? "idle" },
      })),
    [nodeStatuses]
  );

  const edges = useMemo<Edge[]>(
    () =>
      EDGE_DEFS.map((e) => {
        const active = nodeStatuses[e.source] === "started";
        return {
          id: e.id,
          source: e.source,
          target: e.target,
          animated: active,
          style: {
            strokeDasharray: e.conditional ? "4 4" : undefined,
            stroke: active ? "#a78bfa" : "#3f4658",
            strokeWidth: active ? 2 : 1,
          },
          markerEnd: { type: MarkerType.ArrowClosed, color: active ? "#a78bfa" : "#3f4658" },
        };
      }),
    [nodeStatuses]
  );

  return (
    <div className="h-full w-full overflow-hidden rounded-2xl border border-white/10 bg-white/[0.02] backdrop-blur-sm">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        nodeTypes={nodeTypes}
        fitView
        proOptions={{ hideAttribution: true }}
        nodesDraggable={false}
        nodesConnectable={false}
        elementsSelectable={false}
      >
        <Background color="#242938" gap={20} />
        <Controls showInteractive={false} className="!rounded-xl !border !border-white/10 !bg-[#0d0e16]/80 [&>button]:!border-white/10 [&>button]:!bg-transparent [&>button]:!fill-slate-300 [&>button]:hover:!bg-white/5" />
      </ReactFlow>
    </div>
  );
}
