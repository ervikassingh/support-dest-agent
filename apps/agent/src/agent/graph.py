"""
LangGraph skeleton (not wired yet).

Intended nodes:
  router -> retrieve / answer_policy | order_agent | draft_refund -> await_approval (interrupt)
         -> issue_refund | fallback | respond

Postgres checkpointer and real MCP/RAG calls land in a later pass.
For now `main.py` returns stub replies without compiling a graph.
"""

from __future__ import annotations

from typing import Any, Literal, TypedDict


class AgentState(TypedDict, total=False):
    messages: list[dict[str, Any]]
    intent: Literal["policy", "order", "refund", "out_of_scope"]
    customer_id: str
    order_id: str
    documents: list[dict[str, Any]]
    citations: list[dict[str, Any]]
    refund_draft: dict[str, Any]
    approval: Literal["approve", "edit", "reject"]
    step_count: int
    token_count: int
    final_reply: str


def build_graph():  # pragma: no cover - placeholder
    """
    Placeholder for:

        from langgraph.graph import StateGraph, END
        builder = StateGraph(AgentState)
        builder.add_node("router", ...)
        ...
        return builder.compile(checkpointer=...)

    Keep imports lazy until the graph is implemented so `uvicorn` can boot without
    a full LangGraph runtime path.
    """
    raise NotImplementedError("LangGraph compile is stubbed; see module docstring.")
