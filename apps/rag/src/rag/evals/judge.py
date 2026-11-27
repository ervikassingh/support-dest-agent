"""Faithfulness, groundedness, and relevance. Ragas first, then one JSON judge for gaps."""

from __future__ import annotations

import json
import logging
from typing import Any

import httpx

from rag.settings import get_settings

logger = logging.getLogger(__name__)

_KEYS = ("faithfulness", "groundedness", "answer_relevance", "context_relevance")

_JUDGE = """You grade a support answer against retrieved context.
Return JSON with keys faithfulness, groundedness, answer_relevance, context_relevance.
Each value is from 0 to 1.
faithfulness: fraction of the answer's claims that the context supports.
groundedness: 1 when the answer adds no facts beyond the context, else lower.
answer_relevance: how well the answer addresses the question.
context_relevance: how useful the context is for the question.
JSON only.

Question: {question}
Answer: {answer}
Context:
{context}
"""


def _clamp(value: Any) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return 0.0
    return max(0.0, min(1.0, number))


async def _json_judge(question: str, answer: str, contexts: list[str]) -> dict[str, float]:
    settings = get_settings()
    if not settings.openrouter_api_key:
        raise RuntimeError("OPENROUTER_API_KEY is not set")
    url = f"{settings.openrouter_base_url.rstrip('/')}/chat/completions"
    payload = {
        "model": settings.judge_model,
        "temperature": 0,
        "messages": [
            {
                "role": "user",
                "content": _JUDGE.format(
                    question=question,
                    answer=answer,
                    context="\n\n".join(contexts) or "(empty)",
                ),
            }
        ],
    }
    async with httpx.AsyncClient(timeout=90.0) as client:
        response = await client.post(
            url,
            headers={"Authorization": f"Bearer {settings.openrouter_api_key}"},
            json=payload,
        )
    response.raise_for_status()
    content = response.json()["choices"][0]["message"]["content"]
    start = content.find("{")
    end = content.rfind("}")
    parsed = json.loads(content[start : end + 1])
    return {key: _clamp(parsed.get(key)) for key in _KEYS}


async def _ragas_scores(question: str, answer: str, contexts: list[str]) -> dict[str, float]:
    """Ragas collections metrics. OpenRouter is an OpenAI-compatible client."""
    from openai import AsyncOpenAI
    from ragas.embeddings import OpenAIEmbeddings
    from ragas.llms import llm_factory
    from ragas.metrics.collections import (
        AnswerRelevancy,
        ContextRelevance,
        Faithfulness,
        ResponseGroundedness,
    )

    settings = get_settings()
    client = AsyncOpenAI(
        api_key=settings.openrouter_api_key or "missing",
        base_url=settings.openrouter_base_url,
    )
    llm = llm_factory(settings.judge_model, provider="openai", client=client)
    embeddings = OpenAIEmbeddings(client=client, model=settings.embedding_model)
    faithfulness = await Faithfulness(llm=llm).ascore(
        user_input=question,
        response=answer,
        retrieved_contexts=contexts,
    )
    groundedness = await ResponseGroundedness(llm=llm).ascore(
        response=answer,
        retrieved_contexts=contexts,
    )
    relevance = await AnswerRelevancy(llm=llm, embeddings=embeddings).ascore(
        user_input=question,
        response=answer,
    )
    context = await ContextRelevance(llm=llm).ascore(
        user_input=question,
        retrieved_contexts=contexts,
    )
    return {
        "faithfulness": _clamp(faithfulness.value),
        "groundedness": _clamp(groundedness.value),
        "answer_relevance": _clamp(relevance.value),
        "context_relevance": _clamp(context.value),
    }


async def score_answer(question: str, answer: str, contexts: list[str]) -> dict[str, Any]:
    scores: dict[str, float] = {}
    backends: list[str] = []
    ragas_error = None
    try:
        scores.update(await _ragas_scores(question, answer, contexts))
        backends.append("ragas")
    except Exception as exc:  # noqa: BLE001 - eval should still return a judge score
        ragas_error = str(exc)
        logger.warning("Ragas scoring failed: %s", exc)
    if any(key not in scores for key in _KEYS):
        judged = await _json_judge(question, answer, contexts)
        for key in _KEYS:
            scores.setdefault(key, judged[key])
        backends.append("json")
    return {"scores": scores, "backend": backends, "ragas_error": ragas_error}


async def judge_relevance(question: str, documents: list[dict]) -> list[int]:
    """Return 1/0 per document when labeled relevance missed entirely."""
    if not documents:
        return []
    blocks = []
    for index, document in enumerate(documents, start=1):
        blocks.append(f"[{index}] {document.get('embed_text') or document.get('content')}")
    settings = get_settings()
    url = f"{settings.openrouter_base_url.rstrip('/')}/chat/completions"
    prompt = (
        "Which context blocks contain the answer to the question? "
        'Return JSON {"relevant": [1, 2]} using the block numbers. JSON only.\n\n'
        f"Question: {question}\n\n" + "\n\n".join(blocks)
    )
    async with httpx.AsyncClient(timeout=90.0) as client:
        response = await client.post(
            url,
            headers={"Authorization": f"Bearer {settings.openrouter_api_key or ''}"},
            json={
                "model": settings.judge_model,
                "temperature": 0,
                "messages": [{"role": "user", "content": prompt}],
            },
        )
    response.raise_for_status()
    content = response.json()["choices"][0]["message"]["content"]
    start = content.find("{")
    end = content.rfind("}")
    chosen = set(json.loads(content[start : end + 1]).get("relevant") or [])
    return [1 if index in chosen else 0 for index in range(1, len(documents) + 1)]
