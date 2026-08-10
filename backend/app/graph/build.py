"""Assembles the top-level crew graph from the node functions defined across
`app/agents/`, `app/subgraphs/`, and `app/graph/`.

`node_overrides` exists for two real reasons, not speculative flexibility:
tests need to swap LLM-calling nodes for deterministic stubs to verify graph
topology without hitting a real model, and `coder_node` needs a `workspace_root`
closed over per-build rather than hardcoded.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from langchain_core.language_models import BaseChatModel
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from app.agents.reviewer import reviewer_node
from app.agents.supervisor import supervisor_node
from app.graph.human_review import finalize_node, human_review_node
from app.graph.routing import (
    revise_router_node,
    route_after_human_review,
    route_after_revise,
    route_from_supervisor,
)
from app.graph.state import SupervisorState
from app.subgraphs.coder_graph import coder_node
from app.subgraphs.planner_graph import planner_node
from app.subgraphs.research_team import analyst_node, join_research_node, researcher_node

DEFAULT_WORKSPACE_ROOT = Path("./workspaces")


def build_graph(
    *,
    checkpointer: BaseCheckpointSaver,
    workspace_root: Path = DEFAULT_WORKSPACE_ROOT,
    chat_model: BaseChatModel | None = None,
    node_overrides: dict[str, Callable[..., Any]] | None = None,
) -> CompiledStateGraph:
    async def _supervisor(state: SupervisorState) -> dict:
        return await supervisor_node(state, chat_model=chat_model)

    async def _planner(state: SupervisorState) -> dict:
        return await planner_node(state, chat_model=chat_model)

    async def _researcher(state: SupervisorState) -> dict:
        return await researcher_node(state, chat_model=chat_model)

    async def _analyst(state: SupervisorState) -> dict:
        return await analyst_node(state, chat_model=chat_model)

    async def _coder(state: SupervisorState) -> dict:
        return await coder_node(state, workspace_root=workspace_root, chat_model=chat_model)

    async def _reviewer(state: SupervisorState) -> dict:
        return await reviewer_node(state, chat_model=chat_model)

    nodes: dict[str, Callable[..., Any]] = {
        "supervisor": _supervisor,
        "planner": _planner,
        "researcher": _researcher,
        "analyst": _analyst,
        "join_research": join_research_node,
        "coder": _coder,
        "reviewer": _reviewer,
        "revise_router": revise_router_node,
        "human_review": human_review_node,
        "finalize": finalize_node,
    }
    nodes.update(node_overrides or {})

    builder = StateGraph(SupervisorState)
    for name, fn in nodes.items():
        builder.add_node(name, fn)

    builder.add_edge(START, "supervisor")
    builder.add_conditional_edges(
        "supervisor",
        route_from_supervisor,
        {
            "planner": "planner",
            "researcher": "researcher",
            "analyst": "analyst",
            "coder": "coder",
            "reviewer": "reviewer",
            "human_review": "human_review",
        },
    )
    builder.add_edge("planner", "supervisor")
    builder.add_edge("researcher", "join_research")
    builder.add_edge("analyst", "join_research")
    builder.add_edge("join_research", "supervisor")
    builder.add_edge("coder", "reviewer")
    builder.add_edge("reviewer", "revise_router")
    builder.add_conditional_edges(
        "revise_router",
        route_after_revise,
        {
            "planner": "planner",
            "researcher": "researcher",
            "analyst": "analyst",
            "coder": "coder",
            "human_review": "human_review",
        },
    )
    builder.add_conditional_edges(
        "human_review",
        route_after_human_review,
        {"finalize": "finalize", "supervisor": "supervisor"},
    )
    builder.add_edge("finalize", END)

    return builder.compile(checkpointer=checkpointer)
