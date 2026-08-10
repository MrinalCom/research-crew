"""LangSmith tracing toggle.

`langchain-core` reads tracing config straight from `os.environ`, not from our
`Settings` object — pydantic-settings loads `.env` into `Settings` but doesn't
push those values back into the process environment. This bridges the two so
setting `LANGCHAIN_TRACING_V2=true` in `.env` actually turns tracing on.
"""

from __future__ import annotations

import os

from app.config import Settings


def configure_tracing(settings: Settings) -> None:
    os.environ["LANGCHAIN_TRACING_V2"] = "true" if settings.langchain_tracing_v2 else "false"
    if settings.langchain_api_key:
        os.environ["LANGCHAIN_API_KEY"] = settings.langchain_api_key
    os.environ["LANGCHAIN_PROJECT"] = settings.langchain_project
