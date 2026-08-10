"""Supervisor: routes to the next specialist via structured LLM output.

Pure routing brain — no tools, no side effects on artifacts. The actual
fan-out (routing to both researcher and analyst at once) happens in
`graph.routing.route_from_supervisor`, which expands a single "researcher"
choice into a two-node fan-out; the supervisor itself just picks one label.
"""

from __future__ import annotations

from typing import Any, Literal

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from app.agents.llm import build_chat_model
from app.agents.prompts import SUPERVISOR_SYSTEM_PROMPT
from app.graph.state import SupervisorState

SupervisorChoice = Literal["planner", "researcher", "coder", "reviewer", "human_review"]


class SupervisorDecision(BaseModel):
    next_agent: SupervisorChoice = Field(
        description="Which specialist to invoke next. 'researcher' starts the parallel research phase "
        "(both researcher and analyst)."
    )
    reason: str = Field(description="One sentence justification.")


def _summarize_state(state: SupervisorState) -> str:
    lines = [f"Task: {state['task']}", f"Plan set: {'yes' if state.get('plan') else 'no'}"]
    artifact_summary = ", ".join(f"{a['id']}({a['kind']})" for a in state["artifacts"]) or "(none)"
    lines.append(f"Artifacts so far: {artifact_summary}")
    if state["review_history"]:
        latest = state["review_history"][-1]
        lines.append(f"Latest review: approved={latest['approved']} feedback={latest['feedback']}")
    return "\n".join(lines)


async def supervisor_node(state: SupervisorState, *, chat_model: BaseChatModel | None = None) -> dict[str, Any]:
    model = (chat_model or build_chat_model()).with_structured_output(SupervisorDecision)
    result = await model.ainvoke(
        [SystemMessage(content=SUPERVISOR_SYSTEM_PROMPT), HumanMessage(content=_summarize_state(state))]
    )
    return {"next_agent": result.next_agent}
