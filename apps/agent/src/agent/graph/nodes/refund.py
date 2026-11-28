"""Refund flow: load store memory → draft → interrupt → issue → write memory."""

from __future__ import annotations

from typing import Any, Literal

from langchain_core.messages import AIMessage
from langgraph.types import interrupt

from agent.graph.state import AgentState
from agent.memory.postgres import append_refund_memory, read_refund_memory
from agent.tools.approval import approval_id
from agent.tools.mcp.adapters import issue_refund
from agent.tools.mcp.client import call_mcp_tool


def _stop(text: str) -> dict[str, Any]:
    return {
        "refund_draft": {},
        "interrupt_kind": "none",
        "messages": [AIMessage(content=text)],
        "final_reply": text,
    }


async def load_refund_memory_node(state: AgentState, *, store: Any) -> dict[str, Any]:
    customer_id = (state.get("customer_id") or "").strip()
    order_id = (state.get("order_id") or "").strip()
    if customer_id == "unknown":
        customer_id = ""
    if not customer_id and order_id:
        order = await call_mcp_tool("get_order", {"order_id": order_id})
        if not order.get("error"):
            customer_id = str(order.get("customer_id") or "")
    if not customer_id:
        return {"refund_memory": []}
    notes = await read_refund_memory(store, customer_id)
    return {"refund_memory": notes, "customer_id": customer_id}


async def draft_refund(state: AgentState) -> dict[str, Any]:
    order_id = (state.get("order_id") or "").strip()
    if not order_id:
        return _stop("I can draft a refund once I have the order id, like ORD-1001.")
    eligibility = await call_mcp_tool("check_refund_eligibility", {"order_id": order_id})
    if eligibility.get("error"):
        return _stop(f"I couldn't check refund eligibility for {order_id}: {eligibility['error']}")
    if not eligibility.get("eligible"):
        reason = eligibility.get("reason") or "not eligible"
        return _stop(f"{order_id} isn't eligible for a refund: {reason}")
    amount = float(eligibility.get("max_amount") or 0)
    if amount <= 0:
        return _stop(f"{order_id} has no refundable amount.")
    memory = state.get("refund_memory") or []
    customer_id = (state.get("customer_id") or "").strip()
    draft = {
        "order_id": order_id,
        "amount": amount,
        "reason": "customer requested refund",
        "eligibility": eligibility,
        "prior_operator_notes": memory,
        "customer_id": "" if customer_id == "unknown" else customer_id,
    }
    reply = (
        f"Refund draft ready for {order_id} (${amount:.2f}). "
        "Paused for operator approval — use the Approvals page or "
        "POST /threads/{thread_id}/resume."
    )
    if memory:
        reply += f" Operator memory: {len(memory)} prior note(s) loaded."
    return {
        "refund_draft": draft,
        "interrupt_kind": "refund",
        "messages": [AIMessage(content=reply)],
        "final_reply": reply,
    }


def after_draft(state: AgentState) -> Literal["await_refund_approval", "respond"]:
    draft = state.get("refund_draft") or {}
    if draft.get("order_id") and float(draft.get("amount") or 0) > 0:
        return "await_refund_approval"
    return "respond"


async def await_refund_approval(state: AgentState) -> dict[str, Any]:
    draft = state.get("refund_draft") or {}
    decision = interrupt(
        {
            "type": "refund_approval",
            "draft": draft,
        }
    )
    # decision expected: {decision, amount?, note?}
    return {"approval": decision if isinstance(decision, dict) else {"decision": decision}}


async def issue_refund_node(state: AgentState, *, store: Any) -> dict[str, Any]:
    approval = state.get("approval") or {}
    draft = state.get("refund_draft") or {}
    decision = approval.get("decision") or "reject"
    customer_id = (draft.get("customer_id") or state.get("customer_id") or "").strip()
    if customer_id == "unknown":
        customer_id = ""

    if decision == "reject":
        note = {
            "event": "refund_rejected",
            "order_id": draft.get("order_id"),
            "operator_note": approval.get("note"),
        }
        await append_refund_memory(store, customer_id, note)
        text = "Refund request rejected by operator."
        if approval.get("note"):
            text += f" Note: {approval['note']}"
        return {
            "messages": [AIMessage(content=text)],
            "final_reply": text,
            "interrupt_kind": "none",
            "refund_outcome": "rejected",
        }

    amount = (
        float(approval["amount"])
        if decision == "edit" and approval.get("amount") is not None
        else float(draft.get("amount") or 0)
    )
    signed = approval_id(str(draft.get("order_id")), amount)
    result = await issue_refund(
        order_id=str(draft.get("order_id")),
        amount=amount,
        approval_id=signed,
        reason=draft.get("reason"),
    )
    await append_refund_memory(
        store,
        customer_id,
        {
            "event": "refund_issued" if not result.get("error") else "refund_failed",
            "order_id": draft.get("order_id"),
            "amount": amount,
            "approval_id": signed,
            "result": result,
            "operator_note": approval.get("note"),
        },
    )
    if result.get("error"):
        text = f"Could not issue refund: {result['error']}"
    else:
        text = (
            f"Refund issued for {draft.get('order_id')} "
            f"(${amount:.2f}, approval {signed[:12]})."
        )
    return {
        "messages": [AIMessage(content=text)],
        "final_reply": text,
        "interrupt_kind": "none",
        "refund_outcome": "failed" if result.get("error") else "issued",
    }
