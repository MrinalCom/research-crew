"""Thin run metadata store: run_id -> task/status/timestamps.

Exists because the checkpointer answers "what's the state of thread X" well
but has no good API for "list every run, newest first, with its status" — a
plain small table serves that UX-facing query far more simply than trying to
scan checkpoint storage for it.

Two backends behind one interface, selected the same way as the checkpointer
(`Settings.uses_postgres`): Postgres via asyncpg in Docker Compose, SQLite via
the stdlib (off the event loop via `asyncio.to_thread`) for zero-infra local
dev.
"""

from __future__ import annotations

import asyncio
import sqlite3
import uuid
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import AsyncIterator, Protocol

from app.config import Settings, get_settings

RunStatus = str  # "running" | "paused" | "completed" | "failed"


@dataclass
class RunRecord:
    run_id: str
    task: str
    status: RunStatus
    max_revisions: int
    created_at: str
    updated_at: str


class RunsStore(Protocol):
    async def create(self, task: str, max_revisions: int) -> RunRecord: ...
    async def update_status(self, run_id: str, status: RunStatus) -> None: ...
    async def get(self, run_id: str) -> RunRecord | None: ...
    async def list(self) -> list[RunRecord]: ...


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class SqliteRunsStore:
    def __init__(self, db_path: Path):
        self._db_path = db_path
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS runs (
                    run_id TEXT PRIMARY KEY,
                    task TEXT NOT NULL,
                    status TEXT NOT NULL,
                    max_revisions INTEGER NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )

    def _create_sync(self, run_id: str, task: str, max_revisions: int) -> RunRecord:
        now = _now()
        record = RunRecord(run_id, task, "running", max_revisions, now, now)
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO runs (run_id, task, status, max_revisions, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
                (record.run_id, record.task, record.status, record.max_revisions, record.created_at, record.updated_at),
            )
        return record

    def _update_status_sync(self, run_id: str, status: RunStatus) -> None:
        with self._connect() as conn:
            conn.execute("UPDATE runs SET status = ?, updated_at = ? WHERE run_id = ?", (status, _now(), run_id))

    def _get_sync(self, run_id: str) -> RunRecord | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM runs WHERE run_id = ?", (run_id,)).fetchone()
        return RunRecord(**dict(row)) if row else None

    def _list_sync(self) -> list[RunRecord]:
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM runs ORDER BY created_at DESC").fetchall()
        return [RunRecord(**dict(row)) for row in rows]

    async def create(self, task: str, max_revisions: int) -> RunRecord:
        run_id = str(uuid.uuid4())
        return await asyncio.to_thread(self._create_sync, run_id, task, max_revisions)

    async def update_status(self, run_id: str, status: RunStatus) -> None:
        await asyncio.to_thread(self._update_status_sync, run_id, status)

    async def get(self, run_id: str) -> RunRecord | None:
        return await asyncio.to_thread(self._get_sync, run_id)

    async def list(self) -> list[RunRecord]:
        return await asyncio.to_thread(self._list_sync)


class PostgresRunsStore:
    def __init__(self, pool):
        self._pool = pool

    @classmethod
    async def create_pool(cls, database_url: str) -> "PostgresRunsStore":
        import asyncpg

        pool = await asyncpg.create_pool(database_url)
        store = cls(pool)
        async with pool.acquire() as conn:
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS runs (
                    run_id TEXT PRIMARY KEY,
                    task TEXT NOT NULL,
                    status TEXT NOT NULL,
                    max_revisions INTEGER NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
        return store

    async def close(self) -> None:
        await self._pool.close()

    async def create(self, task: str, max_revisions: int) -> RunRecord:
        run_id = str(uuid.uuid4())
        now = _now()
        record = RunRecord(run_id, task, "running", max_revisions, now, now)
        async with self._pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO runs (run_id, task, status, max_revisions, created_at, updated_at) VALUES ($1, $2, $3, $4, $5, $6)",
                record.run_id, record.task, record.status, record.max_revisions, record.created_at, record.updated_at,
            )
        return record

    async def update_status(self, run_id: str, status: RunStatus) -> None:
        async with self._pool.acquire() as conn:
            await conn.execute("UPDATE runs SET status = $1, updated_at = $2 WHERE run_id = $3", status, _now(), run_id)

    async def get(self, run_id: str) -> RunRecord | None:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow("SELECT * FROM runs WHERE run_id = $1", run_id)
        return RunRecord(**dict(row)) if row else None

    async def list(self) -> list[RunRecord]:
        async with self._pool.acquire() as conn:
            rows = await conn.fetch("SELECT * FROM runs ORDER BY created_at DESC")
        return [RunRecord(**dict(row)) for row in rows]


@asynccontextmanager
async def build_runs_store(settings: Settings | None = None) -> AsyncIterator[RunsStore]:
    settings = settings or get_settings()

    if settings.uses_postgres:
        store = await PostgresRunsStore.create_pool(settings.database_url)
        try:
            yield store
        finally:
            await store.close()
    else:
        sqlite_path = settings.database_url.removeprefix("sqlite:///") or "./research_crew.sqlite3"
        yield SqliteRunsStore(Path(sqlite_path).with_name(Path(sqlite_path).stem + "_runs.sqlite3"))
