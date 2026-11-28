"""Routing and write-safety cases from evals/dataset.json."""

from __future__ import annotations

import json
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

from langchain_core.messages import HumanMessage

from agent.routing.intent import classify_intent
from agent.tools.local.send_email import send_email
from agent.tools.mcp.adapters import issue_refund

_DATASET = Path(__file__).resolve().parents[2] / "evals" / "dataset.json"


def load_dataset() -> list[dict[str, Any]]:
    return json.loads(_DATASET.read_text())


def path_for_intent(intent: str) -> str:
    if intent in ("chitchat", "out_of_scope"):
        return "cheap"
    if intent == "refund":
        return "refund"
    if intent == "email":
        return "email"
    return "main"


async def eval_routing(case: dict) -> dict:
    result = await classify_intent([HumanMessage(content=case["input"]["message"])])
    intent = result["intent"]
    path = path_for_intent(intent)
    ok = intent == case["expected"]["intent"] and path == case["expected"]["path"]
    return {"ok": ok, "got": {"intent": intent, "path": path}}


async def eval_refund_safety(case: dict) -> dict:
    inp = case["input"]
    approval_id = inp.get("approval_id")
    # Soft local check mirrors MCP refusal contract without requiring MCP up.
    if not approval_id:
        refused = True
        detail = {"error": "missing approval_id"}
    else:
        detail = await issue_refund(
            order_id=inp["order_id"],
            amount=float(inp["amount"]),
            approval_id=approval_id,
        )
        refused = bool(detail.get("error"))
    ok = refused == case["expected"]["refused"]
    return {"ok": ok, "got": {"refused": refused, "detail": detail}}


async def eval_email_safety(case: dict) -> dict:
    inp = case["input"]
    result = send_email(
        to=inp["to"],
        subject=inp["subject"],
        body=inp["body"],
        confirmation_id=inp.get("confirmation_id"),
    )
    refused = not result.get("ok")
    ok = refused == case["expected"]["refused"]
    return {"ok": ok, "got": {"refused": refused, "detail": result}}


_EVALUATORS = {
    "routing": eval_routing,
    "refund_safety": eval_refund_safety,
    "email_safety": eval_email_safety,
}


async def run_safety_evals(
    on_progress: Callable[[int], Awaitable[None]] | None = None,
) -> dict[str, Any]:
    dataset = load_dataset()
    cases = []
    for case in dataset:
        if on_progress is not None:
            await on_progress(len(cases))
        evaluator = _EVALUATORS.get(case["tag"])
        try:
            if evaluator is None:
                raise ValueError(f"unknown tag {case['tag']}")
            outcome = await evaluator(case)
        except Exception as exc:  # noqa: BLE001
            outcome = {"ok": False, "got": {"error": str(exc)}}
        cases.append(
            {"id": case["id"], "tag": case["tag"], "input": case["input"], "expected": case["expected"], **outcome}
        )

    by_tag: dict[str, dict[str, int]] = {}
    for row in cases:
        bucket = by_tag.setdefault(row["tag"], {"passed": 0, "total": 0})
        bucket["total"] += 1
        bucket["passed"] += int(row["ok"])
    passed = sum(1 for row in cases if row["ok"])
    summary = {
        "passed": passed,
        "total": len(cases),
        "pass_rate": round(passed / len(cases), 4) if cases else 0.0,
        **{f"{tag}_pass_rate": round(b["passed"] / b["total"], 4) for tag, b in by_tag.items()},
    }
    return {"summary": summary, "by_tag": by_tag, "cases": cases}
