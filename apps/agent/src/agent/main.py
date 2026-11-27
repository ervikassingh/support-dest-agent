"""FastAPI entry for the agent orchestrator. Nest calls these HTTP endpoints."""

from __future__ import annotations

import logging
import os
import uuid
from contextlib import asynccontextmanager
from typing import Any, Literal

from fastapi import FastAPI, HTTPException
from langchain_core.messages import HumanMessage
from langgraph.types import Command
from pydantic import BaseModel, Field

from agent.clients import mcp_connection_hint
from agent.graph import build_graph
from agent.memory import MemoryBundle
from agent.settings import settings

logger = logging.getLogger(__name__)

memory = MemoryBundle()
graph = None  # compiled at startup when Postgres is available


def _configure_langsmith() -> None:
    if settings.langsmith_tracing and settings.langsmith_api_key:
        os.environ["LANGSMITH_TRACING"] = "true"
        os.environ["LANGSMITH_API_KEY"] = settings.langsmith_api_key
        os.environ["LANGSMITH_PROJECT"] = settings.langsmith_project


@asynccontextmanager
async def lifespan(_app: FastAPI):
    global graph
    _configure_langsmith()
    await memory.start()
    if memory.ready and memory.checkpointer is not None and memory.store is not None:
        graph = build_graph(checkpointer=memory.checkpointer, store=memory.store)
        logger.info("LangGraph compiled with PostgresSaver + PostgresStore")
    else:
        graph = None
        logger.error("LangGraph not compiled: %s", memory.error)
    yield
    await memory.stop()
    graph = None


app = FastAPI(title="Support Desk Agent", version="0.2.0", lifespan=lifespan)


class ChatRequest(BaseModel):
    message: str
    thread_id: str | None = Field(default=None, alias="threadId")

    model_config = {"populate_by_name": True}


class ResumeRequest(BaseModel):
    decision: Literal["approve", "edit", "reject"]
    amount: float | None = None
    note: str | None = None


def _require_graph():
    if graph is None:
        raise HTTPException(
            status_code=503,
            detail=f"Agent graph unavailable (Postgres): {memory.error or 'not ready'}",
        )
    return graph


def _config(thread_id: str) -> dict[str, Any]:
    return {"configurable": {"thread_id": thread_id}}


def _reply_from_state(values: dict[str, Any]) -> str:
    if values.get("final_reply"):
        return str(values["final_reply"])
    messages = values.get("messages") or []
    for msg in reversed(messages):
        content = getattr(msg, "content", None)
        if content and getattr(msg, "type", "") == "ai":
            return content if isinstance(content, str) else str(content)
    return ""


def _interrupt_payload(snapshot: Any) -> dict[str, Any] | None:
    interrupts = []
    try:
        for task in snapshot.tasks or []:
            for item in getattr(task, "interrupts", None) or []:
                interrupts.append(getattr(item, "value", item))
    except Exception:  # noqa: BLE001
        return None
    if not interrupts:
        return None
    first = interrupts[0]
    return first if isinstance(first, dict) else {"value": first}


@app.get("/health")
async def health() -> dict[str, Any]:
    return {
        "status": "ok" if memory.ready and graph is not None else "degraded",
        "service": "agent",
        "rag_url": settings.rag_url,
        "mcp": mcp_connection_hint(),
        "checkpointer": "postgres" if memory.ready else "unavailable",
        "store": "postgres" if memory.ready else "unavailable",
        "memory_error": memory.error,
        "models": {
            "provider": "openrouter",
            "base_url": settings.openrouter_base_url,
            "cheap": settings.cheap_model,
            "main": settings.main_model,
        },
        "email_provider": settings.email_provider,
    }


@app.post("/chat")
async def chat(body: ChatRequest) -> dict[str, Any]:
    g = _require_graph()
    thread_id = body.thread_id or f"thread-{uuid.uuid4().hex[:10]}"
    config = _config(thread_id)
    text = body.message.strip()

    snapshot = await g.aget_state(config)
    if snapshot.next:
        payload = _interrupt_payload(snapshot) or {}
        kind = payload.get("type")
        if kind == "email_confirm":
            confirmed = text.lower() in {"yes", "y", "confirm", "approve", "send", "ok", "okay"}
            rejected = text.lower() in {"no", "n", "cancel", "reject", "stop"}
            if not confirmed and not rejected:
                return {
                    "reply": (
                        "I'm waiting for you to confirm the email draft. "
                        "Reply **yes** to send or **no** to cancel."
                    ),
                    "threadId": thread_id,
                    "status": "interrupted",
                    "interrupt": payload,
                }
            result = await g.ainvoke(Command(resume={"confirmed": confirmed}), config)
            return {
                "reply": _reply_from_state(result),
                "threadId": thread_id,
                "status": "ok",
            }
        if kind == "refund_approval":
            return {
                "reply": (
                    "A refund draft is waiting for operator approval. "
                    "Use the Approvals page or POST /threads/"
                    f"{thread_id}/resume."
                ),
                "threadId": thread_id,
                "status": "interrupted",
                "interrupt": payload,
            }

    result = await g.ainvoke({"messages": [HumanMessage(content=text)]}, config)
    status = "ok"
    snap = await g.aget_state(config)
    interrupt = None
    if snap.next:
        status = "interrupted"
        interrupt = _interrupt_payload(snap)

    return {
        "reply": _reply_from_state(result),
        "threadId": thread_id,
        "status": status,
        **({"interrupt": interrupt} if interrupt else {}),
    }


@app.post("/threads/{thread_id}/resume")
async def resume(thread_id: str, body: ResumeRequest) -> dict[str, Any]:
    """Operator HITL resume for refund approvals."""
    g = _require_graph()
    config = _config(thread_id)
    snapshot = await g.aget_state(config)
    if not snapshot.next:
        raise HTTPException(status_code=404, detail=f"No paused run for {thread_id}")

    payload = _interrupt_payload(snapshot) or {}
    if payload.get("type") != "refund_approval":
        raise HTTPException(
            status_code=400,
            detail=f"Thread is paused for {payload.get('type') or 'unknown'}, not refund_approval",
        )

    result = await g.ainvoke(
        Command(
            resume={
                "decision": body.decision,
                "amount": body.amount,
                "note": body.note,
            }
        ),
        config,
    )
    return {
        "status": "resumed" if body.decision != "reject" else "rejected",
        "message": _reply_from_state(result),
        "threadId": thread_id,
        "approval": body.model_dump(),
    }


def run() -> None:
    import uvicorn

    uvicorn.run("agent.main:app", host="0.0.0.0", port=settings.port, reload=False)


if __name__ == "__main__":
    run()
