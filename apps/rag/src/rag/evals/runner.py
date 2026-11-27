"""Run the golden set and optionally upload a LangSmith experiment."""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

from rag.answer import answer_events
from rag.evals.judge import judge_relevance, score_answer
from rag.evals.metrics import (
    average_precision_at,
    hit_at,
    mean,
    mrr_at,
    ndcg_at,
    precision_at,
    recall_at,
    relevance_flags,
)
from rag.retrieve import retrieve
from rag.settings import get_settings

_GOLDEN = Path(__file__).resolve().parents[3] / "evals" / "golden.json"


def load_golden() -> list[dict[str, Any]]:
    return json.loads(_GOLDEN.read_text())


def _ranking(flags: list[int], n_relevant: int) -> dict[str, float]:
    return {
        "hit_at_5": hit_at(flags, 5),
        "recall_at_5": recall_at(flags, 5, n_relevant),
        "precision_at_5": precision_at(flags, 5),
        "mrr_at_10": mrr_at(flags, 10),
        "map_at_10": average_precision_at(flags, 10, n_relevant),
        "ndcg_at_10": ndcg_at(flags, 10, n_relevant),
    }


async def _answer_case(question: str) -> dict[str, Any]:
    started = time.perf_counter()
    first_token_at = None
    final: dict[str, Any] = {}
    async for event in answer_events(question):
        if event["type"] == "token" and first_token_at is None:
            first_token_at = time.perf_counter()
        if event["type"] == "done":
            final = event
    finished = time.perf_counter()
    usage = final.get("usage") or {}
    return {
        "answer": final.get("answer"),
        "refused": final.get("refused", False),
        "citations": final.get("citations") or [],
        "ttft_ms": None if first_token_at is None else round((first_token_at - started) * 1000, 1),
        "e2e_ms": round((finished - started) * 1000, 1),
        "usage": usage,
    }


async def run_rag_evals(
    *,
    answer: bool = True,
    judge: bool = True,
    limit: int | None = None,
) -> dict[str, Any]:
    cases = load_golden()
    if limit is not None:
        cases = cases[:limit]
    rows = []
    for case in cases:
        found = await retrieve(case["question"], top_k=10)
        documents = found["documents"]
        labels = case["relevant"]
        flags = relevance_flags(documents, labels, 10)
        source = "labels"
        n_relevant = len(labels)
        if judge and not any(flags) and documents:
            judged = await judge_relevance(case["question"], documents[:5])
            flags = judged + [0] * max(0, 10 - len(judged))
            n_relevant = sum(judged) or len(labels)
            source = "judge"
        row: dict[str, Any] = {
            "id": case["id"],
            "question": case["question"],
            "relevance_source": source,
            "ranking": _ranking(flags, n_relevant),
            "retrieved": [
                {"title": doc.get("title"), "header_path": doc.get("header_path"), "score": doc.get("score")}
                for doc in documents
            ],
        }
        if answer:
            generated = await _answer_case(case["question"])
            row["answer"] = generated["answer"]
            row["refused"] = generated["refused"]
            row["ttft_ms"] = generated["ttft_ms"]
            row["e2e_ms"] = generated["e2e_ms"]
            row["usage"] = generated["usage"]
            if judge and generated["answer"]:
                contexts = [doc.get("embed_text") or doc.get("content") or "" for doc in documents]
                graded = await score_answer(case["question"], generated["answer"], contexts)
                row["quality"] = graded["scores"]
                row["judge_backend"] = graded["backend"]
                if graded["ragas_error"]:
                    row["ragas_error"] = graded["ragas_error"]
        rows.append(row)

    ranking_keys = ("hit_at_5", "recall_at_5", "precision_at_5", "mrr_at_10", "map_at_10", "ndcg_at_10")
    summary: dict[str, Any] = {
        key: round(mean([row["ranking"][key] for row in rows]), 4) for key in ranking_keys
    }
    if answer:
        summary["ttft_ms"] = round(mean([row["ttft_ms"] or 0 for row in rows if row.get("ttft_ms") is not None]), 1) if any(row.get("ttft_ms") is not None for row in rows) else None
        summary["e2e_ms"] = round(mean([row.get("e2e_ms") or 0 for row in rows]), 1)
        summary["prompt_tokens"] = sum(int((row.get("usage") or {}).get("prompt_tokens") or 0) for row in rows)
        summary["completion_tokens"] = sum(int((row.get("usage") or {}).get("completion_tokens") or 0) for row in rows)
        summary["embedding_tokens"] = sum(int((row.get("usage") or {}).get("embedding_tokens") or 0) for row in rows)
        costs = [(row.get("usage") or {}).get("cost_usd") for row in rows]
        summary["cost_usd"] = None if any(cost is None for cost in costs) else round(sum(costs), 6)
        for key in ("faithfulness", "groundedness", "answer_relevance", "context_relevance"):
            values = [row["quality"][key] for row in rows if row.get("quality") and key in row["quality"]]
            summary[key] = round(mean(values), 4) if values else None
    experiment = _langsmith(cases, rows)
    return {"cases": len(rows), "summary": summary, "results": rows, "langsmith": experiment}


def _langsmith(cases: list[dict], rows: list[dict]) -> dict[str, Any]:
    settings = get_settings()
    if not settings.langsmith_api_key:
        return {"uploaded": False, "reason": "LANGSMITH_API_KEY is not set"}
    try:
        os.environ["LANGSMITH_API_KEY"] = settings.langsmith_api_key
        from langsmith import Client

        client = Client()
        name = "support-rag-golden"
        existing = list(client.list_datasets(dataset_name=name))
        dataset = existing[0] if existing else client.create_dataset(dataset_name=name, description="RAG golden set")
        if not existing:
            for case in cases:
                client.create_example(
                    inputs={"question": case["question"]},
                    outputs={"relevant": case["relevant"]},
                    dataset_id=dataset.id,
                    metadata={"id": case["id"]},
                )
        for case, row in zip(cases, rows, strict=False):
            run = client.create_run(
                name=row["id"],
                run_type="chain",
                inputs={"question": case["question"]},
                outputs={"answer": row.get("answer"), "retrieved": row.get("retrieved")},
                project_name=settings.langsmith_project,
            )
            run_id = getattr(run, "id", None)
            if run_id is None:
                continue
            scores = dict(row["ranking"])
            scores.update(row.get("quality") or {})
            for key, value in scores.items():
                if isinstance(value, (int, float)):
                    client.create_feedback(run_id, key=key, score=float(value))
        return {"uploaded": True, "dataset": name, "project": settings.langsmith_project}
    except Exception as exc:  # noqa: BLE001
        return {"uploaded": False, "reason": str(exc)}
