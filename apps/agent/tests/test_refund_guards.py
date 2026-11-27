import asyncio
import hashlib
import hmac
from unittest.mock import AsyncMock, patch

from langchain_core.messages import AIMessage

from agent.graph.nodes.main_agent import after_main, stop_tool_loop
from agent.graph.nodes.refund import after_draft, draft_refund
from agent.routing.intent import normalize_customer_id, normalize_order_id
from agent.settings import settings
from agent.tools.approval import approval_id


def test_approval_id_signs_order_and_cents():
    mac = hmac.new(
        settings.approval_secret.encode(),
        b"ORD-1001:4999",
        hashlib.sha256,
    ).hexdigest()
    assert approval_id("ORD-1001", 49.99) == f"APR-{mac}"
    assert approval_id("ORD-1001", 10) != approval_id("ORD-1002", 10)


def test_customer_ids_match_mcp():
    assert normalize_customer_id("see CUST-2 please") == "CUS-2"
    assert normalize_customer_id("cus-guest") == "CUS-GUEST"
    assert normalize_customer_id("null") == ""
    assert normalize_order_id("order ord-1003") == "ORD-1003"
    assert normalize_order_id(None) == ""


def test_draft_without_order_does_not_pick_one():
    result = asyncio.run(draft_refund({}))
    assert result["refund_draft"] == {}
    assert result["interrupt_kind"] == "none"
    assert after_draft(result) == "respond"


def test_ineligible_order_does_not_interrupt():
    eligibility = {"eligible": False, "reason": "Order still in transit", "max_amount": 0}

    async def fake_tool(name, arguments):
        assert name == "check_refund_eligibility"
        return eligibility

    with patch("agent.graph.nodes.refund.call_mcp_tool", new=AsyncMock(side_effect=fake_tool)):
        result = asyncio.run(draft_refund({"order_id": "ORD-1002"}))
    assert result["refund_draft"] == {}
    assert "in transit" in result["final_reply"]
    assert after_draft(result) == "respond"


def test_step_limit_closes_the_tool_call():
    call = AIMessage(
        content="",
        tool_calls=[{"id": "call-1", "name": "get_order", "args": {"order_id": "ORD-1001"}}],
    )
    state = {"messages": [call], "step_count": 8}
    assert after_main(state) == "stop"
    assert after_main({**state, "step_count": 7}) == "tools"
    stopped = asyncio.run(stop_tool_loop(state))
    assert stopped["messages"][0].tool_call_id == "call-1"
    assert "step limit" in stopped["final_reply"]
