from app.graph.state import Artifact, merge_artifacts


def make_artifact(id: str, content: str, version: int = 1) -> Artifact:
    return Artifact(id=id, kind="research_note", content=content, author="researcher", version=version)


def test_merge_artifacts_appends_new_ids():
    existing = [make_artifact("a1", "first")]
    updates = [make_artifact("a2", "second")]

    result = merge_artifacts(existing, updates)

    ids = {a["id"] for a in result}
    assert ids == {"a1", "a2"}


def test_merge_artifacts_replaces_and_bumps_version_on_same_id():
    existing = [make_artifact("a1", "draft one", version=1)]
    updates = [make_artifact("a1", "draft two", version=1)]

    result = merge_artifacts(existing, updates)

    assert len(result) == 1
    assert result[0]["content"] == "draft two"
    assert result[0]["version"] == 2


def test_merge_artifacts_handles_concurrent_fanout_writes():
    # researcher and analyst branches both append distinct ids in the same update
    existing: list[Artifact] = []
    updates = [make_artifact("research_note", "notes"), make_artifact("analysis", "analysis")]

    result = merge_artifacts(existing, updates)

    assert {a["id"] for a in result} == {"research_note", "analysis"}
    assert all(a["version"] == 1 for a in result)


def test_merge_artifacts_empty_existing_and_empty_updates():
    assert merge_artifacts([], []) == []
