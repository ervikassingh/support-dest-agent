"""Minimal LangSmith-oriented eval runner for routing + write safety."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from agent.evals_safety import load_dataset, run_safety_evals  # noqa: E402


async def main() -> int:
    result = await run_safety_evals()
    for row in result["cases"]:
        mark = "PASS" if row["ok"] else "FAIL"
        print(f"{mark}  {row['id']}  ({row['tag']})  {row.get('got')}")

    summary = result["summary"]
    print(f"\n{summary['passed']}/{summary['total']} passed")

    # Optional LangSmith experiment upload
    try:
        from langsmith import Client

        client = Client()
        ds_name = "support-agent-v1"
        dataset_id = None
        for ds in client.list_datasets(dataset_name=ds_name):
            dataset_id = ds.id
            break
        if dataset_id is None:
            ds = client.create_dataset(dataset_name=ds_name, description="Minimal v1 evals")
            dataset_id = ds.id
            for case in load_dataset():
                client.create_example(
                    inputs=case["input"],
                    outputs=case["expected"],
                    dataset_id=dataset_id,
                    metadata={"tag": case["tag"], "id": case["id"]},
                )
        print(f"LangSmith dataset ready: {ds_name} ({dataset_id})")
    except Exception as exc:  # noqa: BLE001
        print(f"LangSmith upload skipped: {exc}")

    return 0 if summary["passed"] == summary["total"] else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
