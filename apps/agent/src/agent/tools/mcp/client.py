"""Thin MCP Streamable HTTP client — one session per tool call."""

from __future__ import annotations

import json
import logging
from typing import Any

from agent.settings import settings

logger = logging.getLogger(__name__)


async def call_mcp_tool(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    """Invoke an MCP tool. Soft-fails with an error dict if MCP is unreachable."""
    try:
        from mcp import ClientSession
        from mcp.client.streamable_http import streamable_http_client
    except ImportError as exc:
        return {"error": f"MCP client unavailable: {exc}"}

    try:
        async with streamable_http_client(settings.mcp_url) as streams:
            read, write = streams[0], streams[1]
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.call_tool(name, arguments)
                texts: list[str] = []
                for block in result.content or []:
                    text = getattr(block, "text", None)
                    if text:
                        texts.append(text)
                raw = "\n".join(texts) if texts else ""
                try:
                    return json.loads(raw) if raw else {"raw": raw}
                except json.JSONDecodeError:
                    return {"raw": raw}
    except Exception as exc:  # noqa: BLE001
        logger.warning("MCP tool %s failed: %s", name, exc)
        return {"error": str(exc), "tool": name}
