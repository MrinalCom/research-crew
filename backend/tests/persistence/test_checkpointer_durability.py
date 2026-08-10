"""Proves that a run interrupted mid-execution resumes from the same thread_id
after the checkpointer is torn down and rebuilt against the same SQLite file —
standing in for a real process restart.
"""

from __future__ import annotations

import operator
from typing import Annotated, TypedDict

from langgraph.graph import END, START, StateGraph

from app.persistence.checkpointer import build_checkpointer


class CounterState(TypedDict):
    count: int
    log: Annotated[list[str], operator.add]


def increment(state: CounterState) -> dict:
    return {"count": state["count"] + 1, "log": ["incremented"]}


def finalize(state: CounterState) -> dict:
    return {"count": state["count"] + 100, "log": ["finalized"]}


def _build_graph(checkpointer):
    builder = StateGraph(CounterState)
    builder.add_node("increment", increment)
    builder.add_node("finalize", finalize)
    builder.add_edge(START, "increment")
    builder.add_edge("increment", "finalize")
    builder.add_edge("finalize", END)
    return builder.compile(checkpointer=checkpointer, interrupt_after=["increment"])


async def test_run_resumes_after_checkpointer_is_recreated_against_same_db(tmp_path, monkeypatch):
    from app.config import Settings

    db_path = tmp_path / "durability.sqlite3"
    settings = Settings(database_url=f"sqlite:///{db_path}")
    thread_id = "durability-test-thread"
    config = {"configurable": {"thread_id": thread_id}}

    # "Session 1": run up to the interrupt point, then tear the checkpointer down.
    async with build_checkpointer(settings) as checkpointer_1:
        graph_1 = _build_graph(checkpointer_1)
        paused_state = await graph_1.ainvoke({"count": 0, "log": []}, config)

        assert paused_state["count"] == 1
        assert paused_state["log"] == ["incremented"]

        snapshot = await graph_1.aget_state(config)
        assert snapshot.next == ("finalize",)  # confirms execution actually paused, not finished

    assert db_path.exists()

    # "Session 2": brand new checkpointer instance, same file, same thread_id — simulates a restart.
    async with build_checkpointer(settings) as checkpointer_2:
        graph_2 = _build_graph(checkpointer_2)

        pre_resume_state = await graph_2.aget_state(config)
        assert pre_resume_state.values["count"] == 1  # state survived the "restart"

        final_state = await graph_2.ainvoke(None, config)  # None input = resume from last checkpoint

        assert final_state["count"] == 101  # 1 (session 1) + 100 (finalize in session 2)
        assert final_state["log"] == ["incremented", "finalized"]


async def test_distinct_thread_ids_do_not_share_state(tmp_path):
    from app.config import Settings

    db_path = tmp_path / "isolation.sqlite3"
    settings = Settings(database_url=f"sqlite:///{db_path}")

    async with build_checkpointer(settings) as checkpointer:
        graph = _build_graph(checkpointer)

        config_a = {"configurable": {"thread_id": "thread-a"}}
        config_b = {"configurable": {"thread_id": "thread-b"}}

        await graph.ainvoke({"count": 0, "log": []}, config_a)
        await graph.ainvoke({"count": 50, "log": []}, config_b)

        state_a = await graph.aget_state(config_a)
        state_b = await graph.aget_state(config_b)

        assert state_a.values["count"] == 1
        assert state_b.values["count"] == 51
