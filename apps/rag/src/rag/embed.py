"""OpenRouter embeddings. The model id and dimension come from the environment."""

from __future__ import annotations

from typing import Any

import httpx

from rag.settings import get_settings


class EmbeddingError(RuntimeError):
    pass


def _cost_from_tokens(tokens: int) -> float | None:
    rate = get_settings().embedding_usd_per_million
    if rate is None:
        return None
    return tokens * rate / 1_000_000


async def embed_texts(texts: list[str]) -> tuple[list[list[float]], dict[str, Any]]:
    if not texts:
        return [], {"prompt_tokens": 0, "cost_usd": 0.0, "cost_source": "provider"}
    settings = get_settings()
    if not settings.openrouter_api_key:
        raise EmbeddingError("OPENROUTER_API_KEY is not set")

    url = f"{settings.openrouter_base_url.rstrip('/')}/embeddings"
    payload: dict[str, Any] = {"model": settings.embedding_model, "input": texts}
    if settings.embedding_dim:
        payload["dimensions"] = settings.embedding_dim

    async with httpx.AsyncClient(timeout=120.0) as client:
        response = await client.post(
            url,
            headers={"Authorization": f"Bearer {settings.openrouter_api_key}"},
            json=payload,
        )
    if response.status_code >= 400:
        raise EmbeddingError(f"Embedding request failed ({response.status_code}): {response.text[:400]}")

    body = response.json()
    rows = sorted(body.get("data") or [], key=lambda item: item.get("index", 0))
    vectors = [list(item["embedding"]) for item in rows]
    if len(vectors) != len(texts):
        raise EmbeddingError(f"Expected {len(texts)} embeddings, got {len(vectors)}")
    dim = settings.embedding_dim
    for vector in vectors:
        if len(vector) != dim:
            raise EmbeddingError(
                f"Model returned dimension {len(vector)}, EMBEDDING_DIM is {dim}. "
                "Set EMBEDDING_DIM to the vector length the model returns."
            )

    usage = body.get("usage") or {}
    tokens = int(usage.get("prompt_tokens") or usage.get("total_tokens") or 0)
    reported = usage.get("cost")
    if reported is not None:
        cost: float | None = float(reported)
        source = "provider"
    else:
        cost = _cost_from_tokens(tokens)
        source = "env_rates" if cost is not None else None
    return vectors, {"prompt_tokens": tokens, "cost_usd": cost, "cost_source": source}
