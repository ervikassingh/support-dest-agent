# mcp-server flows

## Tool call

```mermaid
sequenceDiagram
  participant C as MCP client (agent)
  participant E as Express /mcp
  participant H as createMcpHandler
  participant S as McpServer (factory)
  participant D as data.ts (module state)
  C->>E: POST /mcp initialize
  E->>H: node handler
  H->>S: createSupportDeskMcpServer()
  S-->>C: capabilities, tools
  C->>E: tools/call {name, arguments}
  E->>H: handle
  H->>S: zod-validate arguments, run tool
  S->>D: read or mutate ORDERS / REFUNDS
  S-->>C: content [{type: text, text: JSON}]
```

The agent opens a new session for every tool call (initialize, call, close). Arguments that fail the zod schema are rejected by the SDK before the tool runs.

## Refund eligibility

```mermaid
flowchart TD
  start([check_refund_eligibility order_id]) --> found{Order exists?}
  found -->|no| nf[eligible false: not found]
  found -->|yes| ref{already_refunded?}
  ref -->|yes| r1[eligible false: already refunded + prior_refund_id]
  ref -->|no| tr{status == in_transit?}
  tr -->|yes| r2[eligible false: still in transit]
  tr -->|no| win{note == 'outside return window stub'?}
  win -->|yes| r3[eligible false: outside return window]
  win -->|no| ok[eligible true, max_amount = order total]
```

All ineligible results have `max_amount: 0`.

## `issue_refund`

```mermaid
flowchart TD
  call([issue_refund order_id, amount, approval_id?, reason?]) --> aid{approval_id non-blank?}
  aid -->|no| e1["error: refused, missing approval_id"]
  aid -->|yes| elig[check_refund_eligibility]
  elig --> ok{eligible?}
  ok -->|no| e2[error: eligibility reason]
  ok -->|yes| amt{0 < amount ≤ max_amount?}
  amt -->|no| e3[error: amount outside eligible max]
  amt -->|yes| post["REFUNDS[REF-xxxx] = record<br/>order.already_refunded = true<br/>order.prior_refund_id = REF-xxxx"]
  post --> ret([refund record, status posted])
```

Because a posted refund sets `already_refunded`, a second call for the same order fails eligibility. That is the only protection against double refunds.

## `escalate_to_human`

Returns `{escalated: true, thread_id, summary, queue: "human-support-stub"}`. Nothing is stored or notified. The agent does not call it today.
