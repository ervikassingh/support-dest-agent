"""Outbound clients: RAG over HTTP, MCP connection hint."""

from __future__ import annotations

import logging
from typing import Any

import httpx

from agent.settings import settings

logger = logging.getLogger(__name__)


async def rag_retrieve(query: str, top_k: int = 5) -> dict[str, Any]:
    """Fetch policy chunks. Failures leave the agent with empty context."""
    url = f"{settings.rag_url.rstrip('/')}/retrieve"
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            res = await client.post(url, json={"query": query, "top_k": top_k})
            res.raise_for_status()
            return res.json()
    except Exception as exc:  # noqa: BLE001 - chat still answers without policy context
        logger.warning("RAG retrieve failed (%s): %s", url, exc)
        return {"query": query, "documents": [], "citations": [], "error": str(exc)}


def mcp_connection_hint() -> dict[str, Any]:
    """Document the shared MCP HTTP endpoint used by tool adapters."""
    return {
        "transport": "streamable-http",
        "url": settings.mcp_url,
        "connected": True,
        "note": "Read tools call MCP per invocation; write tools are graph-gated.",
    }
