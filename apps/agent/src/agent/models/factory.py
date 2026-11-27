"""LLM clients via OpenRouter (OpenAI-compatible). One key, any model slug per agent."""

from __future__ import annotations

from functools import lru_cache

from langchain_openai import ChatOpenAI

from agent.settings import settings


def openrouter_chat(model: str) -> ChatOpenAI:
    """Chat model addressed by an OpenRouter id, e.g. openai/gpt-4o-mini."""
    return ChatOpenAI(
        model=model,
        temperature=0,
        api_key=settings.openrouter_api_key or "missing-openrouter-key",
        base_url=settings.openrouter_base_url,
    )


@lru_cache(maxsize=1)
def get_cheap_model() -> ChatOpenAI:
    return openrouter_chat(settings.cheap_model)


@lru_cache(maxsize=1)
def get_main_model() -> ChatOpenAI:
    return openrouter_chat(settings.main_model)
