# mcp-server tech debt

Severity levels are defined in [architecture/tech-debt.md](../../architecture/tech-debt.md). Missing auth is [X-TD-1](../../architecture/tech-debt.md#x-td-1-no-authentication-or-authorization-anywhere).

| ID | Item | Severity |
| --- | --- | --- |
| MCP-TD-1 | Refund signatures fall back to a secret in source | Medium |
| MCP-TD-2 | Data is in-memory and resets on restart | Medium |
| MCP-TD-3 | Return-window eligibility is a magic string, not date math | Medium |
| MCP-TD-4 | Errors are indistinguishable from success at the protocol level | Low |
| MCP-TD-5 | Refunds are all-or-nothing, with no idempotency key | Low |
| MCP-TD-6 | `escalate_to_human` is a no-op | Low |
| MCP-TD-7 | No tests | Low |

### MCP-TD-1. Refund signatures fall back to a secret in source

**Severity:** Medium.

`issue_refund` accepts `approval_id` only when it is the HMAC of `order_id` and the amount in cents. With `APPROVAL_SECRET` unset, both this service and the agent use `dev-approval-secret`, so anyone who can read the repo and reach `/mcp` can sign a refund. The signature is not an operator record ([AGENT-TD-5](../agent/tech-debt.md)).

**Fix:** set `APPROVAL_SECRET` on both processes before exposing MCP. Keep operator identity on AGENT-TD-5.

### MCP-TD-2. Data is in-memory and resets on restart

**Severity:** Medium.

`ORDERS`, `CUSTOMERS`, and `REFUNDS` live in `data.ts`. Posted refunds disappear on restart, and a refunded order becomes refundable again. Only four orders exist; the planned 20–30 edge cases (partial shipment, missing tracking, two open orders, high-value) are not there. `data/README.md` describes the planned SQLite or Postgres store.

**Fix:** move to a seeded database under `data/` (SQLite is enough for the demo), and keep `data.ts` as the seed source.

### MCP-TD-3. Return-window eligibility is a magic string, not date math

**Severity:** Medium.

`checkRefundEligibility` marks ORD-1003 ineligible because `note === "outside return window (stub)"`. `return_window_days` and `delivered_at` are present but unused, so every other delivered order is eligible forever.

**Fix:** eligible when `now - delivered_at ≤ return_window_days`, with an injectable clock for tests.

### MCP-TD-4. Errors are indistinguishable from success at the protocol level

**Severity:** Low.

Errors are returned as normal text content with no `isError: true`. Clients and tracing cannot count tool failures without parsing JSON.

**Fix:** keep the JSON error body for the model and also set `isError: true`.

### MCP-TD-5. Refunds are all-or-nothing, with no idempotency key

**Severity:** Low.

Any posted refund sets `already_refunded`, so a partial refund blocks any further refund on the order. `currency` is ignored. Double-posting is prevented only by that flag; there is no idempotency key, so a client retry after a lost response gets an "already refunded" error instead of the original record.

**Fix:** track refunded amount per order (max = total − refunded), and accept an idempotency key (the `approval_id` would do) that returns the existing record.

### MCP-TD-6. `escalate_to_human` is a no-op

**Severity:** Low.

It echoes its input and stores nothing. The agent never calls it.

**Fix:** persist escalations to a queue or table that operators can see, and wire the agent's fallback path to it ([AGENT-TD-11](../agent/tech-debt.md)).

### MCP-TD-7. No tests

**Severity:** Low.

`lint` is `tsc --noEmit`. Eligibility rules and the `issue_refund` guards have no tests ([X-TD-3](../../architecture/tech-debt.md#x-td-3-no-ci-and-thin-test-coverage)).

**Fix:** unit tests for `data.ts` and an in-process MCP client test for each tool.
