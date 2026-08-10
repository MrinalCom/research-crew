"""Planner specialist: a single structured LLM call, no tools.

Simple enough that a full ReAct loop would be overkill — planning here means
turning a task into a short numbered plan from the model's own reasoning, not
executing anything.
"""

from __future__ import annotations

from typing import Any

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage

from app.agents.llm import build_chat_model
from app.agents.prompts import PLANNER_SYSTEM_PROMPT
from app.graph.state import SupervisorState


async def planner_node(state: SupervisorState, *, chat_model: BaseChatModel | None = None) -> dict[str, Any]:
    model = chat_model or build_chat_model()
    response = await model.ainvoke(
        [SystemMessage(content=PLANNER_SYSTEM_PROMPT), HumanMessage(content=f"Task: {state['task']}")]
    )
    plan_text = response.content if isinstance(response.content, str) else str(response.content)
    return {"plan": plan_text, "messages": [response]}
