"""Run lifecycle API: create, stream, resume, list, inspect, and time-travel.

A single graph "run" maps 1:1 onto a checkpointer thread (`thread_id == run_id`).
Streaming responses are SSE, produced by `streaming.events.stream_graph_events`.
`/resume` itself returns the SSE stream for the resumed execution rather than a
plain 200 — the client always ends up consuming an SSE stream after either
`POST /runs` + `GET /runs/{id}/stream` or `POST /runs/{id}/resume`.
"""

from __future__ import annotations

import json
from typing import Any, AsyncIterator

from fastapi import APIRouter, Depends, HTTPException
from langgraph.types import Command
from sse_starlette.sse import EventSourceResponse

from app.api.deps import get_graph, get_runs_store, require_api_key
from app.api.schemas import CheckpointSummary, CreateRunRequest, ResumeRequest, RunSummary
from app.config import Settings, get_settings
from app.graph.state import SupervisorState
from app.observability.logging import get_logger
from app.persistence.runs_store import RunRecord, RunsStore
from app.streaming.events import get_pending_interrupt_payload, stream_graph_events

logger = get_logger(component="runs_api")
router = APIRouter(dependencies=[Depends(require_api_key)])


def _config_for(run_id: str) -> dict:
    return {"configurable": {"thread_id": run_id}}


def _to_summary(record: RunRecord) -> RunSummary:
    return RunSummary(**record.__dict__)


def _build_initial_state(run_id: str, record: RunRecord) -> SupervisorState:
    return SupervisorState(
        run_id=run_id,
        messages=[],
        task=record.task,
        plan=None,
        artifacts=[],
        review_history=[],
        revision_count=0,
        max_revisions=record.max_revisions,
        next_agent="supervisor",
        pending_approval=None,
        human_decision=None,
        human_edit_content=None,
    )


async def _run_and_track(graph, input_: Any, config: dict, run_id: str, runs_store: RunsStore) -> AsyncIterator[dict]:
    errored = False
    async for sse_event in stream_graph_events(graph, input_, config):
        if sse_event["event"] == "error":
            errored = True
        yield sse_event

    if errored:
        status = "failed"
    else:
        snapshot = await graph.aget_state(config)
        status = "paused" if snapshot.next else "completed"
    logger.info("run_status_updated", run_id=run_id, status=status)
    await runs_store.update_status(run_id, status)


@router.post("", response_model=RunSummary)
async def create_run(
    body: CreateRunRequest,
    runs_store: RunsStore = Depends(get_runs_store),
    settings: Settings = Depends(get_settings),
) -> RunSummary:
    max_revisions = body.max_revisions or settings.max_revisions
    record = await runs_store.create(task=body.task, max_revisions=max_revisions)
    logger.info("run_created", run_id=record.run_id, max_revisions=max_revisions)
    return _to_summary(record)


@router.get("", response_model=list[RunSummary])
async def list_runs(runs_store: RunsStore = Depends(get_runs_store)) -> list[RunSummary]:
    records = await runs_store.list()
    return [_to_summary(r) for r in records]


@router.get("/{run_id}", response_model=RunSummary)
async def get_run(run_id: str, runs_store: RunsStore = Depends(get_runs_store)) -> RunSummary:
    record = await runs_store.get(run_id)
    if record is None:
        raise HTTPException(status_code=404, detail="run not found")
    return _to_summary(record)


@router.get("/{run_id}/stream")
async def stream_run(run_id: str, graph=Depends(get_graph), runs_store: RunsStore = Depends(get_runs_store)):
    record = await runs_store.get(run_id)
    if record is None:
        raise HTTPException(status_code=404, detail="run not found")

    config = _config_for(run_id)
    snapshot = await graph.aget_state(config)

    if snapshot.next:
        # already started (paused at an interrupt, or mid-flight) — reconnecting
        # clients get a one-shot status event, not a re-run. Advance via /resume.
        # If it's paused at an interrupt, include the full payload (not just
        # "waiting") so a client that reconnects mid-approval — e.g. after a
        # page refresh — still gets the approval modal, not a dead end.
        async def waiting() -> AsyncIterator[dict]:
            yield {"event": "node_status", "data": json.dumps({"node": snapshot.next[0], "status": "waiting"})}
            payload = get_pending_interrupt_payload(snapshot)
            if payload is not None:
                yield {"event": "interrupt", "data": json.dumps({"payload": payload, "next": list(snapshot.next)}, default=str)}

        return EventSourceResponse(waiting())

    initial_state = _build_initial_state(run_id, record)
    return EventSourceResponse(_run_and_track(graph, initial_state, config, run_id, runs_store))


@router.post("/{run_id}/resume")
async def resume_run(
    run_id: str,
    body: ResumeRequest,
    graph=Depends(get_graph),
    runs_store: RunsStore = Depends(get_runs_store),
):
    record = await runs_store.get(run_id)
    if record is None:
        raise HTTPException(status_code=404, detail="run not found")

    config = _config_for(run_id)
    resume_payload = {"decision": body.decision, "edited_content": body.edited_content}
    logger.info("run_resumed", run_id=run_id, decision=body.decision)
    return EventSourceResponse(_run_and_track(graph, Command(resume=resume_payload), config, run_id, runs_store))


@router.get("/{run_id}/history", response_model=list[CheckpointSummary])
async def get_history(run_id: str, graph=Depends(get_graph)) -> list[CheckpointSummary]:
    config = _config_for(run_id)
    checkpoints: list[CheckpointSummary] = []
    async for snapshot in graph.aget_state_history(config):
        checkpoints.append(
            CheckpointSummary(
                checkpoint_id=snapshot.config["configurable"]["checkpoint_id"],
                next=list(snapshot.next),
                step=(snapshot.metadata or {}).get("step"),
            )
        )
    return checkpoints


@router.post("/{run_id}/replay_from/{checkpoint_id}")
async def replay_from(
    run_id: str,
    checkpoint_id: str,
    graph=Depends(get_graph),
    runs_store: RunsStore = Depends(get_runs_store),
):
    record = await runs_store.get(run_id)
    if record is None:
        raise HTTPException(status_code=404, detail="run not found")

    config = {"configurable": {"thread_id": run_id, "checkpoint_id": checkpoint_id}}
    return EventSourceResponse(_run_and_track(graph, None, config, run_id, runs_store))
