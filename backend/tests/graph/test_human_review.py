from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command

from app.graph.human_review import finalize_node, human_review_node
from app.graph.routing import route_after_human_review
from app.graph.state import Artifact, ReviewVerdict, SupervisorState


def make_initial_state() -> SupervisorState:
    return SupervisorState(
        run_id="hitl-test-run",
        messages=[],
        task="write a hello world script",
        plan=None,
        artifacts=[
            Artifact(id="code_solution", kind="code_file", content="print('hello')", author="coder", version=1)
        ],
        review_history=[ReviewVerdict(approved=True, feedback="looks good", target_artifact_id="code_solution")],
        revision_count=0,
        max_revisions=3,
        next_agent="human_review",
        pending_approval=None,
        human_decision=None,
        human_edit_content=None,
    )


def _build_graph():
    supervisor_reached = {"value": False}

    def supervisor_stub(state: SupervisorState) -> dict:
        supervisor_reached["value"] = True
        return {"messages": []}

    builder = StateGraph(SupervisorState)
    builder.add_node("human_review", human_review_node)
    builder.add_node("finalize", finalize_node)
    builder.add_node("supervisor", supervisor_stub)
    builder.add_edge(START, "human_review")
    builder.add_conditional_edges("human_review", route_after_human_review, {"finalize": "finalize", "supervisor": "supervisor"})
    builder.add_edge("finalize", END)
    builder.add_edge("supervisor", END)

    graph = builder.compile(checkpointer=MemorySaver())
    return graph, supervisor_reached


def test_human_review_pauses_and_exposes_approval_payload():
    graph, _ = _build_graph()
    config = {"configurable": {"thread_id": "approve-thread"}}

    result = graph.invoke(make_initial_state(), config)

    assert "__interrupt__" in result
    interrupt_payload = result["__interrupt__"][0].value
    assert interrupt_payload["artifact"]["id"] == "code_solution"
    assert interrupt_payload["revision_count"] == 0

    snapshot = graph.get_state(config)
    assert snapshot.next == ("human_review",)


def test_approve_resumes_and_finalizes_with_original_content():
    graph, _ = _build_graph()
    config = {"configurable": {"thread_id": "approve-thread-2"}}

    graph.invoke(make_initial_state(), config)
    final_state = graph.invoke(Command(resume={"decision": "approve"}), config)

    final_artifacts = [a for a in final_state["artifacts"] if a["kind"] == "final_report"]
    assert len(final_artifacts) == 1
    assert final_artifacts[0]["content"] == "print('hello')"
    assert final_artifacts[0]["author"] == "system"
    assert final_state["next_agent"] == "done"


def test_edit_resumes_and_finalizes_with_human_edited_content():
    graph, _ = _build_graph()
    config = {"configurable": {"thread_id": "edit-thread"}}

    graph.invoke(make_initial_state(), config)
    final_state = graph.invoke(
        Command(resume={"decision": "edit", "edited_content": "print('hello, edited')"}), config
    )

    final_artifacts = [a for a in final_state["artifacts"] if a["kind"] == "final_report"]
    assert final_artifacts[0]["content"] == "print('hello, edited')"
    assert final_artifacts[0]["author"] == "human"


def test_reject_routes_back_to_supervisor_not_finalize():
    graph, supervisor_reached = _build_graph()
    config = {"configurable": {"thread_id": "reject-thread"}}

    graph.invoke(make_initial_state(), config)
    final_state = graph.invoke(Command(resume={"decision": "reject"}), config)

    assert supervisor_reached["value"] is True
    assert not any(a["kind"] == "final_report" for a in final_state["artifacts"])
