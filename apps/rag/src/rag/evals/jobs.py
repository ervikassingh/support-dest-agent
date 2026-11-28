"""Background eval runs persisted in the shared eval_runs table."""

from __future__ import annotations

import asyncio
import logging
import uuid
from typing import Any

from psycopg.types.json import Jsonb

from rag.db import connection

logger = logging.getLogger(__name__)

SUITE = "rag"

_TABLE = """
CREATE TABLE IF NOT EXISTS eval_runs (
    id uuid PRIMARY KEY,
    suite text NOT NULL,
    status text NOT NULL,
    params jsonb NOT NULL DEFAULT '{}',
    done int NOT NULL DEFAULT 0,
    total int NOT NULL DEFAULT 0,
    summary jsonb,
    result jsonb,
    error text,
    started_at timestamptz NOT NULL DEFAULT now(),
    finished_at timestamptz
)
"""

_COLUMNS = "id, suite, status, params, done, total, summary, error, started_at, finished_at"

_tasks: set[asyncio.Task] = set()


class RunInProgress(Exception):
    pass


async def ensure_table() -> None:
    async with connection() as conn:
        await conn.execute(_TABLE)
        await conn.execute(
            "CREATE INDEX IF NOT EXISTS eval_runs_suite_started_idx ON eval_runs (suite, started_at DESC)"
        )
        await conn.execute(
            "UPDATE eval_runs SET status = 'failed', error = 'Interrupted: the service restarted', "
            "finished_at = now() WHERE suite = %s AND status = 'running'",
            (SUITE,),
        )
        await conn.commit()


def _view(row: dict[str, Any] | None) -> dict[str, Any] | None:
    if row is None:
        return None
    out = dict(row)
    out["id"] = str(out["id"])
    for key in ("started_at", "finished_at"):
        if out.get(key) is not None:
            out[key] = out[key].isoformat()
    return out


async def list_runs(limit: int = 20) -> list[dict[str, Any]]:
    async with connection() as conn:
        cur = await conn.execute(
            f"SELECT {_COLUMNS} FROM eval_runs WHERE suite = %s ORDER BY started_at DESC LIMIT %s",
            (SUITE, limit),
        )
        return [_view(row) for row in await cur.fetchall()]


async def get_run(run_id: str) -> dict[str, Any] | None:
    async with connection() as conn:
        cur = await conn.execute(
            f"SELECT {_COLUMNS}, result FROM eval_runs WHERE id = %s AND suite = %s",
            (run_id, SUITE),
        )
        return _view(await cur.fetchone())


async def start_run(params: dict[str, Any]) -> dict[str, Any]:
    from rag.evals.runner import load_golden, run_rag_evals

    total = len(load_golden())
    if params.get("limit"):
        total = min(total, params["limit"])
    run_id = str(uuid.uuid4())
    async with connection() as conn:
        cur = await conn.execute(
            "SELECT 1 FROM eval_runs WHERE suite = %s AND status = 'running' LIMIT 1", (SUITE,)
        )
        if await cur.fetchone():
            raise RunInProgress("A RAG eval run is already in progress")
        await conn.execute(
            "INSERT INTO eval_runs (id, suite, status, params, total) VALUES (%s, %s, 'running', %s, %s)",
            (run_id, SUITE, Jsonb(params), total),
        )
        await conn.commit()

    async def progress(done: int) -> None:
        async with connection() as conn:
            await conn.execute("UPDATE eval_runs SET done = %s WHERE id = %s", (done, run_id))
            await conn.commit()

    async def work() -> None:
        try:
            result = await run_rag_evals(**params, on_progress=progress)
            async with connection() as conn:
                await conn.execute(
                    "UPDATE eval_runs SET status = 'done', done = total, summary = %s, result = %s, "
                    "finished_at = now() WHERE id = %s",
                    (Jsonb(result["summary"]), Jsonb(result), run_id),
                )
                await conn.commit()
        except Exception as exc:  # noqa: BLE001
            logger.exception("RAG eval run %s failed", run_id)
            async with connection() as conn:
                await conn.execute(
                    "UPDATE eval_runs SET status = 'failed', error = %s, finished_at = now() WHERE id = %s",
                    (str(exc) or type(exc).__name__, run_id),
                )
                await conn.commit()

    task = asyncio.create_task(work())
    _tasks.add(task)
    task.add_done_callback(_tasks.discard)
    return await get_run(run_id)
