"""Human-in-the-loop approval gate.

Uses the dynamic `interrupt()` call (current recommended pattern) rather than
static `interrupt_before`/`interrupt_after` node lists — `interrupt()` lets us
hand the frontend a structured payload describing exactly what needs approval
(the artifact, recent review history, revision count) instead of just "a node
is paused". A checkpointer is required for this to work: execution state is
persisted at the interrupt point and only resumes on an explicit
`Command(resume=...)` carrying the human's decision.

This gate sits directly in front of `finalize` — the one node allowed to
produce the run's final, externally-visible output — which is the concrete
"risky action" being protected.
"""

from __future__ import annotations

from typing import Any

from langgraph.types import interrupt

from app.agents.reviewer import latest_reviewable_artifact
from app.graph.state import Artifact, SupervisorState


def human_review_node(state: SupervisorState) -> dict[str, Any]:
    artifact = latest_reviewable_artifact(state)
    payload = {
        "task": state["task"],
        "artifact": artifact,
        "review_history": state["review_history"][-3:],
        "revision_count": state["revision_count"],
    }

    decision = interrupt(payload)  # pauses here (durably) until Command(resume=decision)

    return {
        "human_decision": decision.get("decision"),
        "human_edit_content": decision.get("edited_content"),
        "pending_approval": payload,
    }


def finalize_node(state: SupervisorState) -> dict[str, Any]:
    artifact = latest_reviewable_artifact(state)
    content = artifact["content"] if artifact else ""
    author = "system"

    if state["human_decision"] == "edit" and state.get("human_edit_content"):
        content = state["human_edit_content"]
        author = "human"

    final_artifact = Artifact(id="final_report", kind="final_report", content=content, author=author, version=1)
    return {"artifacts": [final_artifact], "next_agent": "done"}
