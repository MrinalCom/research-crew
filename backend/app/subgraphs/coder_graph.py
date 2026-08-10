"""Coder specialist: a ReAct tool-using agent scoped to its own run workspace.

Built on `langgraph.prebuilt.create_react_agent` rather than a hand-rolled
agent/tool-node loop — the tool-calling loop itself is a solved problem and
reimplementing it would just be surface area for bugs with no benefit.

The specialist's own tool-call/tool-response messages stay inside its internal
`ainvoke` and never leak into the shared `SupervisorState.messages` — only the
final summary message and the resulting artifact are written back out, per the
scratchpad-vs-shared-state separation described in graph/state.py.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage
from langgraph.prebuilt import create_react_agent

from app.agents.llm import build_chat_model
from app.agents.prompts import CODER_SYSTEM_PROMPT
from app.graph.state import Artifact, SupervisorState, latest_feedback_for
from app.tools.code_exec import make_code_exec_tool
from app.tools.file_io import make_file_tools

SOLUTION_FILENAME = "solution.py"
ARTIFACT_ID = "code_solution"


def build_coder_agent(
    workspace_dir: Path,
    *,
    timeout_seconds: int = 10,
    memory_limit_mb: int = 256,
    chat_model: BaseChatModel | None = None,
):
    tools = [
        *make_file_tools(workspace_dir),
        make_code_exec_tool(workspace_dir, timeout_seconds, memory_limit_mb),
    ]
    model = chat_model or build_chat_model()
    return create_react_agent(model, tools, prompt=CODER_SYSTEM_PROMPT)


def _build_task_brief(state: SupervisorState) -> str:
    lines = [f"Task: {state['task']}"]
    if state.get("plan"):
        lines.append(f"Plan:\n{state['plan']}")
    for note in state["artifacts"]:
        if note["kind"] == "research_note":
            lines.append(f"Research note ({note['id']}):\n{note['content']}")
    feedback = latest_feedback_for(state, ARTIFACT_ID)
    if feedback:
        lines.append(f"Reviewer feedback to address in this revision:\n{feedback}")
    return "\n\n".join(lines)


async def coder_node(
    state: SupervisorState,
    *,
    workspace_root: Path,
    chat_model: BaseChatModel | None = None,
    timeout_seconds: int = 10,
    memory_limit_mb: int = 256,
) -> dict[str, Any]:
    workspace_dir = workspace_root / state["run_id"]
    agent = build_coder_agent(
        workspace_dir,
        timeout_seconds=timeout_seconds,
        memory_limit_mb=memory_limit_mb,
        chat_model=chat_model,
    )

    brief = _build_task_brief(state)
    result = await agent.ainvoke({"messages": [HumanMessage(content=brief)]})
    final_message = result["messages"][-1]
    summary = final_message.content if isinstance(final_message.content, str) else str(final_message.content)

    solution_path = workspace_dir / SOLUTION_FILENAME
    code_content = solution_path.read_text() if solution_path.exists() else f"# no solution.py written\n# agent summary:\n# {summary}"

    artifact = Artifact(
        id=ARTIFACT_ID,
        kind="code_file",
        content=code_content,
        author="coder",
        version=1,
    )

    return {
        "artifacts": [artifact],
        "messages": [final_message],
    }
