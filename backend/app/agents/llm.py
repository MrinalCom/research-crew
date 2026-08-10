"""Provider-agnostic chat model factory — swap providers via config, not code."""

from __future__ import annotations

from functools import lru_cache

from langchain_core.language_models import BaseChatModel

from app.config import Settings, get_settings


def build_chat_model(settings: Settings | None = None, *, temperature: float = 0.0) -> BaseChatModel:
    settings = settings or get_settings()

    if settings.llm_provider == "anthropic":
        from langchain_anthropic import ChatAnthropic

        return ChatAnthropic(
            model=settings.llm_model,
            api_key=settings.anthropic_api_key,
            temperature=temperature,
        )

    if settings.llm_provider == "openai":
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(
            model=settings.llm_model,
            api_key=settings.openai_api_key,
            temperature=temperature,
        )

    raise ValueError(f"unsupported LLM_PROVIDER: {settings.llm_provider!r}")


@lru_cache
def get_default_chat_model() -> BaseChatModel:
    return build_chat_model()
