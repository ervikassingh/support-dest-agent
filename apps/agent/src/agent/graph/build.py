"""Compile the support-desk LangGraph with PostgresSaver + PostgresStore."""

from __future__ import annotations

from typing import Any

from langgraph.graph import END, START, StateGraph
from langgraph.prebuilt import ToolNode

from agent.graph.nodes.cheap import cheap_agent
from agent.graph.nodes.email import await_email_confirm, draft_email, send_email_node
from agent.graph.nodes.main_agent import after_main, main_agent, prepare_main, stop_tool_loop
from agent.graph.nodes.refund import (
    after_draft,
    await_refund_approval,
    draft_refund,
    issue_refund_node,
    load_refund_memory_node,
)
from agent.graph.nodes.router import after_router, route_intent
from agent.graph.nodes.summarize import summarize_if_needed
from agent.graph.state import AgentState
from agent.tools import get_main_agent_tools


def build_graph(*, checkpointer: Any, store: Any):
    async def load_memory(state: AgentState) -> dict:
        return await load_refund_memory_node(state, store=store)

    async def issue_refund(state: AgentState) -> dict:
        return await issue_refund_node(state, store=store)

    def respond(state: AgentState) -> dict:
        # final_reply already set by upstream nodes
        return {}

    builder = StateGraph(AgentState)
    builder.add_node("summarize", summarize_if_needed)
    builder.add_node("router", route_intent)
    builder.add_node("cheap_agent", cheap_agent)
    builder.add_node("prepare_main", prepare_main)
    builder.add_node("main_agent", main_agent)
    builder.add_node("tools", ToolNode(get_main_agent_tools()))
    builder.add_node("stop_tool_loop", stop_tool_loop)
    builder.add_node("load_refund_memory", load_memory)
    builder.add_node("draft_refund", draft_refund)
    builder.add_node("await_refund_approval", await_refund_approval)
    builder.add_node("issue_refund", issue_refund)
    builder.add_node("draft_email", draft_email)
    builder.add_node("await_email_confirm", await_email_confirm)
    builder.add_node("send_email", send_email_node)
    builder.add_node("respond", respond)

    builder.add_edge(START, "summarize")
    builder.add_edge("summarize", "router")
    builder.add_conditional_edges(
        "router",
        after_router,
        {
            "cheap_agent": "cheap_agent",
            "main_agent": "prepare_main",
            "refund_flow": "load_refund_memory",
            "email_flow": "draft_email",
        },
    )
    builder.add_edge("cheap_agent", "respond")
    builder.add_edge("prepare_main", "main_agent")
    builder.add_conditional_edges(
        "main_agent",
        after_main,
        {"tools": "tools", "stop": "stop_tool_loop", "respond": "respond"},
    )
    builder.add_edge("tools", "main_agent")
    builder.add_edge("stop_tool_loop", "respond")
    builder.add_edge("load_refund_memory", "draft_refund")
    builder.add_conditional_edges(
        "draft_refund",
        after_draft,
        {"await_refund_approval": "await_refund_approval", "respond": "respond"},
    )
    builder.add_edge("await_refund_approval", "issue_refund")
    builder.add_edge("issue_refund", "respond")
    builder.add_edge("draft_email", "await_email_confirm")
    builder.add_edge("await_email_confirm", "send_email")
    builder.add_edge("send_email", "respond")
    builder.add_edge("respond", END)

    return builder.compile(checkpointer=checkpointer, store=store)
