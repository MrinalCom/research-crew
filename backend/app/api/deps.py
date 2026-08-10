from __future__ import annotations

from fastapi import Header, HTTPException, Request, status

from app.config import Settings, get_settings


def get_graph(request: Request):
    return request.app.state.graph


def get_runs_store(request: Request):
    return request.app.state.runs_store


async def require_api_key(x_api_key: str | None = Header(default=None)) -> None:
    settings: Settings = get_settings()
    if x_api_key != settings.api_dev_key:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid or missing X-API-Key")
