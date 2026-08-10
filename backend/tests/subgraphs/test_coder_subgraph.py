from langchain_core.messages import AIMessage

from app.graph.state import SupervisorState
from app.subgraphs import coder_graph


class _StubAgent:
    def __init__(self, final_message: AIMessage):
        self._final_message = final_message

    async def ainvoke(self, _input):
        return {"messages": [self._final_message]}


def make_state(**overrides) -> SupervisorState:
    base = SupervisorState(
        run_id="test-run",
        messages=[],
        task="write a function that adds two numbers",
        plan="1. write add(a, b)\n2. test it",
        artifacts=[],
        review_history=[],
        revision_count=0,
        max_revisions=3,
        next_agent="coder",
        pending_approval=None,
        human_decision=None,
        human_edit_content=None,
    )
    base.update(overrides)
    return base


async def test_coder_node_reads_solution_file_written_by_agent(tmp_path, monkeypatch):
    state = make_state()
    workspace_dir = tmp_path / state["run_id"]
    workspace_dir.mkdir(parents=True)
    (workspace_dir / coder_graph.SOLUTION_FILENAME).write_text("def add(a, b):\n    return a + b\n")

    stub = _StubAgent(AIMessage(content="Implemented add() and tested it successfully."))
    monkeypatch.setattr(coder_graph, "build_coder_agent", lambda *a, **k: stub)

    update = await coder_graph.coder_node(state, workspace_root=tmp_path)

    assert len(update["artifacts"]) == 1
    artifact = update["artifacts"][0]
    assert artifact["id"] == coder_graph.ARTIFACT_ID
    assert artifact["kind"] == "code_file"
    assert "def add(a, b):" in artifact["content"]
    assert update["messages"][0].content == "Implemented add() and tested it successfully."


async def test_coder_node_falls_back_to_summary_when_no_solution_file(tmp_path, monkeypatch):
    state = make_state()
    stub = _StubAgent(AIMessage(content="I could not produce a working solution."))
    monkeypatch.setattr(coder_graph, "build_coder_agent", lambda *a, **k: stub)

    update = await coder_graph.coder_node(state, workspace_root=tmp_path)

    assert "no solution.py written" in update["artifacts"][0]["content"]


async def test_coder_node_includes_prior_reviewer_feedback_in_brief(tmp_path, monkeypatch):
    state = make_state(
        review_history=[
            {"approved": False, "feedback": "handle negative numbers", "target_artifact_id": "code_solution"}
        ]
    )
    captured_brief = {}

    class CapturingStub(_StubAgent):
        async def ainvoke(self, input_):
            captured_brief["text"] = input_["messages"][0].content
            return await super().ainvoke(input_)

    stub = CapturingStub(AIMessage(content="done"))
    monkeypatch.setattr(coder_graph, "build_coder_agent", lambda *a, **k: stub)

    await coder_graph.coder_node(state, workspace_root=tmp_path)

    assert "handle negative numbers" in captured_brief["text"]


async def test_coder_node_omits_feedback_section_when_last_review_approved(tmp_path, monkeypatch):
    state = make_state(
        review_history=[{"approved": True, "feedback": "looks good", "target_artifact_id": "code_solution"}]
    )
    captured_brief = {}

    class CapturingStub(_StubAgent):
        async def ainvoke(self, input_):
            captured_brief["text"] = input_["messages"][0].content
            return await super().ainvoke(input_)

    stub = CapturingStub(AIMessage(content="done"))
    monkeypatch.setattr(coder_graph, "build_coder_agent", lambda *a, **k: stub)

    await coder_graph.coder_node(state, workspace_root=tmp_path)

    assert "Reviewer feedback" not in captured_brief["text"]
