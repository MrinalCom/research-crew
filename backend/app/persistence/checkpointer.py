"""Checkpointer factory: SQLite for zero-infra local dev, Postgres in Docker Compose.

Both are async savers so a single event loop serves the FastAPI app without
blocking on checkpoint I/O. Selection is driven purely by `DATABASE_URL` — the
rest of the graph code never knows which backend it's talking to.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator

from langgraph.checkpoint.base import BaseCheckpointSaver

from app.config import Settings, get_settings


@asynccontextmanager
async def build_checkpointer(settings: Settings | None = None) -> AsyncIterator[BaseCheckpointSaver]:
    settings = settings or get_settings()

    if settings.uses_postgres:
        from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

        async with AsyncPostgresSaver.from_conn_string(settings.database_url) as saver:
            await saver.setup()
            yield saver
    else:
        from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

        sqlite_path = settings.database_url.removeprefix("sqlite:///") or "./research_crew.sqlite3"
        Path(sqlite_path).parent.mkdir(parents=True, exist_ok=True)
        async with AsyncSqliteSaver.from_conn_string(sqlite_path) as saver:
            yield saver
