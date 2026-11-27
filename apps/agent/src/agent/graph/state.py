"""Shared LangGraph agent state."""

from __future__ import annotations

from typing import Annotated, Any, Literal

from langgraph.graph.message import add_messages
from typing_extensions import TypedDict

Intent = Literal["chitchat", "policy", "order", "refund", "email", "out_of_scope"]


class AgentState(TypedDict, total=False):
    messages: Annotated[list[Any], add_messages]
    intent: Intent
    customer_id: str
    order_id: str
    documents: list[dict[str, Any]]
    citations: list[dict[str, Any]]
    refund_draft: dict[str, Any]
    email_draft: dict[str, Any]
    refund_memory: list[dict[str, Any]]
    approval: dict[str, Any]
    email_confirmed: bool
    step_count: int
    token_count: int
    summary: str
    final_reply: str
    interrupt_kind: Literal["none", "refund", "email"]
