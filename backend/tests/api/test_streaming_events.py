"""Verifies the astream_events -> SSE translation against the real compiled
graph (with stub specialist nodes, no LLM calls) so we're checking actual
LangGraph event shapes rather than assumptions about them.
"""

from __future__ import annotations

import json

from langgraph.checkpoint.memory import MemorySaver

from app.graph.build import build_graph
from app.graph.state import Artifact, ReviewVerdict, SupervisorState
from app.streaming.events import stream_graph_events


def make_initial_state() -> SupervisorState:
    return SupervisorState(
        run_id="stream-test-run",
        messages=[],
        task="do a thing",
        plan=None,
        artifacts=[],
        review_history=[],
        revision_count=0,
        max_revisions=3,
        next_agent="planner",
        pending_approval=None,
        human_decision=None,
        human_edit_content=None,
    )


def _stub_graph():
    def stub_supervisor(state: SupervisorState) -> dict:
        if not state.get("plan"):
            return {"next_agent": "planner"}
        return {"next_agent": "human_review"}

    def stub_planner(state: SupervisorState) -> dict:
        return {"plan": "1. do it"}

    graph = build_graph(
        checkpointer=MemorySaver(),
        node_overrides={"supervisor": stub_supervisor, "planner": stub_planner},
    )
    return graph


async def test_stream_emits_node_status_for_known_nodes_only():
    graph = _stub_graph()
    config = {"configurable": {"thread_id": "stream-thread-1"}}

    events = [e async for e in stream_graph_events(graph, make_initial_state(), config)]

    node_status_events = [json.loads(e["data"]) for e in events if e["event"] == "node_status"]
    nodes_seen = {e["node"] for e in node_status_events}

    # supervisor (x2) -> planner -> supervisor -> human_review, which then pauses mid-node
    assert nodes_seen == {"supervisor", "planner", "human_review"}
    assert all(e["status"] in ("started", "completed") for e in node_status_events)

    started = [e["node"] for e in node_status_events if e["status"] == "started"]
    completed = [e["node"] for e in node_status_events if e["status"] == "completed"]
    # human_review starts (so the frontend can show "awaiting approval") but never
    # completes in this stream — it paused inside the node via interrupt()
    assert sorted(started) == sorted(completed + ["human_review"])


async def test_stream_ends_with_interrupt_event_when_run_pauses():
    graph = _stub_graph()
    config = {"configurable": {"thread_id": "stream-thread-2"}}

    events = [e async for e in stream_graph_events(graph, make_initial_state(), config)]

    assert events[-1]["event"] == "interrupt"
    payload = json.loads(events[-1]["data"])
    assert payload["next"] == ["human_review"]
    assert "run_complete" not in [e["event"] for e in events]


async def test_stream_ends_with_run_complete_after_full_completion():
    from langgraph.types import Command

    graph = _stub_graph()
    config = {"configurable": {"thread_id": "stream-thread-3"}}

    await graph.ainvoke(make_initial_state(), config)  # pause at human_review

    events = [e async for e in stream_graph_events(graph, Command(resume={"decision": "approve"}), config)]

    assert events[-1]["event"] == "run_complete"
    assert json.loads(events[-1]["data"]) == {"status": "completed"}


async def test_stream_yields_error_event_on_node_exception_instead_of_raising():
    def broken_supervisor(state: SupervisorState) -> dict:
        raise ValueError("boom")

    graph = build_graph(
        checkpointer=MemorySaver(),
        node_overrides={"supervisor": broken_supervisor},
    )
    config = {"configurable": {"thread_id": "stream-thread-error"}}

    events = [e async for e in stream_graph_events(graph, make_initial_state(), config)]

    assert events[-1]["event"] == "error"
    assert "boom" in json.loads(events[-1]["data"])["message"]
