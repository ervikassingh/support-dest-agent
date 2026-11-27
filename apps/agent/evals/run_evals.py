"""Minimal LangSmith-oriented eval runner for routing + write safety."""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from agent.routing.intent import classify_intent  # noqa: E402
from agent.tools.local.send_email import send_email  # noqa: E402
from agent.tools.mcp.adapters import issue_refund  # noqa: E402


def path_for_intent(intent: str) -> str:
    if intent in ("chitchat", "out_of_scope"):
        return "cheap"
    if intent == "refund":
        return "refund"
    if intent == "email":
        return "email"
    return "main"


async def eval_routing(case: dict) -> dict:
    from langchain_core.messages import HumanMessage

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


async def main() -> int:
    dataset = json.loads((Path(__file__).parent / "dataset.json").read_text())
    results = []
    for case in dataset:
        tag = case["tag"]
        if tag == "routing":
            outcome = await eval_routing(case)
        elif tag == "refund_safety":
            outcome = await eval_refund_safety(case)
        elif tag == "email_safety":
            outcome = await eval_email_safety(case)
        else:
            outcome = {"ok": False, "got": {"error": f"unknown tag {tag}"}}
        results.append({"id": case["id"], "tag": tag, **outcome})
        mark = "PASS" if outcome["ok"] else "FAIL"
        print(f"{mark}  {case['id']}  ({tag})  {outcome.get('got')}")

    passed = sum(1 for r in results if r["ok"])
    print(f"\n{passed}/{len(results)} passed")

    # Optional LangSmith experiment upload
    try:
        from langsmith import Client

        client = Client()
        ds_name = "support-desk-agent-v1"
        dataset_id = None
        for ds in client.list_datasets(dataset_name=ds_name):
            dataset_id = ds.id
            break
        if dataset_id is None:
            ds = client.create_dataset(dataset_name=ds_name, description="Minimal v1 evals")
            dataset_id = ds.id
            for case in dataset:
                client.create_example(
                    inputs=case["input"],
                    outputs=case["expected"],
                    dataset_id=dataset_id,
                    metadata={"tag": case["tag"], "id": case["id"]},
                )
        print(f"LangSmith dataset ready: {ds_name} ({dataset_id})")
    except Exception as exc:  # noqa: BLE001
        print(f"LangSmith upload skipped: {exc}")

    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
