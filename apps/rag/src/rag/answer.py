"""Answer a question from retrieved chunks, with a streaming variant for time-to-first-token."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any

import httpx

from rag.retrieve import retrieve
from rag.settings import get_settings

_SYSTEM = """You answer support-policy questions using only the context below.
If the context does not contain the answer, say you don't know. Do not guess.
Cite the context blocks you used as [n].

{context}
"""


def context_block(index: int, document: dict[str, Any]) -> str:
    meta = (
        f"metadata: version={document.get('version')} "
        f"pages={document.get('page_start')}-{document.get('page_end')} "
        f"source={document.get('source_uri') or document.get('title')} "
        f"type={document.get('source_type')}"
    )
    body = document.get("embed_text") or document.get("content") or ""
    return f"[{index}] {body}\n{meta}"


def _rates(prompt_tokens: int, completion_tokens: int) -> tuple[float | None, str | None]:
    settings = get_settings()
    if (
        settings.chat_input_usd_per_million is None
        or settings.chat_output_usd_per_million is None
    ):
        return None, None
    cost = (
        prompt_tokens * settings.chat_input_usd_per_million
        + completion_tokens * settings.chat_output_usd_per_million
    ) / 1_000_000
    return cost, "env_rates"


def _combine_usage(embedding: dict[str, Any], chat: dict[str, Any]) -> dict[str, Any]:
    prompt = int(chat.get("prompt_tokens") or 0)
    completion = int(chat.get("completion_tokens") or 0)
    embed_tokens = int(embedding.get("prompt_tokens") or 0)
    if chat.get("cost_usd") is not None and embedding.get("cost_usd") is not None:
        cost = float(chat["cost_usd"]) + float(embedding["cost_usd"])
        source = "provider"
    else:
        estimated, source = _rates(prompt, completion)
        embed_cost = embedding.get("cost_usd")
        if estimated is not None and embed_cost is not None:
            cost = estimated + float(embed_cost)
        elif estimated is not None and embed_tokens == 0:
            cost = estimated
        else:
            cost = None
            source = None
    return {
        "prompt_tokens": prompt,
        "completion_tokens": completion,
        "embedding_tokens": embed_tokens,
        "cost_usd": cost,
        "cost_source": source,
    }


async def answer_events(question: str, top_k: int = 5) -> AsyncIterator[dict[str, Any]]:
    found = await retrieve(question, top_k=top_k)
    documents = found["documents"]
    citations = found["citations"]
    if not documents:
        yield {
            "type": "done",
            "question": question,
            "answer": "I don't have a policy document that covers that.",
            "citations": [],
            "refused": True,
            "usage": _combine_usage(found.get("usage") or {}, {}),
        }
        return

    context = "\n\n".join(
        context_block(index, document) for index, document in enumerate(documents, start=1)
    )
    settings = get_settings()
    payload = {
        "model": settings.main_model,
        "temperature": 0,
        "stream": True,
        "stream_options": {"include_usage": True},
        "messages": [
            {"role": "system", "content": _SYSTEM.format(context=context)},
            {"role": "user", "content": question},
        ],
    }
    url = f"{settings.openrouter_base_url.rstrip('/')}/chat/completions"
    parts: list[str] = []
    chat_usage: dict[str, Any] = {}
    async with httpx.AsyncClient(timeout=120.0) as client:
        async with client.stream(
            "POST",
            url,
            headers={"Authorization": f"Bearer {settings.openrouter_api_key or ''}"},
            json=payload,
        ) as response:
            if response.status_code >= 400:
                detail = (await response.aread()).decode()[:400]
                raise RuntimeError(f"Answer request failed ({response.status_code}): {detail}")
            async for line in response.aiter_lines():
                if not line.startswith("data:"):
                    continue
                data = line.removeprefix("data:").strip()
                if data == "[DONE]":
                    break
                event = json.loads(data)
                usage = event.get("usage")
                if usage:
                    chat_usage = {
                        "prompt_tokens": usage.get("prompt_tokens") or 0,
                        "completion_tokens": usage.get("completion_tokens") or 0,
                        "cost_usd": usage.get("cost"),
                        "cost_source": "provider" if usage.get("cost") is not None else None,
                    }
                choices = event.get("choices") or []
                if not choices:
                    continue
                delta = (choices[0].get("delta") or {}).get("content") or ""
                if delta:
                    parts.append(delta)
                    yield {"type": "token", "text": delta}

    answer = "".join(parts).strip()
    yield {
        "type": "done",
        "question": question,
        "answer": answer,
        "citations": citations,
        "refused": False,
        "usage": _combine_usage(found.get("usage") or {}, chat_usage),
    }


async def answer(question: str, top_k: int = 5) -> dict[str, Any]:
    final: dict[str, Any] = {}
    async for event in answer_events(question, top_k=top_k):
        if event["type"] == "done":
            final = event
    final.pop("type", None)
    return final
