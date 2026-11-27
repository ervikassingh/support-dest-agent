"""Main agent with read-tool loop (MCP). Writes are never bound."""

from __future__ import annotations

from typing import Any, Literal

from langchain_core.messages import AIMessage, SystemMessage

from agent.clients import rag_answer
from agent.graph.state import AgentState
from agent.models import get_main_model
from agent.tools import get_main_agent_tools

_SYSTEM = """You are the main support desk agent for a fictional store.
Use tools to look up orders, shipping, eligibility, and customers.
Answer policy questions using any retrieved policy context provided.
Never claim you issued a refund or sent an email — those require human confirmation flows.
Be concise and cite order ids when relevant.
If the customer wants a refund or an email, tell them to ask explicitly for that
so the dedicated flow can run (or continue if already in progress)."""

MAX_STEPS = 8


async def prepare_main(state: AgentState) -> dict[str, Any]:
    """Optional RAG retrieve for policy intent."""
    updates: dict[str, Any] = {"step_count": 0}
    if state.get("intent") == "policy":
        last = ""
        for msg in reversed(state.get("messages") or []):
            if getattr(msg, "type", None) == "human":
                last = getattr(msg, "content", "") or ""
                break
        rag = await rag_answer(str(last))
        docs = []
        if rag.get("answer"):
            docs.append({"answer": rag["answer"], "citations": rag.get("citations") or []})
        updates["documents"] = docs
        updates["citations"] = rag.get("citations") or []
    return updates


async def main_agent(state: AgentState) -> dict[str, Any]:
    tools = get_main_agent_tools()
    model = get_main_model().bind_tools(tools)
    docs = state.get("documents") or []
    doc_block = ""
    if docs:
        doc_block = "\n\nRetrieved policy context:\n" + "\n".join(
            str(d.get("answer") or d) for d in docs
        )
    messages = [
        SystemMessage(content=_SYSTEM + doc_block),
        *(state.get("messages") or []),
    ]
    resp = await model.ainvoke(messages)
    step = int(state.get("step_count") or 0) + 1
    updates: dict[str, Any] = {"messages": [resp], "step_count": step}
    if not getattr(resp, "tool_calls", None):
        text = resp.content if isinstance(resp.content, str) else str(resp.content)
        updates["final_reply"] = text
    return updates


def after_main(state: AgentState) -> Literal["tools", "respond"]:
    messages = state.get("messages") or []
    if not messages:
        return "respond"
    last = messages[-1]
    if isinstance(last, AIMessage) and last.tool_calls and int(state.get("step_count") or 0) < MAX_STEPS:
        return "tools"
    return "respond"
