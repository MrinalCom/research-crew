from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import runs as runs_api
from app.config import get_settings
from app.graph.build import build_graph
from app.observability.logging import configure_logging
from app.observability.tracing import configure_tracing
from app.persistence.checkpointer import build_checkpointer
from app.persistence.runs_store import build_runs_store


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    configure_logging(settings)
    configure_tracing(settings)

    async with build_checkpointer(settings) as checkpointer, build_runs_store(settings) as runs_store:
        app.state.graph = build_graph(checkpointer=checkpointer, workspace_root=settings.workspaces_dir)
        app.state.runs_store = runs_store
        app.state.settings = settings
        yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="Research Crew API", version="0.1.0", lifespan=lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(runs_api.router, prefix="/runs", tags=["runs"])

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
