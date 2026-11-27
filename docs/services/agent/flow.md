# agent flows

One graph, compiled in `graph/build.py` with `AsyncPostgresSaver` (thread checkpoints) and `AsyncPostgresStore` (operator refund notes). The cheap model has no tools. The main model is bound to MCP read tools only. Write tools (`issue_refund`, `send_email`) are called from graph nodes, never by the model.

## Graph

```mermaid
flowchart TD
  startNode([POST /chat]) --> summarize["summarize<br/>if est. tokens ≥ 70% of budget<br/>skipped while an interrupt is open"]
  summarize --> router["router · CHEAP_MODEL<br/>keyword fallback on error"]

  router -->|chitchat, out_of_scope| cheap["cheap_agent · no tools"]
  router -->|policy, order| prepare["prepare_main<br/>RAG /retrieve if policy"]
  router -->|refund| loadMem["load_refund_memory<br/>PostgresStore"]
  router -->|email| draftEmail[draft_email]

  cheap --> respond[respond]
  prepare --> main["main_agent · MAIN_MODEL"]
  main -->|tool calls and step_count < 8| tools["tools (ToolNode)<br/>get_order, get_shipping_status,<br/>check_refund_eligibility, get_customer"]
  tools --> main
  main -->|step limit with tool calls still open| stop["stop_tool_loop<br/>close tool calls, ask for a person"]
  stop --> respond
  main -->|no tool calls| respond

  loadMem --> draftRefund["draft_refund<br/>MCP check_refund_eligibility"]
  draftRefund -->|no order, error, or ineligible| respond
  draftRefund -->|eligible| awaitRefund["await_refund_approval<br/>interrupt type=refund_approval"]
  awaitRefund --> issue["issue_refund<br/>MCP issue_refund or skip on reject<br/>append PostgresStore note"]
  issue --> respond

  draftEmail --> awaitEmail["await_email_confirm<br/>interrupt type=email_confirm"]
  awaitEmail --> send["send_email<br/>stub; needs confirmation_id"]
  send --> respond

  respond --> endNode([END])

  saver[(PostgresSaver)] -.-> startNode
  saver -.-> awaitRefund
  saver -.-> awaitEmail
```

## `/chat` request handling

`main.py` checks for an open interrupt before running the graph:

```mermaid
flowchart TD
  req([POST /chat]) --> tid[thread_id = body.threadId or new thread-hex]
  tid --> snap[aget_state]
  snap --> paused{snapshot.next?}
  paused -->|no| run[ainvoke with HumanMessage]
  paused -->|yes, email_confirm| yn{message is yes-like or no-like?}
  yn -->|neither| wait[Reply 'waiting for you to confirm', status interrupted]
  yn -->|yes or no| resumeE["ainvoke Command(resume={confirmed})"]
  paused -->|yes, refund_approval| block[Reply 'waiting for operator approval', status interrupted]
  run --> after[aget_state: still paused?]
  after --> out([reply, threadId, status ok or interrupted, interrupt payload])
  resumeE --> out2([reply, threadId, status ok])
```

Yes-like: `yes, y, confirm, approve, send, ok, okay`. No-like: `no, n, cancel, reject, stop`.

## Refund branch

```mermaid
sequenceDiagram
  participant C as Customer (/chat)
  participant G as Graph
  participant S as PostgresStore
  participant M as mcp-server
  participant O as Operator (/threads/:id/resume)
  C->>G: "refund ORD-1001"
  G->>M: get_order, if the message has no customer id
  G->>S: read notes for that customer (skip if unknown)
  G->>M: check_refund_eligibility(order_id)
  G->>G: draft {order_id, amount = max_amount, reason, eligibility, notes}
  G-->>C: "Refund draft ready ... paused for operator approval"
  Note over G: interrupt(refund_approval) checkpointed
  C->>G: any message
  G-->>C: "waiting for operator approval" (no resume)
  O->>G: {decision, amount?, note?}
  alt reject
    G->>S: append refund_rejected
    G-->>O: "Refund request rejected by operator."
  else approve or edit
    G->>G: approval_id = HMAC(order_id, amount)
    G->>M: issue_refund(order_id, amount, approval_id, reason)
    G->>S: append refund_issued or refund_failed
    G-->>O: "Refund issued ..." or "Could not issue refund: ..."
  end
```

`edit` uses the operator's `amount`; `approve` uses the drafted amount. MCP checks the HMAC, then enforces `0 < amount ≤ max_amount` and eligibility again.

No order id, an eligibility error, or an ineligible order ends the turn with an explanation. Those paths do not interrupt.

## Email branch

1. `draft_email` builds a fixed template to `customer@example.com`, mentions `order_id` if known, and asks for **yes** or **no**.
2. `await_email_confirm` interrupts with `type: email_confirm`.
3. The next `/chat` message resumes it (see above).
4. `send_email` cancels on no. On yes it mints `EMC-hex` and calls the stub, which logs and returns `status: stubbed`.

## Policy and order turns

- `prepare_main` resets `step_count` to 0. For `policy`, it sends the last human message to rag `POST /retrieve` (`top_k=5`) and stores each chunk's `embed_text` plus a metadata line in `documents`.
- `main_agent` puts the documents into the system prompt, binds the four read tools, and calls `MAIN_MODEL`. If the response has no tool calls it becomes `final_reply`.
- `ToolNode` runs the tool calls. Each MCP call opens its own Streamable HTTP session.
- `after_main` loops back while there are tool calls and `step_count < 8`. At the limit, `stop_tool_loop` writes a `ToolMessage` for each open call and sets the reply. Each turn also clears `final_reply` in the router so an older reply cannot leak through.

## Summarization

Before routing, `summarize_if_needed` estimates tokens as `len(content) // 4` per message. At or above `CONTEXT_TOKEN_BUDGET × SUMMARIZE_THRESHOLD_RATIO` (89,600 by default) and with more than `KEEP_RECENT_MESSAGES + 1` messages, it summarizes the older messages with the cheap model, removes them, and adds a `[Conversation summary]` system message. It does nothing while `interrupt_kind` is `refund` or `email`.

## Evals

| Runner | What | Needs |
| --- | --- | --- |
| `poetry run python evals/run_evals.py` | `dataset.json`: routing (via `classify_intent`), refund safety (calls MCP `issue_refund`), email safety (calls `send_email`) | Model key; MCP for refund cases with an `approval_id` |
| `POST /evals/run` | `tool_tasks.json` through the full graph, `n` runs each; checks the expected tool and args appear | Postgres, model key, MCP |
