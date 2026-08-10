"""Web search tool for the researcher/analyst agents.

Degrades gracefully rather than failing hard when no `TAVILY_API_KEY` is
configured — returns a stub tool that tells the agent (and, transitively, the
human reading its output) that search was unavailable, instead of crashing the
whole run over a missing optional key.
"""

from __future__ import annotations

from langchain_core.tools import tool

from app.config import Settings, get_settings


def make_web_search_tool(settings: Settings | None = None):
    settings = settings or get_settings()

    if not settings.tavily_api_key:

        @tool
        def web_search(query: str) -> str:
            """Search the web for `query`. (No TAVILY_API_KEY configured — returns a stub notice.)"""
            return f"[web search unavailable: no TAVILY_API_KEY configured; reason about '{query}' from general knowledge instead]"

        return web_search

    from langchain_tavily import TavilySearch

    return TavilySearch(max_results=5, tavily_api_key=settings.tavily_api_key)
