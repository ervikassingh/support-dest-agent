# agent decisions

System-wide decisions are in [architecture/decisions](../../architecture/decisions/README.md). The core ones for this service are [0007: write tools gated by interrupt](../../architecture/decisions/0007-write-tools-gated-by-interrupt.md) and [0008: Postgres checkpointer and store](../../architecture/decisions/0008-postgres-checkpointer-and-store.md).

## AGENT-1. Route first with a cheap model, keyword fallback

**Context.** Most messages are small talk or a single lookup. Sending all of them to the main model with tools wastes tokens.

**Decision.** `router` asks `CHEAP_MODEL` for JSON `{intent, order_id, customer_id}` over the last human message. On any exception or unknown label it uses `_heuristic()` keyword matching. Regex extraction of order and customer ids backs up the model's output.

**Alternatives.** Structured output / function calling for the classification; embedding-based classifier; no router (one agent with all tools).

**Consequences.** Cheap and fast. Only the latest message is classified, so follow-ups like "yes, do it" lose context ([AGENT-TD-8](tech-debt.md)). The heuristic defaults to `policy`.

## AGENT-2. Two model tiers

**Decision.** `CHEAP_MODEL` for router, cheap agent, and summarizer. `MAIN_MODEL` for the tool-using agent. Both via OpenRouter ([ADR 0004](../../architecture/decisions/0004-openrouter-single-model-gateway.md)), `temperature=0`, cached with `lru_cache`.

**Consequences.** Swapping either is an env change. Refund drafting uses no model at all today; the README's "stronger model for refund reasoning" is not applied.

## AGENT-3. Agent retrieves; agent writes the policy answer

**Context.** rag has both `/retrieve` and `/answer`.

**Decision.** The agent calls `/retrieve` and lets `MAIN_MODEL` answer with the chunks in its system prompt, so the same model can also call order tools in that turn.

**Alternatives.** Call rag `/answer` and relay it; RAG as a tool the model chooses to call.

**Consequences.** Policy and order context can be mixed in one answer. rag's refusal and citation handling in `/answer` is bypassed, and citations are kept in state but not returned to the caller ([AGENT-TD-7](tech-debt.md)). Retrieval only runs when the router says `policy`.

## AGENT-4. One MCP session per tool call

**Decision.** `call_mcp_tool` opens a Streamable HTTP client, initializes a session, calls one tool, and closes. Any failure returns `{"error": ..., "tool": name}` instead of raising.

**Alternatives.** A long-lived session opened in the lifespan; `langchain-mcp-adapters` with tool discovery.

**Consequences.** No connection state to manage, and the agent survives mcp-server restarts. Each call pays an MCP handshake. Tool schemas are hand-copied in `adapters.py` rather than discovered.

## AGENT-5. Refunds resume only from the operator endpoint; emails resume from chat

**Context.** Refunds need an operator. Email confirmation is the customer's own choice.

**Decision.** `/chat` resumes an `email_confirm` interrupt on a yes-like or no-like message and refuses to resume `refund_approval`. `/threads/{id}/resume` resumes only `refund_approval`.

**Consequences.** A customer cannot approve their own refund through chat. The thread blocks on new chat input until the operator acts.

## AGENT-6. Hard step limit on the tool loop

**Decision.** `MAX_STEPS = 8` main-model calls per turn, checked in `after_main`.

**Consequences.** Bounds cost and runaway loops. At the limit the graph closes the open tool calls and tells the customer a person can take over. It does not call `escalate_to_human` ([AGENT-TD-11](tech-debt.md)).

## AGENT-7. Summarize instead of truncating

**Decision.** At 70% of `CONTEXT_TOKEN_BUDGET`, replace all but the last 8 messages with a cheap-model summary that keeps ids and refund or email status. Never while an interrupt is open, so the draft context stays intact.

**Consequences.** Long threads keep working. Token counts are estimated from characters, not measured.

## AGENT-8. Operator memory in the LangGraph store, per customer

**Decision.** Every refund decision appends `{event, order_id, amount?, approval_id?, result?, operator_note}` under `("refunds", "operator") / customer_id`, keeping the last 50. Notes are loaded into the next draft for that customer.

**Consequences.** Operators see history across threads. Notes are skipped when the customer id is missing. The id comes from the message (`CUS-#` or `CUS-GUEST`) or from `get_order`.
