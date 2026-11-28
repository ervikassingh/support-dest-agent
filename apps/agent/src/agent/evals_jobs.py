"""Background eval runs persisted in the shared eval_runs table."""

from __future__ import annotations

import asyncio
import logging
import uuid
from collections.abc import Awaitable, Callable
from typing import Any

from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from psycopg_pool import AsyncConnectionPool

from agent.settings import settings

logger = logging.getLogger(__name__)

SUITES = ("agent_tools", "agent_safety")

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

_pool: AsyncConnectionPool | None = None
_tasks: set[asyncio.Task] = set()


class RunInProgress(Exception):
    pass


async def start() -> None:
    global _pool
    _pool = AsyncConnectionPool(
        conninfo=settings.database_url,
        min_size=1,
        max_size=4,
        kwargs={"row_factory": dict_row},
        open=False,
    )
    await _pool.open()
    async with _pool.connection() as conn:
        await conn.execute(_TABLE)
        await conn.execute(
            "CREATE INDEX IF NOT EXISTS eval_runs_suite_started_idx ON eval_runs (suite, started_at DESC)"
        )
        await conn.execute(
            "UPDATE eval_runs SET status = 'failed', error = 'Interrupted: the service restarted', "
            "finished_at = now() WHERE suite = ANY(%s) AND status = 'running'",
            (list(SUITES),),
        )


async def stop() -> None:
    global _pool
    for task in list(_tasks):
        task.cancel()
    if _pool is not None:
        await _pool.close()
        _pool = None


def ready() -> bool:
    return _pool is not None


def _pool_or_raise() -> AsyncConnectionPool:
    if _pool is None:
        raise RuntimeError("Eval storage is unavailable (Postgres)")
    return _pool


def _view(row: dict[str, Any] | None) -> dict[str, Any] | None:
    if row is None:
        return None
    out = dict(row)
    out["id"] = str(out["id"])
    for key in ("started_at", "finished_at"):
        if out.get(key) is not None:
            out[key] = out[key].isoformat()
    return out


async def _execute(query: str, params: tuple) -> None:
    async with _pool_or_raise().connection() as conn:
        await conn.execute(query, params)


async def list_runs(suite: str, limit: int = 20) -> list[dict[str, Any]]:
    async with _pool_or_raise().connection() as conn:
        cur = await conn.execute(
            f"SELECT {_COLUMNS} FROM eval_runs WHERE suite = %s ORDER BY started_at DESC LIMIT %s",
            (suite, limit),
        )
        return [_view(row) for row in await cur.fetchall()]


async def get_run(run_id: str) -> dict[str, Any] | None:
    async with _pool_or_raise().connection() as conn:
        cur = await conn.execute(
            f"SELECT {_COLUMNS}, result FROM eval_runs WHERE id = %s AND suite = ANY(%s)",
            (run_id, list(SUITES)),
        )
        return _view(await cur.fetchone())


async def start_run(
    suite: str,
    params: dict[str, Any],
    total: int,
    job: Callable[[Callable[[int], Awaitable[None]]], Awaitable[dict[str, Any]]],
) -> dict[str, Any]:
    run_id = str(uuid.uuid4())
    async with _pool_or_raise().connection() as conn:
        cur = await conn.execute(
            "SELECT 1 FROM eval_runs WHERE suite = %s AND status = 'running' LIMIT 1", (suite,)
        )
        if await cur.fetchone():
            raise RunInProgress(f"An {suite} eval run is already in progress")
        await conn.execute(
            "INSERT INTO eval_runs (id, suite, status, params, total) VALUES (%s, %s, 'running', %s, %s)",
            (run_id, suite, Jsonb(params), total),
        )

    async def progress(done: int) -> None:
        await _execute("UPDATE eval_runs SET done = %s WHERE id = %s", (done, run_id))

    async def work() -> None:
        try:
            result = await job(progress)
            summary = result.get("summary") or {k: v for k, v in result.items() if k != "tasks"}
            await _execute(
                "UPDATE eval_runs SET status = 'done', done = total, summary = %s, result = %s, "
                "finished_at = now() WHERE id = %s",
                (Jsonb(summary), Jsonb(result), run_id),
            )
        except Exception as exc:  # noqa: BLE001
            logger.exception("Eval run %s (%s) failed", run_id, suite)
            await _execute(
                "UPDATE eval_runs SET status = 'failed', error = %s, finished_at = now() WHERE id = %s",
                (str(exc) or type(exc).__name__, run_id),
            )

    task = asyncio.create_task(work())
    _tasks.add(task)
    task.add_done_callback(_tasks.discard)
    return await get_run(run_id)
