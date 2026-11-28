# Chat flow

How one customer message travels from the browser to the agent and back. The graph itself is on the [agent](../services/agent.md#langgraph) page. Paused runs are in [Human in the loop](human-in-the-loop.md).

## End to end

```mermaid
sequenceDiagram
  actor U as Customer
  participant W as web
  participant A as api
  participant G as agent
  participant R as rag
  participant M as mcp-server
  participant P as Postgres
  U->>W: type message
  W->>A: POST /chat {message, threadId?}
  A->>G: POST /chat
  G->>P: load checkpoint (thread_id)
  G->>G: summarize → router (cheap model)
  alt chitchat or out_of_scope
    G->>G: cheap model replies, no tools
  else policy
    G->>R: POST /retrieve
    R-->>G: chunks + citations
    G->>G: main model answers from context
  else order
    loop up to 8 steps
      G->>M: read tool (get_order, ...)
      M-->>G: JSON result
    end
  else refund or email
    G->>G: draft, then interrupt()
  end
  G->>P: write checkpoint
  G-->>A: {reply, threadId, status, interrupt?}
  A-->>W: same body
  W->>U: reply, plus Approvals link if interrupted
```

The first message sends no `threadId`; the agent creates `thread-<hex>` and every later message reuses it.

## A thread that is already paused

Before running the graph, `/chat` checks whether the thread is waiting on an interrupt:

```mermaid
flowchart TD
  req([POST /chat]) --> snap[Load thread state]
  snap --> paused{Paused?}
  paused -->|no| run[Run the graph with the message]
  paused -->|email_confirm| yn{yes-like or no-like?}
  yn -->|neither| wait[Reply: waiting for you to confirm]
  yn -->|yes or no| resumeE[Resume the email branch]
  paused -->|refund_approval| block[Reply: waiting for operator approval]
```

A customer can confirm their own email, but can never resume a refund from chat. Only the operator endpoint can.

## Errors

- If the agent returns non-2xx or is unreachable, api returns 503 to the browser (including the agent's 404 and 400 on resume).
- If rag is down, the policy turn gets empty context and the model says it has no policy.
- If mcp-server is down, the tool returns `{"error": ...}` to the model, which tells the customer.
- If OpenRouter fails, the router falls back to keywords; other nodes raise and the turn fails.
