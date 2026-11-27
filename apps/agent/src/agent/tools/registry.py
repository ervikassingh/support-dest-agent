"""Tool registry: MCP read tools bound to the main agent (writes excluded)."""

from __future__ import annotations

from langchain_core.tools import BaseTool

from agent.tools.mcp.adapters import build_read_tools


def get_main_agent_tools() -> list[BaseTool]:
    """Tools the model may call. Write tools (email/refund) are NOT included."""
    return list(build_read_tools())
