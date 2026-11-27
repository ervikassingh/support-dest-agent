# mcp-server tech debt

Severity levels are defined in [architecture/tech-debt.md](../../architecture/tech-debt.md). Missing auth is [X-TD-1](../../architecture/tech-debt.md#x-td-1-no-authentication-or-authorization-anywhere); the `CUS-` vs `CUST-` id mismatch is [X-TD-2](../../architecture/tech-debt.md#x-td-2-customer-id-format-disagrees-between-agent-and-mcp-server).

| ID | Item | Severity |
| --- | --- | --- |
| MCP-TD-1 | `approval_id` is checked for presence, not validity | High |
| MCP-TD-2 | Data is in-memory and resets on restart | Medium |
| MCP-TD-3 | Return-window eligibility is a magic string, not date math | Medium |
| MCP-TD-4 | Errors are indistinguishable from success at the protocol level | Low |
| MCP-TD-5 | Refunds are all-or-nothing, with no idempotency key | Low |
| MCP-TD-6 | `escalate_to_human` is a no-op | Low |
| MCP-TD-7 | No tests | Low |

### MCP-TD-1. `approval_id` is checked for presence, not validity

**Severity:** High.

`issue_refund` accepts any non-blank string as `approval_id`. Any client that can reach `/mcp` can issue a refund for any eligible order up to its total. Read and write tools are on the same endpoint with no per-client scopes.

**Fix:** verify `approval_id` against an approval record (created by api when an operator decides, see [AGENT-TD-5](../agent/tech-debt.md)) that matches order id and amount and is single-use. Expose write tools only to clients with a write-scoped token.

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
