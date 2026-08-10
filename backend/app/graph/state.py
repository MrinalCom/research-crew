"""Shared graph state for the research/coding crew.

Design note: each specialist subgraph (planner/researcher/analyst/coder) keeps its
own private scratchpad state internally and only writes a final `Artifact` (plus a
short summary message) back into this shared state at its exit node. That keeps
tool-call noise and intermediate reasoning out of the shared context that the
supervisor and reviewer read.
"""

from __future__ import annotations

import operator
from typing import Annotated, Literal, TypedDict

from langchain_core.messages import AnyMessage
from langgraph.graph.message import add_messages

AgentName = Literal["planner", "researcher", "analyst", "coder", "reviewer", "human_review", "done"]
ArtifactKind = Literal["research_note", "code_file", "plan", "final_report"]
HumanDecision = Literal["approve", "reject", "edit"]


class Artifact(TypedDict):
    id: str
    kind: ArtifactKind
    content: str
    author: str
    version: int


class ReviewVerdict(TypedDict):
    approved: bool
    feedback: str
    target_artifact_id: str


def merge_artifacts(existing: list[Artifact], updates: list[Artifact]) -> list[Artifact]:
    """Append new artifact ids; replace-and-bump-version for ids that already exist.

    This runs on every state update that touches `artifacts`, including concurrent
    fan-out writes from `researcher` and `analyst` — both append distinct ids, so
    order between them is safe to merge either way.
    """
    by_id = {artifact["id"]: dict(artifact) for artifact in existing}
    for update in updates:
        prior = by_id.get(update["id"])
        if prior is not None:
            merged = dict(update)
            merged["version"] = prior["version"] + 1
            by_id[update["id"]] = merged
        else:
            by_id[update["id"]] = dict(update)
    return list(by_id.values())


def latest_feedback_for(state: "SupervisorState", artifact_id: str) -> str | None:
    """Feedback from the most recent unapproved review targeting `artifact_id`, if any.

    Used by specialist nodes to inject reviewer feedback into a revision attempt
    without re-reading feedback that was already addressed and approved.
    """
    for verdict in reversed(state["review_history"]):
        if verdict["target_artifact_id"] != artifact_id:
            continue
        return None if verdict["approved"] else verdict["feedback"]
    return None


class SupervisorState(TypedDict):
    run_id: str
    messages: Annotated[list[AnyMessage], add_messages]
    task: str
    plan: str | None
    artifacts: Annotated[list[Artifact], merge_artifacts]
    review_history: Annotated[list[ReviewVerdict], operator.add]
    revision_count: int
    max_revisions: int
    next_agent: AgentName
    pending_approval: dict | None
    human_decision: HumanDecision | None
    human_edit_content: str | None
