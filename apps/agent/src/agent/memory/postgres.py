"""PostgresSaver + PostgresStore lifecycle helpers."""

from __future__ import annotations

import logging
from contextlib import AsyncExitStack
from typing import Any

from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.store.postgres.aio import AsyncPostgresStore

from agent.settings import settings

logger = logging.getLogger(__name__)

REFUND_NAMESPACE = ("refunds", "operator")


class MemoryBundle:
    """Holds long-lived checkpointer + store for the FastAPI process."""

    def __init__(self) -> None:
        self.checkpointer: AsyncPostgresSaver | None = None
        self.store: AsyncPostgresStore | None = None
        self._stack: AsyncExitStack | None = None
        self.ready: bool = False
        self.error: str | None = None

    async def start(self) -> None:
        self._stack = AsyncExitStack()
        try:
            self.checkpointer = await self._stack.enter_async_context(
                AsyncPostgresSaver.from_conn_string(settings.database_url)
            )
            self.store = await self._stack.enter_async_context(
                AsyncPostgresStore.from_conn_string(settings.database_url)
            )
            await self.checkpointer.setup()
            await self.store.setup()
            self.ready = True
            self.error = None
            logger.info("Postgres checkpointer and store ready")
        except Exception as exc:  # noqa: BLE001
            self.ready = False
            self.error = str(exc)
            logger.exception("Failed to start Postgres memory: %s", exc)
            if self._stack is not None:
                await self._stack.aclose()
                self._stack = None
            self.checkpointer = None
            self.store = None

    async def stop(self) -> None:
        if self._stack is not None:
            await self._stack.aclose()
            self._stack = None
        self.checkpointer = None
        self.store = None
        self.ready = False


async def read_refund_memory(store: AsyncPostgresStore, customer_id: str) -> list[dict[str, Any]]:
    if not customer_id or customer_id == "unknown":
        return []
    item = await store.aget(REFUND_NAMESPACE, customer_id)
    if item is None:
        return []
    value = item.value or {}
    notes = value.get("notes")
    return notes if isinstance(notes, list) else []


async def append_refund_memory(
    store: AsyncPostgresStore,
    customer_id: str,
    note: dict[str, Any],
) -> None:
    if not customer_id or customer_id == "unknown":
        return
    existing = await read_refund_memory(store, customer_id)
    existing.append(note)
    await store.aput(
        REFUND_NAMESPACE,
        customer_id,
        {"notes": existing[-50:]},  # cap growth
    )
