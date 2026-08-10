"""End-to-end topology test for the assembled crew graph: supervisor routing,
concurrent researcher/analyst fan-out + join, the coder/reviewer revision
loop, and the human-in-the-loop approve/finalize path — all driven by
deterministic stub nodes injected via `node_overrides` so this doesn't
require a real LLM or API key.
"""

from __future__ import annotations

from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import Command

from app.graph.build import build_graph
from app.graph.state import Artifact, ReviewVerdict, SupervisorState


def make_initial_state() -> SupervisorState:
    return SupervisorState(
        run_id="build-test-run",
        messages=[],
        task="build a small utility",
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


def _make_stub_graph():
    calls = {"planner": 0, "researcher": 0, "analyst": 0, "coder": 0, "reviewer": 0}

    def stub_supervisor(state: SupervisorState) -> dict:
        if not state.get("plan"):
            return {"next_agent": "planner"}
        artifact_ids = {a["id"] for a in state["artifacts"]}
        if "research_note" not in artifact_ids:
            return {"next_agent": "researcher"}  # expands to [researcher, analyst] via route_from_supervisor
        if "code_solution" not in artifact_ids:
            return {"next_agent": "coder"}
        return {"next_agent": "human_review"}

    def stub_planner(state: SupervisorState) -> dict:
        calls["planner"] += 1
        return {"plan": "1. research\n2. implement\n3. review"}

    def stub_researcher(state: SupervisorState) -> dict:
        calls["researcher"] += 1
        artifact = Artifact(id="research_note", kind="research_note", content="relevant findings", author="researcher", version=1)
        return {"artifacts": [artifact]}

    def stub_analyst(state: SupervisorState) -> dict:
        calls["analyst"] += 1
        artifact = Artifact(id="analysis_note", kind="research_note", content="risk analysis", author="analyst", version=1)
        return {"artifacts": [artifact]}

    def stub_coder(state: SupervisorState) -> dict:
        calls["coder"] += 1
        content = "buggy_code()" if calls["coder"] == 1 else "fixed_code()"
        artifact = Artifact(id="code_solution", kind="code_file", content=content, author="coder", version=1)
        return {"artifacts": [artifact]}

    def stub_reviewer(state: SupervisorState) -> dict:
        calls["reviewer"] += 1
        approved = calls["reviewer"] > 1
        feedback = "looks good" if approved else "fix the bug first"
        verdict = ReviewVerdict(approved=approved, feedback=feedback, target_artifact_id="code_solution")
        return {"review_history": [verdict]}

    graph = build_graph(
        checkpointer=MemorySaver(),
        node_overrides={
            "supervisor": stub_supervisor,
            "planner": stub_planner,
            "researcher": stub_researcher,
            "analyst": stub_analyst,
            "coder": stub_coder,
            "reviewer": stub_reviewer,
        },
    )
    return graph, calls


async def test_full_run_fans_out_research_then_revises_code_then_pauses_for_approval():
    graph, calls = _make_stub_graph()
    config = {"configurable": {"thread_id": "full-run-thread"}, "recursion_limit": 50}

    result = await graph.ainvoke(make_initial_state(), config)

    # fan-out: both researcher and analyst ran exactly once from a single supervisor dispatch
    assert calls["researcher"] == 1
    assert calls["analyst"] == 1
    artifact_ids = {a["id"] for a in result["artifacts"]}
    assert {"research_note", "analysis_note"}.issubset(artifact_ids)

    # revision loop: coder ran twice (rejected once, then fixed), reviewer ran twice
    assert calls["coder"] == 2
    assert calls["reviewer"] == 2
    code_artifact = next(a for a in result["artifacts"] if a["id"] == "code_solution")
    assert code_artifact["content"] == "fixed_code()"
    assert result["revision_count"] == 1

    # paused for human approval
    assert "__interrupt__" in result
    snapshot = await graph.aget_state(config)
    assert snapshot.next == ("human_review",)


async def test_approving_after_full_run_finalizes_with_reviewed_content():
    graph, calls = _make_stub_graph()
    config = {"configurable": {"thread_id": "full-run-approve-thread"}, "recursion_limit": 50}

    await graph.ainvoke(make_initial_state(), config)
    final_state = await graph.ainvoke(Command(resume={"decision": "approve"}), config)

    final_report = next(a for a in final_state["artifacts"] if a["kind"] == "final_report")
    assert final_report["content"] == "fixed_code()"
    assert final_state["next_agent"] == "done"
    # planner and reviewer/coder call counts unaffected by the human-review/finalize leg
    assert calls["planner"] == 1
