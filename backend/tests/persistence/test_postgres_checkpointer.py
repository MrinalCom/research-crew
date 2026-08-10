"""Same durability guarantee as the SQLite test, verified against a real
Postgres instance (the backend used by docker-compose). Skips automatically
if no Postgres is reachable, so the rest of the suite doesn't depend on Docker
being up.
"""

from __future__ import annotations

import os

import pytest

from app.config import Settings
from app.graph.build import build_graph
from app.graph.state import Artifact, ReviewVerdict, SupervisorState
from app.persistence.checkpointer import build_checkpointer

TEST_DATABASE_URL = os.environ.get(
    "TEST_POSTGRES_URL", "postgresql://postgres:postgres@localhost:5434/langgraph_crew"
)


async def _postgres_reachable() -> bool:
    try:
        import psycopg

        async with await psycopg.AsyncConnection.connect(TEST_DATABASE_URL, connect_timeout=2):
            return True
    except Exception:
        return False


def make_initial_state() -> SupervisorState:
    return SupervisorState(
        run_id="pg-test-run",
        messages=[],
        task="build a small utility",
        plan="1. do it",
        artifacts=[Artifact(id="code_solution", kind="code_file", content="print(1)", author="coder", version=1)],
        review_history=[ReviewVerdict(approved=True, feedback="fine", target_artifact_id="code_solution")],
        revision_count=0,
        max_revisions=3,
        next_agent="human_review",
        pending_approval=None,
        human_decision=None,
        human_edit_content=None,
    )


@pytest.fixture
async def skip_if_no_postgres():
    if not await _postgres_reachable():
        pytest.skip(f"Postgres not reachable at {TEST_DATABASE_URL} — run `docker compose up -d db` to enable this test")


async def test_postgres_checkpointer_persists_interrupt_across_fresh_connections(skip_if_no_postgres):
    settings = Settings(database_url=TEST_DATABASE_URL)
    config = {"configurable": {"thread_id": "pg-durability-thread"}}

    # Stub the supervisor to route straight to human_review — this test is about
    # checkpointer durability through the real graph topology, not agent routing
    # logic (covered by test_build_graph.py), and stubbing avoids needing a real
    # LLM API key here.
    route_to_human_review = {"supervisor": lambda state: {"next_agent": "human_review"}}

    async with build_checkpointer(settings) as checkpointer_1:
        graph_1 = build_graph(checkpointer=checkpointer_1, node_overrides=route_to_human_review)
        result = await graph_1.ainvoke(make_initial_state(), config)

        assert "__interrupt__" in result
        snapshot = await graph_1.aget_state(config)
        assert snapshot.next == ("human_review",)

    # fresh saver + fresh compiled graph, same thread_id — simulates a backend restart
    async with build_checkpointer(settings) as checkpointer_2:
        graph_2 = build_graph(checkpointer=checkpointer_2, node_overrides=route_to_human_review)

        pre_resume = await graph_2.aget_state(config)
        assert pre_resume.values["task"] == "build a small utility"

        from langgraph.types import Command

        final_state = await graph_2.ainvoke(Command(resume={"decision": "approve"}), config)

        final_report = next(a for a in final_state["artifacts"] if a["kind"] == "final_report")
        assert final_report["content"] == "print(1)"
        assert final_state["next_agent"] == "done"
