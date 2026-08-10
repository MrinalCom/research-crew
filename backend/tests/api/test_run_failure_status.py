"""A node exception mid-run must not be recorded as "paused" — that status
means "waiting for human approval" and would strand the run looking like it
needs a review that will never come. It should be "failed".
"""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient
from langgraph.checkpoint.memory import MemorySaver

from app.api.deps import get_graph, get_runs_store
from app.config import get_settings
from app.graph.build import build_graph
from app.graph.state import SupervisorState
from app.main import app
from app.persistence.runs_store import SqliteRunsStore

API_KEY = get_settings().api_dev_key
AUTH = {"X-API-Key": API_KEY}


def _broken_supervisor(state: SupervisorState) -> dict:
    raise RuntimeError("supervisor exploded")


@pytest.fixture
async def client(tmp_path):
    test_graph = build_graph(checkpointer=MemorySaver(), node_overrides={"supervisor": _broken_supervisor})
    test_store = SqliteRunsStore(tmp_path / "runs.sqlite3")

    app.dependency_overrides[get_graph] = lambda: test_graph
    app.dependency_overrides[get_runs_store] = lambda: test_store

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


async def test_run_that_errors_mid_stream_is_marked_failed_not_paused(client):
    created = (await client.post("/runs", json={"task": "will explode"}, headers=AUTH)).json()
    run_id = created["run_id"]

    stream_resp = await client.get(f"/runs/{run_id}/stream", headers=AUTH)
    assert "supervisor exploded" in stream_resp.text

    final_run = (await client.get(f"/runs/{run_id}", headers=AUTH)).json()
    assert final_run["status"] == "failed"
