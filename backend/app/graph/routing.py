"""Conditional-edge logic for the crew graph.

Termination guarantee: the revision-loop cutoff (`revise_router_node`) is pure
state arithmetic — it never calls an LLM. That's deliberate: if the cutoff were
judged by a model, a model that "prefers" to keep revising could make the loop
run forever. Comparing `revision_count` against `max_revisions` in plain Python
means the loop provably terminates regardless of what any agent decides.

The counting/lookup work lives in a node (`revise_router_node`) because nodes
can write state; the edge function that follows it (`route_after_revise`) does
nothing but read the `next_agent` field that node just set — keeping the actual
edge-selection function a trivial, side-effect-free lookup.
"""

from __future__ import annotations

from typing import Any, Literal

from app.graph.state import AgentName, SupervisorState


def _origin_agent_for_artifact(state: SupervisorState, artifact_id: str) -> AgentName:
    for artifact in state["artifacts"]:
        if artifact["id"] == artifact_id:
            author = artifact["author"]
            if author in ("coder", "researcher", "analyst"):
                return author  # type: ignore[return-value]
    return "coder"


def revise_router_node(state: SupervisorState) -> dict[str, Any]:
    if not state["review_history"]:
        return {"next_agent": "human_review"}

    latest = state["review_history"][-1]
    if latest["approved"]:
        return {"next_agent": "human_review"}

    new_count = state["revision_count"] + 1
    if new_count > state["max_revisions"]:
        # revisions exhausted — hand off to a human rather than looping forever
        return {"next_agent": "human_review"}

    origin_agent = _origin_agent_for_artifact(state, latest["target_artifact_id"])
    return {"revision_count": new_count, "next_agent": origin_agent}


def route_after_revise(state: SupervisorState) -> Literal["planner", "researcher", "analyst", "coder", "human_review"]:
    return state["next_agent"]  # type: ignore[return-value]


def route_from_supervisor(state: SupervisorState) -> str | list[str]:
    """Expands the supervisor's single 'researcher' choice into a concurrent
    fan-out to both `researcher` and `analyst` — the supervisor only names one
    label; this is the one place that knows it means "start the research phase"."""
    next_agent = state["next_agent"]
    if next_agent == "researcher":
        return ["researcher", "analyst"]
    return next_agent


def route_after_human_review(state: SupervisorState) -> Literal["finalize", "supervisor"]:
    if state["human_decision"] == "reject":
        return "supervisor"
    return "finalize"  # both "approve" and "edit" proceed to finalize; edit swaps in human content there
