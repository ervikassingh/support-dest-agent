"""FastAPI entry for the agent orchestrator. Nest calls these HTTP endpoints."""

from __future__ import annotations

import uuid
from typing import Any, Literal

from fastapi import FastAPI
from pydantic import BaseModel, Field

from agent.clients import mcp_connection_hint, rag_answer
from agent.settings import settings

app = FastAPI(title="Support Desk Agent", version="0.1.0")

# In-memory pause table until Postgres checkpointer lands.
_paused: dict[str, dict[str, Any]] = {}


class ChatRequest(BaseModel):
    message: str
    thread_id: str | None = Field(default=None, alias="threadId")

    model_config = {"populate_by_name": True}


class ChatResponse(BaseModel):
    reply: str
    thread_id: str = Field(serialization_alias="threadId")
    status: str

    model_config = {"populate_by_name": True}


class ResumeRequest(BaseModel):
    decision: Literal["approve", "edit", "reject"]
    amount: float | None = None
    note: str | None = None


@app.get("/health")
async def health() -> dict[str, Any]:
    return {
        "status": "ok",
        "service": "agent",
        "rag_url": settings.rag_url,
        "mcp": mcp_connection_hint(),
        "checkpointer": "memory-stub",
    }


@app.post("/chat")
async def chat(body: ChatRequest) -> dict[str, Any]:
    """
    Stub chat path:
    - allocates a thread id
    - optionally probes RAG (HTTP)
    - if message looks like a refund, simulate HITL interrupt
    Real LangGraph routing / MCP tools come later.
    """
    thread_id = body.thread_id or f"thread-{uuid.uuid4().hex[:10]}"
    text = body.message.strip()
    lower = text.lower()

    if any(w in lower for w in ("refund", "money back", "return my money")):
        _paused[thread_id] = {
            "draft": {
                "order_id": "ORD-1001",
                "amount": 49.99,
                "reason": "customer requested refund (stub)",
            },
            "message": text,
        }
        return {
            "reply": (
                "Stub: refund draft ready for ORD-1001 ($49.99). "
                "Paused for human approval — use the Approvals page or "
                f"POST /threads/{thread_id}/resume."
            ),
            "threadId": thread_id,
            "status": "interrupted",
        }

    rag = await rag_answer(text)
    if rag.get("answer"):
        reply = str(rag["answer"])
    else:
        reply = (
            "Stub agent reply (LangGraph not compiled yet). "
            f"Received: {text!r}. "
            f"RAG probe: {'ok' if not rag.get('error') else 'unreachable'} "
            f"({settings.rag_url}). MCP: {settings.mcp_url} (client not connected)."
        )

    return {
        "reply": reply,
        "threadId": thread_id,
        "status": "ok",
    }


@app.post("/threads/{thread_id}/resume")
async def resume(thread_id: str, body: ResumeRequest) -> dict[str, Any]:
    """HITL resume stub. Real path: load checkpoint, resume graph with approval."""
    paused = _paused.pop(thread_id, None)
    draft = (paused or {}).get("draft", {})
    amount = body.amount if body.decision == "edit" and body.amount is not None else draft.get(
        "amount"
    )

    if body.decision == "reject":
        return {
            "status": "rejected",
            "message": f"Stub: refund rejected for {thread_id}."
            + (f" Note: {body.note}" if body.note else ""),
            "threadId": thread_id,
        }

    return {
        "status": "resumed",
        "message": (
            f"Stub: would call MCP issue_refund for {thread_id} "
            f"(decision={body.decision}, amount={amount}). "
            "Write tool still refuses without approval context on the MCP side."
        ),
        "threadId": thread_id,
        "approval": body.model_dump(),
    }


def run() -> None:
    import uvicorn

    uvicorn.run("agent.main:app", host="0.0.0.0", port=settings.port, reload=False)


if __name__ == "__main__":
    run()
