export interface Artifact {
  id: string;
  kind: "research_note" | "code_file" | "plan" | "final_report";
  content: string;
  author: string;
  version: number;
}

export interface ReviewVerdict {
  approved: boolean;
  feedback: string;
  target_artifact_id: string;
}

export interface InterruptPayload {
  task: string;
  artifact: Artifact | null;
  review_history: ReviewVerdict[];
  revision_count: number;
}

export type NodeStatusValue = "started" | "completed" | "waiting";

export const GRAPH_NODES = [
  "supervisor",
  "planner",
  "researcher",
  "analyst",
  "join_research",
  "coder",
  "reviewer",
  "revise_router",
  "human_review",
  "finalize",
] as const;

export type GraphNode = (typeof GRAPH_NODES)[number];
