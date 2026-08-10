"""Reviewer specialist: structured-output critique of the latest artifact.

No tools, no scratchpad — a single structured-output LLM call, kept separate
from the ReAct-style specialists in `app/subgraphs/`.
"""

from __future__ import annotations

from typing import Any

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from app.agents.llm import build_chat_model
from app.agents.prompts import REVIEWER_SYSTEM_PROMPT
from app.graph.state import Artifact, ReviewVerdict, SupervisorState


class ReviewVerdictModel(BaseModel):
    approved: bool = Field(
        description="Whether the artifact meets the task's requirements and is ready for human approval."
    )
    feedback: str = Field(
        description="Specific, actionable feedback. If approved, briefly say why it's acceptable."
    )
    target_artifact_id: str = Field(description="The id of the artifact being reviewed.")


def latest_reviewable_artifact(state: SupervisorState) -> Artifact | None:
    candidates = [a for a in state["artifacts"] if a["kind"] in ("code_file", "research_note")]
    return candidates[-1] if candidates else None


async def reviewer_node(state: SupervisorState, *, chat_model: BaseChatModel | None = None) -> dict[str, Any]:
    artifact = latest_reviewable_artifact(state)
    if artifact is None:
        verdict = ReviewVerdict(approved=False, feedback="no artifact to review yet", target_artifact_id="")
        return {"review_history": [verdict]}

    model = (chat_model or build_chat_model()).with_structured_output(ReviewVerdictModel)
    prompt = (
        f"Task: {state['task']}\n\n"
        f"Plan:\n{state.get('plan') or '(none)'}\n\n"
        f"Artifact to review (id={artifact['id']}, kind={artifact['kind']}):\n{artifact['content']}"
    )
    result = await model.ainvoke([SystemMessage(content=REVIEWER_SYSTEM_PROMPT), HumanMessage(content=prompt)])

    verdict = ReviewVerdict(
        approved=result.approved,
        feedback=result.feedback,
        target_artifact_id=result.target_artifact_id or artifact["id"],
    )
    return {"review_history": [verdict]}
