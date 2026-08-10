from langgraph.graph import END, START, StateGraph

from app.graph.routing import revise_router_node, route_after_revise
from app.graph.state import Artifact, ReviewVerdict, SupervisorState


def make_initial_state(max_revisions: int) -> SupervisorState:
    return SupervisorState(
        run_id="test-run",
        messages=[],
        task="do the thing",
        plan=None,
        artifacts=[],
        review_history=[],
        revision_count=0,
        max_revisions=max_revisions,
        next_agent="coder",
        pending_approval=None,
        human_decision=None,
        human_edit_content=None,
    )


def _build_test_graph(coder_calls: list[int]):
    def coder_stub(state: SupervisorState) -> dict:
        coder_calls.append(1)
        artifact = Artifact(id="code_solution", kind="code_file", content=f"attempt {len(coder_calls)}", author="coder", version=1)
        return {"artifacts": [artifact]}

    def always_reject_reviewer(state: SupervisorState) -> dict:
        verdict = ReviewVerdict(approved=False, feedback="not good enough", target_artifact_id="code_solution")
        return {"review_history": [verdict]}

    def human_review_stub(state: SupervisorState) -> dict:
        return {"messages": [], "pending_approval": {"reached": True}}

    builder = StateGraph(SupervisorState)
    builder.add_node("coder", coder_stub)
    builder.add_node("reviewer", always_reject_reviewer)
    builder.add_node("revise_router", revise_router_node)
    builder.add_node("human_review", human_review_stub)

    builder.add_edge(START, "coder")
    builder.add_edge("coder", "reviewer")
    builder.add_edge("reviewer", "revise_router")
    builder.add_conditional_edges(
        "revise_router",
        route_after_revise,
        {
            "coder": "coder",
            "researcher": "coder",
            "analyst": "coder",
            "planner": "coder",
            "human_review": "human_review",
        },
    )
    builder.add_edge("human_review", END)

    return builder.compile()


def test_revision_loop_terminates_at_max_revisions_with_always_reject_reviewer():
    max_revisions = 2
    coder_calls: list[int] = []
    graph = _build_test_graph(coder_calls)

    final_state = graph.invoke(make_initial_state(max_revisions), config={"recursion_limit": 50})

    # 1 initial attempt + max_revisions retries, never more
    assert len(coder_calls) == max_revisions + 1
    assert final_state["revision_count"] == max_revisions
    assert final_state["pending_approval"] == {"reached": True}
    assert final_state["next_agent"] == "human_review"


def test_revision_loop_exits_immediately_when_reviewer_approves():
    def coder_stub(state: SupervisorState) -> dict:
        artifact = Artifact(id="code_solution", kind="code_file", content="good", author="coder", version=1)
        return {"artifacts": [artifact]}

    def always_approve_reviewer(state: SupervisorState) -> dict:
        verdict = ReviewVerdict(approved=True, feedback="looks great", target_artifact_id="code_solution")
        return {"review_history": [verdict]}

    def human_review_stub(state: SupervisorState) -> dict:
        return {"pending_approval": {"reached": True}}

    builder = StateGraph(SupervisorState)
    builder.add_node("coder", coder_stub)
    builder.add_node("reviewer", always_approve_reviewer)
    builder.add_node("revise_router", revise_router_node)
    builder.add_node("human_review", human_review_stub)
    builder.add_edge(START, "coder")
    builder.add_edge("coder", "reviewer")
    builder.add_edge("reviewer", "revise_router")
    builder.add_conditional_edges(
        "revise_router",
        route_after_revise,
        {"coder": "coder", "researcher": "coder", "analyst": "coder", "planner": "coder", "human_review": "human_review"},
    )
    builder.add_edge("human_review", END)
    graph = builder.compile()

    final_state = graph.invoke(make_initial_state(max_revisions=3), config={"recursion_limit": 50})

    assert final_state["revision_count"] == 0
    assert final_state["review_history"] == [
        {"approved": True, "feedback": "looks great", "target_artifact_id": "code_solution"}
    ]


def test_revise_router_routes_back_to_originating_agent_by_artifact_author():
    state = make_initial_state(max_revisions=3)
    state["artifacts"] = [
        Artifact(id="research_note", kind="research_note", content="notes", author="researcher", version=1)
    ]
    state["review_history"] = [
        ReviewVerdict(approved=False, feedback="dig deeper", target_artifact_id="research_note")
    ]

    update = revise_router_node(state)

    assert update["next_agent"] == "researcher"
    assert update["revision_count"] == 1
