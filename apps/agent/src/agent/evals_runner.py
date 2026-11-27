"""Tool-call accuracy, pass@k, and pass^k against the live agent graph."""

from __future__ import annotations

import json
import time
import uuid
from pathlib import Path
from typing import Any

from langchain_core.messages import HumanMessage

from agent.evals_metrics import pass_at_k, pass_hat_k
from agent.settings import settings

_TASKS = Path(__file__).resolve().parents[2] / "evals" / "tool_tasks.json"


def load_tasks() -> list[dict[str, Any]]:
    return json.loads(_TASKS.read_text())


def tool_calls_of(state: dict[str, Any]) -> list[dict[str, Any]]:
    calls = []
    for message in state.get("messages") or []:
        for call in getattr(message, "tool_calls", None) or []:
            calls.append({"name": call.get("name"), "args": call.get("args") or {}})
    return calls


def call_matches(calls: list[dict[str, Any]], tool: str, args: dict[str, Any]) -> bool:
    for call in calls:
        if call["name"] != tool:
            continue
        if all(str(call["args"].get(key)) == str(value) for key, value in args.items()):
            return True
    return False


def usage_of(state: dict[str, Any]) -> tuple[int, int]:
    prompt = 0
    completion = 0
    for message in state.get("messages") or []:
        meta = getattr(message, "usage_metadata", None) or {}
        prompt += int(meta.get("input_tokens") or 0)
        completion += int(meta.get("output_tokens") or 0)
    return prompt, completion


def _cost(prompt_tokens: int, completion_tokens: int) -> float | None:
    if settings.chat_input_usd_per_million is None or settings.chat_output_usd_per_million is None:
        return None
    return (
        prompt_tokens * settings.chat_input_usd_per_million
        + completion_tokens * settings.chat_output_usd_per_million
    ) / 1_000_000


async def run_agent_evals(graph, *, n: int = 5, k: int = 5) -> dict[str, Any]:
    if k > n:
        raise ValueError("k cannot be larger than n")
    tasks = load_tasks()
    task_rows = []
    for task in tasks:
        runs = []
        for _ in range(n):
            thread_id = f"eval-{uuid.uuid4().hex[:10]}"
            started = time.perf_counter()
            state = await graph.ainvoke(
                {"messages": [HumanMessage(content=task["message"])]},
                {"configurable": {"thread_id": thread_id}},
            )
            elapsed_ms = round((time.perf_counter() - started) * 1000, 1)
            calls = tool_calls_of(state)
            prompt, completion = usage_of(state)
            runs.append(
                {
                    "ok": call_matches(calls, task["expect_tool"], task.get("expect_args") or {}),
                    "tool_calls": calls,
                    "latency_ms": elapsed_ms,
                    "prompt_tokens": prompt,
                    "completion_tokens": completion,
                }
            )
        correct = sum(1 for run in runs if run["ok"])
        prompt_tokens = sum(run["prompt_tokens"] for run in runs)
        completion_tokens = sum(run["completion_tokens"] for run in runs)
        task_rows.append(
            {
                "id": task["id"],
                "correct": correct,
                "n": n,
                "tool_call_accuracy": correct / n,
                "pass_at_1": pass_at_k(n, correct, 1),
                f"pass_at_{k}": pass_at_k(n, correct, k),
                f"pass_hat_{k}": pass_hat_k(n, correct, k),
                "latency_ms_mean": round(sum(run["latency_ms"] for run in runs) / n, 1),
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "cost_usd": _cost(prompt_tokens, completion_tokens),
                "runs": runs,
            }
        )

    def avg(key: str) -> float:
        return round(sum(row[key] for row in task_rows) / len(task_rows), 4) if task_rows else 0.0

    costs = [row["cost_usd"] for row in task_rows]
    return {
        "n": n,
        "k": k,
        "tool_call_accuracy": avg("tool_call_accuracy"),
        "pass_at_1": avg("pass_at_1"),
        f"pass_at_{k}": avg(f"pass_at_{k}"),
        f"pass_hat_{k}": avg(f"pass_hat_{k}"),
        "latency_ms_mean": round(sum(row["latency_ms_mean"] for row in task_rows) / len(task_rows), 1)
        if task_rows
        else 0,
        "e2e_ms_mean": round(sum(row["latency_ms_mean"] for row in task_rows) / len(task_rows), 1)
        if task_rows
        else 0,
        "prompt_tokens": sum(row["prompt_tokens"] for row in task_rows),
        "completion_tokens": sum(row["completion_tokens"] for row in task_rows),
        "cost_usd": None if any(cost is None for cost in costs) else round(sum(costs), 6),
        "tasks": task_rows,
    }
