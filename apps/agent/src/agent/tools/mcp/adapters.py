"""LangChain tools that wrap MCP read endpoints (writes stay graph-gated)."""

from __future__ import annotations

import json

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

from agent.tools.mcp.client import call_mcp_tool


class OrderIdInput(BaseModel):
    order_id: str = Field(description="Order id, e.g. ORD-1001")


class CustomerIdInput(BaseModel):
    customer_id: str = Field(description="Customer id, e.g. CUST-1")


async def _get_order(order_id: str) -> str:
    return json.dumps(await call_mcp_tool("get_order", {"order_id": order_id}))


async def _get_shipping_status(order_id: str) -> str:
    return json.dumps(await call_mcp_tool("get_shipping_status", {"order_id": order_id}))


async def _check_refund_eligibility(order_id: str) -> str:
    return json.dumps(await call_mcp_tool("check_refund_eligibility", {"order_id": order_id}))


async def _get_customer(customer_id: str) -> str:
    return json.dumps(await call_mcp_tool("get_customer", {"customer_id": customer_id}))


def build_read_tools() -> list[StructuredTool]:
    return [
        StructuredTool.from_function(
            coroutine=_get_order,
            name="get_order",
            description="[read] Order by id: items, totals, status, customer",
            args_schema=OrderIdInput,
        ),
        StructuredTool.from_function(
            coroutine=_get_shipping_status,
            name="get_shipping_status",
            description="[read] Carrier status and timestamps",
            args_schema=OrderIdInput,
        ),
        StructuredTool.from_function(
            coroutine=_check_refund_eligibility,
            name="check_refund_eligibility",
            description="[read] Window, prior refunds, item eligibility, max amount",
            args_schema=OrderIdInput,
        ),
        StructuredTool.from_function(
            coroutine=_get_customer,
            name="get_customer",
            description="[read] Customer record and recent orders",
            args_schema=CustomerIdInput,
        ),
    ]


async def issue_refund(
    *,
    order_id: str,
    amount: float,
    approval_id: str,
    reason: str | None = None,
) -> dict:
    """Write tool — only call from post-HITL graph nodes."""
    return await call_mcp_tool(
        "issue_refund",
        {
            "order_id": order_id,
            "amount": amount,
            "approval_id": approval_id,
            "reason": reason,
        },
    )
