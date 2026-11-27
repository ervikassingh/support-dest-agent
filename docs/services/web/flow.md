# web flows

## Chat

```mermaid
sequenceDiagram
  actor U as Customer
  participant P as ChatPage (page.tsx)
  participant A as api
  U->>P: type message, Enter
  P->>P: append user bubble, status "Sending…"
  P->>A: POST /chat {message, threadId}
  alt 2xx
    A-->>P: {reply, threadId, status}
    P->>P: store threadId, append reply, set status
    opt status == "interrupted"
      P->>U: show "Review on Approvals" link (/approvals?threadId=...)
    end
  else error
    P->>P: append "Could not reach API ..." bubble, status = error text
  end
```

- The first message sends `threadId: null`. The agent creates `thread-<hex>` and every later message reuses it.
- Messages and the thread id live only in React state. A page reload starts a new thread on the client, though the old thread still exists in the agent's checkpoint.
- Email confirmation happens in this same chat: the agent asks for **yes** or **no**, and the next message resumes the interrupt.
- A pending refund shows `status: "interrupted"` and the Approvals link. Further chat messages get a "waiting for operator approval" reply until it is resolved.

## Approvals

```mermaid
sequenceDiagram
  actor O as Operator
  participant F as ApprovalsForm
  participant A as api
  O->>F: open /approvals?threadId=...
  F->>F: prefill threadId from query
  O->>F: choose approve | edit (+amount) | reject, optional note
  F->>A: POST /approvals/:threadId {decision, amount?, note?}
  A-->>F: {status, message, threadId, approval}
  F->>O: banner with message or "Failed: API <code>"
```

The form does not load or show the refund draft (order, amount, eligibility). The operator sees only what the chat transcript showed.

## Documents

```mermaid
flowchart TD
  mount([Mount / documents count or message changes]) --> tick[GET /documents]
  tick --> any{Any row queued, parsing, or embedding?}
  any -->|yes| wait[setTimeout 2 s] --> tick
  any -->|no| idle([Stop polling])
  submit([Submit form]) --> which{File or URL?}
  which -->|file| multipart[POST /documents multipart 'file']
  which -->|url| json[POST /documents JSON url]
  multipart --> refresh[GET /documents, show 'Queued for ingest.']
  json --> refresh
```

Client-side checks: exactly one of file or URL. File input accepts `.pdf,.docx,.md,.txt,.html,.htm`. The 20 MB limit is enforced by api.
