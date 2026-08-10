"""End-to-end API tests: create a run, stream it to the human-review pause,
resume with approve/reject, list/inspect runs, and pull checkpoint history —
all through the real FastAPI routes, with the graph's LLM-calling nodes
stubbed out via `node_overrides` (no API key needed) and an isolated SQLite
runs store per test.
"""

from __future__ import annotations

import json

import pytest
from httpx import ASGITransport, AsyncClient
from langgraph.checkpoint.memory import MemorySaver

from app.api.deps import get_graph, get_runs_store, require_api_key
from app.config import get_settings
from app.graph.build import build_graph
from app.graph.state import SupervisorState
from app.main import app
from app.persistence.runs_store import SqliteRunsStore

API_KEY = get_settings().api_dev_key


def _stub_supervisor(state: SupervisorState) -> dict:
    if not state.get("plan"):
        return {"next_agent": "planner"}
    return {"next_agent": "human_review"}


def _stub_planner(state: SupervisorState) -> dict:
    return {"plan": "1. do it"}


def _build_test_graph():
    return build_graph(
        checkpointer=MemorySaver(),
        node_overrides={"supervisor": _stub_supervisor, "planner": _stub_planner},
    )


def _parse_sse(text: str) -> list[dict]:
    events = []
    current_event, current_data = None, None
    for line in text.splitlines():
        if line.startswith("event:"):
            current_event = line.removeprefix("event:").strip()
        elif line.startswith("data:"):
            current_data = line.removeprefix("data:").strip()
        elif line == "" and current_event is not None:
            events.append({"event": current_event, "data": current_data})
            current_event, current_data = None, None
    if current_event is not None:
        events.append({"event": current_event, "data": current_data})
    return events


@pytest.fixture
async def client(tmp_path):
    test_graph = _build_test_graph()
    test_store = SqliteRunsStore(tmp_path / "runs.sqlite3")

    app.dependency_overrides[get_graph] = lambda: test_graph
    app.dependency_overrides[get_runs_store] = lambda: test_store

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


AUTH = {"X-API-Key": API_KEY}


async def test_create_run_requires_api_key(client):
    resp = await client.post("/runs", json={"task": "do a thing"})
    assert resp.status_code == 401


async def test_create_run_returns_run_summary(client):
    resp = await client.post("/runs", json={"task": "do a thing"}, headers=AUTH)
    assert resp.status_code == 200
    body = resp.json()
    assert body["task"] == "do a thing"
    assert body["status"] == "running"
    assert body["max_revisions"] == get_settings().max_revisions


async def test_full_stream_then_approve_resume_flow(client):
    created = (await client.post("/runs", json={"task": "build a widget"}, headers=AUTH)).json()
    run_id = created["run_id"]

    stream_resp = await client.get(f"/runs/{run_id}/stream", headers=AUTH)
    assert stream_resp.status_code == 200
    events = _parse_sse(stream_resp.text)
    assert events[-1]["event"] == "interrupt"

    mid_run = (await client.get(f"/runs/{run_id}", headers=AUTH)).json()
    assert mid_run["status"] == "paused"

    resume_resp = await client.post(f"/runs/{run_id}/resume", json={"decision": "approve"}, headers=AUTH)
    assert resume_resp.status_code == 200
    resume_events = _parse_sse(resume_resp.text)
    assert resume_events[-1]["event"] == "run_complete"

    final_run = (await client.get(f"/runs/{run_id}", headers=AUTH)).json()
    assert final_run["status"] == "completed"


async def test_reconnecting_to_a_paused_run_includes_interrupt_payload(client):
    created = (await client.post("/runs", json={"task": "build a widget"}, headers=AUTH)).json()
    run_id = created["run_id"]

    first_stream = await client.get(f"/runs/{run_id}/stream", headers=AUTH)
    assert _parse_sse(first_stream.text)[-1]["event"] == "interrupt"

    # simulate a page refresh: reconnect to the same (still-paused) run
    second_stream = await client.get(f"/runs/{run_id}/stream", headers=AUTH)
    events = _parse_sse(second_stream.text)

    statuses = [e for e in events if e["event"] == "node_status"]
    assert json.loads(statuses[0]["data"])["status"] == "waiting"

    interrupts = [e for e in events if e["event"] == "interrupt"]
    assert len(interrupts) == 1
    payload = json.loads(interrupts[0]["data"])["payload"]
    # this fixture's stub supervisor routes straight to human_review with no
    # artifact produced — the point here is that a payload dict comes through
    # at all on reconnect, not what's in it (see test_human_review.py for
    # artifact-bearing payload content).
    assert payload["task"] == "build a widget"
    assert payload["revision_count"] == 0


async def test_reject_resume_keeps_run_paused_not_completed(client):
    created = (await client.post("/runs", json={"task": "build a widget"}, headers=AUTH)).json()
    run_id = created["run_id"]
    await client.get(f"/runs/{run_id}/stream", headers=AUTH)

    resume_resp = await client.post(f"/runs/{run_id}/resume", json={"decision": "reject"}, headers=AUTH)
    resume_events = _parse_sse(resume_resp.text)

    # rejected -> routes back to supervisor -> stub picks human_review again (plan already set) -> pauses again
    assert resume_events[-1]["event"] == "interrupt"
    final_run = (await client.get(f"/runs/{run_id}", headers=AUTH)).json()
    assert final_run["status"] == "paused"


async def test_list_runs_returns_newest_first(client):
    first = (await client.post("/runs", json={"task": "first"}, headers=AUTH)).json()
    second = (await client.post("/runs", json={"task": "second"}, headers=AUTH)).json()

    listed = (await client.get("/runs", headers=AUTH)).json()
    ids_in_order = [r["run_id"] for r in listed]
    assert ids_in_order[0] == second["run_id"]
    assert ids_in_order[1] == first["run_id"]


async def test_get_missing_run_returns_404(client):
    resp = await client.get("/runs/does-not-exist", headers=AUTH)
    assert resp.status_code == 404


async def test_history_returns_checkpoints_after_a_run(client):
    created = (await client.post("/runs", json={"task": "build a widget"}, headers=AUTH)).json()
    run_id = created["run_id"]
    await client.get(f"/runs/{run_id}/stream", headers=AUTH)

    history_resp = await client.get(f"/runs/{run_id}/history", headers=AUTH)
    assert history_resp.status_code == 200
    checkpoints = history_resp.json()
    assert len(checkpoints) > 0
    assert all("checkpoint_id" in c for c in checkpoints)
