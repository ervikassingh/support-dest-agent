"""BullMQ consumer. One job ingests one reserved document."""

from __future__ import annotations

import asyncio
import logging

from rag.ingest import ingest_document, set_status
from rag.settings import get_settings

logger = logging.getLogger(__name__)

_worker = None


async def _process(job, _token) -> None:
    document_id = str(job.data["documentId"])
    attempts = int(getattr(job, "attempts", None) or job.opts.get("attempts", 1))
    made = int(getattr(job, "attemptsMade", 0)) + 1
    try:
        await ingest_document(document_id)
    except Exception as exc:
        final = made >= attempts
        await set_status(
            document_id,
            "failed" if final else "queued",
            f"attempt {made}/{attempts}: {exc}",
        )
        logger.exception("Ingest failed for %s", document_id)
        raise


async def start() -> None:
    global _worker
    from bullmq import Worker

    settings = get_settings()
    _worker = Worker("ingest", _process, {"connection": settings.redis_url})
    logger.info("Ingest worker listening on %s", settings.redis_url)


async def stop() -> None:
    global _worker
    if _worker is not None:
        await _worker.close()
        _worker = None


def run() -> None:
    """Standalone worker process: `poetry run rag-worker`."""

    async def _main() -> None:
        from rag.db import close_pool, ensure_schema

        logging.basicConfig(level=logging.INFO)
        await ensure_schema()
        await start()
        try:
            await asyncio.Event().wait()
        finally:
            await stop()
            await close_pool()

    asyncio.run(_main())
