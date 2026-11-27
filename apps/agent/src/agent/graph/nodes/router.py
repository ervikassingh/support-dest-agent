from __future__ import annotations

from typing import Any, Literal

from agent.graph.state import AgentState
from agent.routing.intent import classify_intent


async def route_intent(state: AgentState) -> dict[str, Any]:
    result = await classify_intent(list(state.get("messages") or []))
    return {
        "intent": result["intent"],
        "order_id": result.get("order_id") or state.get("order_id") or "",
        "customer_id": result.get("customer_id") or state.get("customer_id") or "",
        "interrupt_kind": "none",
    }


def after_router(
    state: AgentState,
) -> Literal["cheap_agent", "main_agent", "refund_flow", "email_flow"]:
    intent = state.get("intent") or "policy"
    if intent in ("chitchat", "out_of_scope"):
        return "cheap_agent"
    if intent == "refund":
        return "refund_flow"
    if intent == "email":
        return "email_flow"
    return "main_agent"
