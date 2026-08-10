"""Translates `graph.astream_events` into a small, stable SSE event vocabulary
the frontend can dispatch on: `token`, `node_status`, `interrupt`,
`run_complete`, `error`.

Filtering is deliberately conservative: `astream_events` fires for every
LangChain runnable in the call chain (prompt templates, the chat model, tool
nodes inside each specialist's internal ReAct loop, ...), not just our
top-level graph nodes. We only forward events whose `langgraph_node` metadata
is one of our known top-level node names *and* whose run name matches that
node — this is what distinguishes "a top-level node started/ended" from "some
runnable nested inside a node's own subgraph started/ended".
"""

from __future__ import annotations

import json
from typing import Any, AsyncIterator

from langgraph.graph.state import CompiledStateGraph

from app.observability.logging import get_logger

logger = get_logger(component="streaming")

KNOWN_NODES = {
    "supervisor",
    "planner",
    "researcher",
    "analyst",
    "join_research",
    "coder",
    "reviewer",
    "revise_router",
    "human_review",
    "finalize",
}


def _sse(event: str, data: dict[str, Any]) -> dict[str, str]:
    return {"event": event, "data": json.dumps(data, default=str)}


def get_pending_interrupt_payload(snapshot: Any) -> Any:
    """Extract the interrupt's payload (the dict passed to `interrupt()`) from a
    state snapshot whose `next` shows it's paused. Shared by the live stream's
    end-of-run check and by `/stream`'s reconnect-to-a-paused-run path, so a
    client that refreshes mid-approval still gets the full payload, not just a
    bare "waiting" status."""
    interrupts = getattr(snapshot, "interrupts", None) or ()
    return interrupts[0].value if interrupts else None


async def stream_graph_events(graph: CompiledStateGraph, input_: Any, config: dict) -> AsyncIterator[dict[str, str]]:
    thread_id = config.get("configurable", {}).get("thread_id")
    try:
        async for event in graph.astream_events(input_, config, version="v2"):
            kind = event["event"]
            metadata = event.get("metadata", {})
            node = metadata.get("langgraph_node")

            if kind == "on_chat_model_stream" and node in KNOWN_NODES:
                chunk = event["data"].get("chunk")
                content = getattr(chunk, "content", None)
                if isinstance(content, str) and content:
                    yield _sse("token", {"node": node, "content": content})

            elif kind == "on_chain_start" and node in KNOWN_NODES and event.get("name") == node:
                logger.info("node_started", thread_id=thread_id, node=node)
                yield _sse("node_status", {"node": node, "status": "started"})

            elif kind == "on_chain_end" and node in KNOWN_NODES and event.get("name") == node:
                logger.info("node_completed", thread_id=thread_id, node=node)
                yield _sse("node_status", {"node": node, "status": "completed"})

        snapshot = await graph.aget_state(config)
        if snapshot.next:
            payload = get_pending_interrupt_payload(snapshot)
            logger.info("run_interrupted", thread_id=thread_id, next=list(snapshot.next))
            yield _sse("interrupt", {"payload": payload, "next": list(snapshot.next)})
        else:
            logger.info("run_completed", thread_id=thread_id)
            yield _sse("run_complete", {"status": "completed"})
    except Exception as exc:  # surfaced to the client rather than killing the SSE connection silently
        logger.error("run_failed", thread_id=thread_id, error=str(exc))
        yield _sse("error", {"message": str(exc)})
