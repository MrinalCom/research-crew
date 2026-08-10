"""Researcher and analyst specialists — both ReAct agents over the same
web_search tool, run concurrently by the supervisor's fan-out and merged by
`join_research`. They're deliberately near-identical in shape (same tool,
same node contract) but carry different prompts and write to different
artifact ids, so the reviewer and revision loop can address each independently.
"""

from __future__ import annotations

from typing import Any

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage
from langgraph.prebuilt import create_react_agent

from app.agents.llm import build_chat_model
from app.agents.prompts import ANALYST_SYSTEM_PROMPT, RESEARCHER_SYSTEM_PROMPT
from app.graph.state import Artifact, SupervisorState, latest_feedback_for
from app.tools.web_search import make_web_search_tool

RESEARCH_NOTE_ARTIFACT_ID = "research_note"
ANALYSIS_NOTE_ARTIFACT_ID = "analysis_note"


def _build_task_brief(state: SupervisorState, artifact_id: str) -> str:
    lines = [f"Task: {state['task']}"]
    if state.get("plan"):
        lines.append(f"Plan:\n{state['plan']}")
    feedback = latest_feedback_for(state, artifact_id)
    if feedback:
        lines.append(f"Reviewer feedback to address in this revision:\n{feedback}")
    return "\n\n".join(lines)


async def _run_specialist(
    state: SupervisorState,
    *,
    system_prompt: str,
    artifact_id: str,
    author: str,
    chat_model: BaseChatModel | None,
) -> dict[str, Any]:
    tools = [make_web_search_tool()]
    model = chat_model or build_chat_model()
    agent = create_react_agent(model, tools, prompt=system_prompt)

    brief = _build_task_brief(state, artifact_id)
    result = await agent.ainvoke({"messages": [HumanMessage(content=brief)]})
    final_message = result["messages"][-1]
    content = final_message.content if isinstance(final_message.content, str) else str(final_message.content)

    artifact = Artifact(id=artifact_id, kind="research_note", content=content, author=author, version=1)
    return {"artifacts": [artifact], "messages": [final_message]}


async def researcher_node(state: SupervisorState, *, chat_model: BaseChatModel | None = None) -> dict[str, Any]:
    return await _run_specialist(
        state,
        system_prompt=RESEARCHER_SYSTEM_PROMPT,
        artifact_id=RESEARCH_NOTE_ARTIFACT_ID,
        author="researcher",
        chat_model=chat_model,
    )


async def analyst_node(state: SupervisorState, *, chat_model: BaseChatModel | None = None) -> dict[str, Any]:
    return await _run_specialist(
        state,
        system_prompt=ANALYST_SYSTEM_PROMPT,
        artifact_id=ANALYSIS_NOTE_ARTIFACT_ID,
        author="analyst",
        chat_model=chat_model,
    )


def join_research_node(state: SupervisorState) -> dict[str, Any]:
    """Fan-in barrier: LangGraph itself waits for both parallel branches to reach
    this node before invoking it, so no manual synchronization is needed here —
    this node just marks the merge point for routing back to the supervisor."""
    return {}
