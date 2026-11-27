"""Context-window summarization when token budget is nearly full."""

from __future__ import annotations

from typing import Any

from langchain_core.messages import HumanMessage, RemoveMessage, SystemMessage

from agent.graph.state import AgentState
from agent.models import get_cheap_model
from agent.settings import settings


def _estimate_tokens(messages: list[Any]) -> int:
    total = 0
    for msg in messages:
        content = getattr(msg, "content", "") or ""
        if not isinstance(content, str):
            content = str(content)
        total += max(1, len(content) // 4)
    return total


async def summarize_if_needed(state: AgentState) -> dict[str, Any]:
    """Replace older messages with a summary when near the context budget.

    Skips when an interrupt is open (refund/email confirmation in progress).
    """
    if state.get("interrupt_kind") in ("refund", "email"):
        return {"token_count": _estimate_tokens(state.get("messages") or [])}

    messages = list(state.get("messages") or [])
    token_count = _estimate_tokens(messages)
    threshold = int(settings.context_token_budget * settings.summarize_threshold_ratio)
    if token_count < threshold or len(messages) <= settings.keep_recent_messages + 1:
        return {"token_count": token_count}

    keep = settings.keep_recent_messages
    older, recent = messages[:-keep], messages[-keep:]
    if not older:
        return {"token_count": token_count}

    transcript = []
    for msg in older:
        role = getattr(msg, "type", "message")
        content = getattr(msg, "content", "")
        transcript.append(f"{role}: {content}")

    model = get_cheap_model()
    summary_resp = await model.ainvoke(
        [
            SystemMessage(
                content=(
                    "Summarize this support conversation for continuity. "
                    "Keep order ids, customer ids, refund/email status, and open questions."
                )
            ),
            HumanMessage(content="\n".join(transcript)),
        ]
    )
    summary_text = (
        summary_resp.content if isinstance(summary_resp.content, str) else str(summary_resp.content)
    )
    prior = state.get("summary") or ""
    merged = f"{prior}\n{summary_text}".strip() if prior else summary_text

    removals = [RemoveMessage(id=m.id) for m in older if getattr(m, "id", None)]
    summary_msg = SystemMessage(content=f"[Conversation summary]\n{merged}")
    return {
        "messages": [*removals, summary_msg],
        "summary": merged,
        "token_count": _estimate_tokens([summary_msg, *recent]),
    }
