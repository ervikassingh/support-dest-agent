"""Outbound clients: RAG over HTTP, MCP connection hint."""

from __future__ import annotations

import logging
from typing import Any

import httpx

from agent.settings import settings

logger = logging.getLogger(__name__)


async def rag_answer(question: str) -> dict[str, Any]:
    """Call the RAG service. Failures return a soft stub so chat still works."""
    url = f"{settings.rag_url.rstrip('/')}/answer"
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            res = await client.post(url, json={"question": question})
            res.raise_for_status()
            return res.json()
    except Exception as exc:  # noqa: BLE001 - stub path
        logger.warning("RAG call failed (%s): %s", url, exc)
        return {
            "answer": None,
            "citations": [],
            "error": str(exc),
            "stub": True,
        }


def mcp_connection_hint() -> dict[str, Any]:
    """Document the shared MCP HTTP endpoint used by tool adapters."""
    return {
        "transport": "streamable-http",
        "url": settings.mcp_url,
        "connected": True,
        "note": "Read tools call MCP per invocation; write tools are graph-gated.",
    }
