"""RAG HTTP service: ingest status, hybrid retrieve, answers, and evals."""

from __future__ import annotations

import json
import logging
import os
import uuid
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from rag.settings import get_settings

logger = logging.getLogger(__name__)


def configure_langsmith() -> None:
    """Recreate the tracing project. LangSmith drops it when deleted in the UI."""
    settings = get_settings()
    if not settings.langsmith_api_key:
        logger.info("LangSmith disabled: LANGSMITH_API_KEY is not set")
        return
    os.environ["LANGSMITH_TRACING"] = "true"
    os.environ["LANGSMITH_API_KEY"] = settings.langsmith_api_key
    os.environ["LANGSMITH_PROJECT"] = settings.langsmith_project
    try:
        from langsmith import Client

        Client().create_project(
            settings.langsmith_project,
            description="RAG retrieve, answers, and evals",
            upsert=True,
        )
        logger.info("LangSmith project ready: %s", settings.langsmith_project)
    except Exception as exc:  # noqa: BLE001
        logger.warning("LangSmith project was not created: %s", exc)


class ReserveRequest(BaseModel):
    source_key: str = Field(alias="sourceKey")
    filename: str
    source_uri: str | None = Field(default=None, alias="sourceUri")

    model_config = {"populate_by_name": True}


class StatusRequest(BaseModel):
    status: str
    error: str | None = None


class RetrieveRequest(BaseModel):
    query: str
    top_k: int = Field(default=5, ge=1, le=20)


class AnswerRequest(BaseModel):
    question: str
    top_k: int = Field(default=5, ge=1, le=20)


class EvalRequest(BaseModel):
    answer: bool = True
    judge: bool = True
    limit: int | None = Field(default=None, ge=1, le=50)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    from rag.db import close_pool, ensure_schema
    from rag.evals.jobs import ensure_table

    logging.basicConfig(level=logging.INFO)
    configure_langsmith()
    await ensure_schema()
    await ensure_table()
    settings = get_settings()
    if settings.worker_enabled:
        try:
            from rag.worker import start, stop
        except Exception as exc:  # noqa: BLE001
            logger.error("Ingest worker failed to import: %s", exc)
            start = stop = None
        if start is not None:
            try:
                await start()
            except Exception as exc:  # noqa: BLE001
                logger.error("Ingest worker failed to start: %s", exc)
                stop = None
    else:
        stop = None
    yield
    if stop is not None:
        await stop()
    await close_pool()


app = FastAPI(title="Support Desk RAG", version="0.2.0", lifespan=lifespan)


@app.get("/health")
async def health() -> dict[str, Any]:
    from rag.db import active_chunk_table, ping

    settings = get_settings()
    database_ok = await ping()
    return {
        "status": "ok" if database_ok else "degraded",
        "service": "rag",
        "pipeline": "hybrid",
        "database": database_ok,
        "embedding_model": settings.embedding_model,
        "embedding_dim": settings.embedding_dim,
        "chunk_table": active_chunk_table(),
        "worker_enabled": settings.worker_enabled,
    }


@app.post("/documents/reserve")
async def reserve(body: ReserveRequest) -> dict[str, Any]:
    from rag.ingest import reserve_document

    try:
        return await reserve_document(
            source_key=body.source_key,
            filename=body.filename,
            source_uri=body.source_uri,
        )
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/documents")
async def documents() -> list[dict[str, Any]]:
    from rag.ingest import list_documents

    return await list_documents()


@app.get("/documents/{document_id}")
async def document(document_id: str) -> dict[str, Any]:
    from rag.ingest import get_document

    row = await get_document(document_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Document not found")
    return row


@app.post("/documents/{document_id}/status")
async def document_status(document_id: str, body: StatusRequest) -> dict[str, str]:
    from rag.ingest import set_status

    await set_status(document_id, body.status, body.error)
    return {"status": body.status}


@app.post("/retrieve")
async def retrieve_route(body: RetrieveRequest) -> dict[str, Any]:
    from rag.retrieve import retrieve

    try:
        return await retrieve(body.query, top_k=body.top_k)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.post("/answer")
async def answer_route(body: AnswerRequest) -> dict[str, Any]:
    from rag.answer import answer

    try:
        return await answer(body.question, top_k=body.top_k)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.post("/answer/stream")
async def answer_stream(body: AnswerRequest) -> StreamingResponse:
    from rag.answer import answer_events

    async def events():
        try:
            async for event in answer_events(body.question, top_k=body.top_k):
                yield f"data: {json.dumps(event)}\n\n"
        except Exception as exc:  # noqa: BLE001
            yield f"data: {json.dumps({'type': 'error', 'error': str(exc)})}\n\n"

    return StreamingResponse(events(), media_type="text/event-stream")


@app.post("/evals/run")
async def evals_run(body: EvalRequest) -> dict[str, Any]:
    from rag.evals.runner import run_rag_evals

    try:
        return await run_rag_evals(answer=body.answer, judge=body.judge, limit=body.limit)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/evals/jobs", status_code=202)
async def evals_job_start(body: EvalRequest) -> dict[str, Any]:
    from rag.evals.jobs import RunInProgress, start_run

    try:
        return await start_run(body.model_dump())
    except RunInProgress as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.get("/evals/jobs")
async def evals_job_list(limit: int = Query(default=20, ge=1, le=100)) -> list[dict[str, Any]]:
    from rag.evals.jobs import list_runs

    return await list_runs(limit)


@app.get("/evals/jobs/{run_id}")
async def evals_job_get(run_id: uuid.UUID) -> dict[str, Any]:
    from rag.evals.jobs import get_run

    row = await get_run(str(run_id))
    if row is None:
        raise HTTPException(status_code=404, detail="Eval run not found")
    return row


def run() -> None:
    import uvicorn

    uvicorn.run("rag.main:app", host="0.0.0.0", port=get_settings().port, reload=False)


if __name__ == "__main__":
    run()
