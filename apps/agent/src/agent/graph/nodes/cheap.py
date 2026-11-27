"""Cheap agent — no tools; chitchat / out-of-scope only."""

from __future__ import annotations

from typing import Any

from langchain_core.messages import AIMessage, SystemMessage

from agent.graph.state import AgentState
from agent.models import get_cheap_model

_SYSTEM = """You are a friendly support desk assistant for a fictional store.
You have NO tools. Keep replies short.
If the user needs order help, refunds, policy details, or email, tell them briefly
you'll need to help via the full support flow — but still be warm.
For out_of_scope, politely decline and offer to connect them with a human."""


async def cheap_agent(state: AgentState) -> dict[str, Any]:
    model = get_cheap_model()
    intent = state.get("intent") or "chitchat"
    messages = [
        SystemMessage(content=f"{_SYSTEM}\nCurrent intent: {intent}"),
        *(state.get("messages") or []),
    ]
    resp = await model.ainvoke(messages)
    text = resp.content if isinstance(resp.content, str) else str(resp.content)
    return {
        "messages": [AIMessage(content=text)],
        "final_reply": text,
    }
