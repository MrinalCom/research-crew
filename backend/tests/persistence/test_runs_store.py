from app.persistence.runs_store import SqliteRunsStore


async def test_create_get_list_and_update_status(tmp_path):
    store = SqliteRunsStore(tmp_path / "runs.sqlite3")

    record = await store.create(task="do a thing", max_revisions=3)
    assert record.status == "running"
    assert record.max_revisions == 3

    fetched = await store.get(record.run_id)
    assert fetched == record

    await store.update_status(record.run_id, "paused")
    updated = await store.get(record.run_id)
    assert updated.status == "paused"
    assert updated.updated_at >= record.updated_at

    other = await store.create(task="another thing", max_revisions=2)
    all_runs = await store.list()
    run_ids = {r.run_id for r in all_runs}
    assert run_ids == {record.run_id, other.run_id}
    # newest first
    assert all_runs[0].run_id == other.run_id


async def test_get_missing_run_returns_none(tmp_path):
    store = SqliteRunsStore(tmp_path / "runs.sqlite3")
    assert await store.get("does-not-exist") is None
