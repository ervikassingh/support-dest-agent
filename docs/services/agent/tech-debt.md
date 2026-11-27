# agent tech debt

Severity levels are defined in [architecture/tech-debt.md](../../architecture/tech-debt.md). The customer id format mismatch with mcp-server is [X-TD-2](../../architecture/tech-debt.md#x-td-2-customer-id-format-disagrees-between-agent-and-mcp-server).

| ID | Item | Severity |
| --- | --- | --- |
| AGENT-TD-1 | Refund draft falls back to a hard-coded order and amount | High |
| AGENT-TD-2 | Hitting the step limit leaves a dangling tool call and a stale reply | High |
| AGENT-TD-3 | Operator notes for unknown customers share one bucket | High |
| AGENT-TD-4 | Refund is drafted even when the order is ineligible | Medium |
| AGENT-TD-5 | `approval_id` is minted by the agent, not by the approver | Medium |
| AGENT-TD-6 | Email recipient and body are hard-coded | Medium |
| AGENT-TD-7 | No weak-retrieval refusal; citations not returned | Medium |
| AGENT-TD-8 | Router sees only the last message | Medium |
| AGENT-TD-9 | No recovery if Postgres is down at startup | Medium |
| AGENT-TD-10 | Summary message lands after the recent messages | Medium |
| AGENT-TD-11 | Planned fallback, escalation, and token cap are missing | Medium |
| AGENT-TD-12 | Concurrent requests on one thread race | Low |
| AGENT-TD-13 | Evals share production checkpoint tables | Low |
| AGENT-TD-14 | Small inefficiencies and misleading health output | Low |

### AGENT-TD-1. Refund draft falls back to a hard-coded order and amount

**Severity:** High.

`draft_refund` in `graph/nodes/refund.py` uses `order_id = state.get("order_id") or "ORD-1001"` and `amount = 49.99` when eligibility returns no max or an error. "I want a refund" with no order id drafts a refund for ORD-1001 and sends it to the operator.

**Fix:** if there is no order id, ask for one and end the turn. If eligibility errors, tell the operator and do not propose an amount.

### AGENT-TD-2. Hitting the step limit leaves a dangling tool call and a stale reply

**Severity:** High.

When `after_main` stops at 8 steps, the last `AIMessage` still has `tool_calls` with no matching `ToolMessage`, and `final_reply` is not updated. `/chat` then returns whatever `final_reply` was from an earlier turn (state persists across turns). On the next turn the provider can reject the history because a tool call has no result.

**Fix:** on limit, append `ToolMessage`s that say the limit was reached (or drop the pending call), set a clear `final_reply` that offers a human, and clear `final_reply` at the start of every turn.

### AGENT-TD-3. Operator notes for unknown customers share one bucket

**Severity:** High.

`read_refund_memory` and `append_refund_memory` use `customer_id or "unknown"`. Because customer ids are rarely extracted ([X-TD-2](../../architecture/tech-debt.md#x-td-2-customer-id-format-disagrees-between-agent-and-mcp-server)), most refund notes from every customer go into `unknown`, and are loaded into every later anonymous draft. That mixes customers' data in front of operators and skews decisions.

**Fix:** derive `customer_id` from `get_order` during drafting. Skip memory reads and writes when it is unknown.

### AGENT-TD-4. Refund is drafted even when the order is ineligible

**Severity:** Medium.

`draft_refund` does not check `eligibility["eligible"]`. An already-refunded or in-transit order still interrupts for approval with `amount = 0` (or the fallback), and MCP rejects it only after the operator approves.

**Fix:** when ineligible, reply with the reason and offer escalation; do not interrupt.

### AGENT-TD-5. `approval_id` is minted by the agent, not by the approver

**Severity:** Medium.

`issue_refund_node` creates `APR-<hex>` right before calling MCP. It proves the node ran, not who approved. There is no approval record, no operator identity, and nothing MCP can verify ([MCP-TD-1](../mcp-server/tech-debt.md)).

**Fix:** api creates an approval record (operator id, decision, amount, timestamp) and passes its id through resume. MCP verifies it.

### AGENT-TD-6. Email recipient and body are hard-coded

**Severity:** Medium.

`draft_email` always addresses `customer@example.com` with a fixed template. `EMAIL_PROVIDER=resend` is accepted by settings but not implemented; any non-`stub` value reports `status: sent` without sending.

**Fix:** look up the customer email via `get_customer`, draft the body with a model from the conversation, and implement a real provider or reject unknown provider values.

### AGENT-TD-7. No weak-retrieval refusal; citations not returned

**Severity:** Medium.

`prepare_main` passes whatever `/retrieve` returns. RRF scores are not thresholded, and vector search always returns neighbors, so off-topic questions get loosely related context. `citations` are stored in state but `/chat` does not return them, and the main prompt does not ask for `[n]` citations.

**Fix:** threshold on scores (or use rag `/answer`'s refusal), number the context blocks, and return citations in the `/chat` response.

### AGENT-TD-8. Router sees only the last message

**Severity:** Medium.

`classify_intent` classifies only the latest human message. "Can I get a refund for ORD-1001?" then "yes please" routes the second turn as chitchat or policy. The JSON is parsed by hand after stripping code fences.

**Fix:** pass the summary plus the last few turns, and use structured output (`with_structured_output`) for the classification.

### AGENT-TD-9. No recovery if Postgres is down at startup

**Severity:** Medium.

`MemoryBundle.start()` runs once in the lifespan. If it fails, `graph` stays `None` and every request returns 503 until the process restarts. There is no pool health check after startup either.

**Fix:** retry with backoff in the background and compile the graph when memory becomes ready; or fail the process so a supervisor restarts it.

### AGENT-TD-10. Summary message lands after the recent messages

**Severity:** Medium.

`summarize_if_needed` returns `[*removals, summary_msg]`. `add_messages` appends `summary_msg` at the end, after the kept recent messages, so the summary appears as the latest message. Some providers also reject a system message that is not first.

**Fix:** store the summary in `state.summary` only and prepend it in each node's prompt, rather than inserting it into `messages`.

### AGENT-TD-11. Planned fallback, escalation, and token cap are missing

**Severity:** Medium.

The design calls for retry-then-escalate on tool or model errors, a per-conversation token cap that escalates, and `escalate_to_human`. None exist: model errors in `cheap_agent`, `main_agent`, or `summarize` raise and return 500; `token_count` is tracked but not enforced; `escalate_to_human` is never called.

**Fix:** a `fallback` node reached on errors and on budget or step limit that calls `escalate_to_human` and replies with a hand-off message.

### AGENT-TD-12. Concurrent requests on one thread race

**Severity:** Low.

Two `/chat` calls (or a chat plus a resume) for the same `thread_id` can run at once and both write checkpoints.

**Fix:** a per-thread lock (in-process for one worker, Postgres advisory lock for many).

### AGENT-TD-13. Evals share production checkpoint tables

**Severity:** Low.

`/evals/run` writes `eval-*` threads into the same checkpointer as real traffic, and `e2e_ms_mean` is computed identically to `latency_ms_mean`. `run_evals.py` refund-safety cases with an `approval_id` call the live MCP `issue_refund`.

**Fix:** compile an eval graph with an in-memory saver, measure e2e separately or drop the field, and point evals at a disposable MCP.

### AGENT-TD-14. Small inefficiencies and misleading health output

**Severity:** Low.

- `main_agent` rebuilds the tool list and calls `bind_tools` on every step.
- Each MCP call opens a new session and handshake.
- `mcp_connection_hint()` reports `connected: true` without checking.
- Yes and no word lists are duplicated in `main.py` and `email.py` and differ (`ok` is only in `main.py`).
- Settings read only `apps/agent/.env`, not the root `.env` ([X-TD-7](../../architecture/tech-debt.md#x-td-7-inconsistent-env-loading)).

**Fix:** bind once at build time, reuse an MCP session, ping MCP in `/health`, and share one confirmation parser.
