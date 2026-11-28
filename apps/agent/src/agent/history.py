"""Chat transcripts and refund approvals, so the web app can list and reopen them.

The LangGraph checkpoint stays the source of truth for graph state. These tables
record what the user and the operator actually saw.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any

from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from psycopg_pool import AsyncConnectionPool

from agent.settings import settings

logger = logging.getLogger(__name__)

_SCHEMA = (
    """
    CREATE TABLE IF NOT EXISTS chat_threads (
        id text PRIMARY KEY,
        title text NOT NULL,
        status text NOT NULL DEFAULT 'active',
        created_at timestamptz NOT NULL DEFAULT now(),
        updated_at timestamptz NOT NULL DEFAULT now()
    )
    """,
    "CREATE INDEX IF NOT EXISTS chat_threads_updated_idx ON chat_threads (updated_at DESC)",
    """
    CREATE TABLE IF NOT EXISTS chat_messages (
        id bigserial PRIMARY KEY,
        thread_id text NOT NULL REFERENCES chat_threads (id) ON DELETE CASCADE,
        role text NOT NULL,
        content text NOT NULL,
        created_at timestamptz NOT NULL DEFAULT now()
    )
    """,
    "CREATE INDEX IF NOT EXISTS chat_messages_thread_idx ON chat_messages (thread_id, id)",
    """
    CREATE TABLE IF NOT EXISTS refund_approvals (
        id uuid PRIMARY KEY,
        thread_id text NOT NULL REFERENCES chat_threads (id) ON DELETE CASCADE,
        status text NOT NULL DEFAULT 'pending',
        order_id text,
        customer_id text,
        amount numeric(12, 2),
        draft jsonb NOT NULL DEFAULT '{}',
        decision text,
        final_amount numeric(12, 2),
        note text,
        result_message text,
        requested_at timestamptz NOT NULL DEFAULT now(),
        decided_at timestamptz
    )
    """,
    "CREATE INDEX IF NOT EXISTS refund_approvals_requested_idx ON refund_approvals (requested_at DESC)",
    "CREATE UNIQUE INDEX IF NOT EXISTS refund_approvals_one_pending "
    "ON refund_approvals (thread_id) WHERE status = 'pending'",
)

_APPROVAL_COLUMNS = (
    "a.id, a.thread_id, a.status, a.order_id, a.customer_id, a.amount, a.draft, a.decision, "
    "a.final_amount, a.note, a.result_message, a.requested_at, a.decided_at"
)

_pool: AsyncConnectionPool | None = None


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
        for statement in _SCHEMA:
            await conn.execute(statement)


async def stop() -> None:
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None


def ready() -> bool:
    return _pool is not None


def _view(row: dict[str, Any] | None) -> dict[str, Any] | None:
    if row is None:
        return None
    out = dict(row)
    for key, value in out.items():
        if isinstance(value, uuid.UUID):
            out[key] = str(value)
        elif hasattr(value, "isoformat"):
            out[key] = value.isoformat()
        elif key in ("amount", "final_amount") and value is not None:
            out[key] = float(value)
    return out


def _title(text: str) -> str:
    line = " ".join(text.split())
    return line if len(line) <= 80 else f"{line[:77]}…"


async def record_turn(
    thread_id: str,
    user_text: str,
    reply: str,
    status: str,
    interrupt: dict[str, Any] | None,
) -> None:
    """Save one chat turn. Never raises: history must not break the chat."""
    if _pool is None:
        return
    kind = (interrupt or {}).get("type")
    thread_status = {"refund_approval": "awaiting_approval", "email_confirm": "awaiting_email"}.get(
        kind, "active"
    ) if status == "interrupted" else "active"
    try:
        async with _pool.connection() as conn, conn.transaction():
            await conn.execute(
                "INSERT INTO chat_threads (id, title, status) VALUES (%s, %s, %s) "
                "ON CONFLICT (id) DO UPDATE SET status = EXCLUDED.status, updated_at = now()",
                (thread_id, _title(user_text), thread_status),
            )
            await conn.execute(
                "INSERT INTO chat_messages (thread_id, role, content) VALUES (%s, 'user', %s), (%s, 'assistant', %s)",
                (thread_id, user_text, thread_id, reply),
            )
            if kind == "refund_approval":
                draft = (interrupt or {}).get("draft") or {}
                await conn.execute(
                    "INSERT INTO refund_approvals (id, thread_id, order_id, customer_id, amount, draft) "
                    "VALUES (%s, %s, %s, %s, %s, %s) "
                    "ON CONFLICT (thread_id) WHERE status = 'pending' DO NOTHING",
                    (
                        uuid.uuid4(),
                        thread_id,
                        draft.get("order_id"),
                        draft.get("customer_id") or None,
                        draft.get("amount"),
                        Jsonb(draft),
                    ),
                )
    except Exception:  # noqa: BLE001
        logger.exception("Could not record chat turn for %s", thread_id)


async def record_decision(
    thread_id: str,
    decision: str,
    amount: float | None,
    note: str | None,
    outcome: str,
    message: str,
) -> None:
    """Close the pending approval and add the result to the transcript. Never raises."""
    if _pool is None:
        return
    try:
        async with _pool.connection() as conn, conn.transaction():
            await conn.execute(
                "UPDATE refund_approvals SET status = %s, decision = %s, "
                "final_amount = CASE WHEN %s = 'reject' THEN NULL ELSE COALESCE(%s, amount) END, "
                "note = %s, result_message = %s, decided_at = now() "
                "WHERE thread_id = %s AND status = 'pending'",
                (outcome, decision, decision, amount if decision == "edit" else None, note, message, thread_id),
            )
            await conn.execute(
                "INSERT INTO chat_messages (thread_id, role, content) "
                "SELECT %s, 'assistant', %s WHERE EXISTS (SELECT 1 FROM chat_threads WHERE id = %s)",
                (thread_id, message, thread_id),
            )
            await conn.execute(
                "UPDATE chat_threads SET status = 'active', updated_at = now() WHERE id = %s",
                (thread_id,),
            )
    except Exception:  # noqa: BLE001
        logger.exception("Could not record approval decision for %s", thread_id)


def _pool_or_raise() -> AsyncConnectionPool:
    if _pool is None:
        raise RuntimeError("Chat history is unavailable (Postgres)")
    return _pool


async def list_threads(limit: int = 50) -> list[dict[str, Any]]:
    async with _pool_or_raise().connection() as conn:
        cur = await conn.execute(
            """
            SELECT t.id, t.title, t.status, t.created_at, t.updated_at,
                   (SELECT count(*) FROM chat_messages m WHERE m.thread_id = t.id) AS message_count,
                   (SELECT a.status FROM refund_approvals a WHERE a.thread_id = t.id
                    ORDER BY a.requested_at DESC LIMIT 1) AS approval_status
            FROM chat_threads t
            ORDER BY t.updated_at DESC
            LIMIT %s
            """,
            (limit,),
        )
        return [_view(row) for row in await cur.fetchall()]


async def get_thread(thread_id: str) -> dict[str, Any] | None:
    async with _pool_or_raise().connection() as conn:
        cur = await conn.execute(
            "SELECT id, title, status, created_at, updated_at FROM chat_threads WHERE id = %s",
            (thread_id,),
        )
        thread = _view(await cur.fetchone())
        if thread is None:
            return None
        cur = await conn.execute(
            "SELECT id, role, content, created_at FROM chat_messages WHERE thread_id = %s ORDER BY id",
            (thread_id,),
        )
        thread["messages"] = [_view(row) for row in await cur.fetchall()]
        cur = await conn.execute(
            f"SELECT {_APPROVAL_COLUMNS} FROM refund_approvals a WHERE a.thread_id = %s "
            "ORDER BY a.requested_at DESC",
            (thread_id,),
        )
        thread["approvals"] = [_view(row) for row in await cur.fetchall()]
        return thread


async def list_approvals(state: str, limit: int = 50) -> list[dict[str, Any]]:
    where = "a.status = 'pending'" if state == "pending" else "a.status <> 'pending'"
    order = "a.requested_at ASC" if state == "pending" else "a.decided_at DESC"
    async with _pool_or_raise().connection() as conn:
        cur = await conn.execute(
            f"SELECT {_APPROVAL_COLUMNS}, t.title AS thread_title FROM refund_approvals a "
            f"JOIN chat_threads t ON t.id = a.thread_id WHERE {where} ORDER BY {order} LIMIT %s",
            (limit,),
        )
        return [_view(row) for row in await cur.fetchall()]
