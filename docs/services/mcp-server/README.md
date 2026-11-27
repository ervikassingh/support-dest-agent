# mcp-server

TypeScript MCP tool server on `:8002`, speaking Streamable HTTP at `/mcp`. It owns order, customer, and refund tools for this agent and any other MCP client ([ADR 0003](../../architecture/decisions/0003-mcp-as-shared-http-service.md)). Data is in-memory stubs today.

## HTTP

| Method | Path | Does |
| --- | --- | --- |
| GET | `/health` | `{status, service, transport: "streamable-http", mcp_path: "/mcp"}` |
| ALL | `/mcp` | MCP Streamable HTTP endpoint |

The Express app comes from `createMcpExpressApp`, with a `Host` header allowlist of `localhost`, `127.0.0.1`, `mcp-server`, `mcp`.

## Tools

| Tool | Kind | Input | Returns |
| --- | --- | --- | --- |
| `get_order` | read | `{order_id}` | Order: items, totals, status, shipping, refund flags |
| `get_shipping_status` | read | `{order_id}` | `status`, `carrier_status`, `tracking`, `shipped_at`, `delivered_at` |
| `check_refund_eligibility` | read | `{order_id}` | `{eligible, reason, max_amount, prior_refund_id?}` |
| `get_customer` | read | `{customer_id}` | Name, email, `recent_order_ids` |
| `issue_refund` | write, scoped | `{order_id, amount, approval_id?, reason?}` | Refund record `REF-<8 hex>` with `status: posted` |
| `escalate_to_human` | write | `{thread_id, summary}` | `{escalated: true, queue: "human-support-stub"}` |

Every tool returns one text block of pretty-printed JSON. Errors are `{"error": "..."}` in the same shape.

## Stub data (`src/data.ts`)

| Order | Customer | State | Eligible |
| --- | --- | --- | --- |
| `ORD-1001` | `CUS-1` | Delivered, $49.99 | Yes, up to $49.99 |
| `ORD-1002` | `CUS-2` | In transit, $129.00 | No: still in transit |
| `ORD-1003` | `CUS-1` | Delivered Sept, $899.00 | No: outside return window |
| `ORD-1004` | `CUS-GUEST` | Delivered, $24.00, refunded `REF-9` | No: already refunded |

`ORDERS`, `CUSTOMERS`, and `REFUNDS` are module-level objects, so every MCP session in the process shares them. Reads return `structuredClone` copies. A restart resets everything.

## Layout

```
src/
  index.ts           Express app, /health, /mcp → createMcpHandler(factory)
  create-server.ts   McpServer factory; tool registration with zod schemas
  data.ts            Types, stub data, getOrder, getCustomer, checkRefundEligibility
```

## Config

| Variable | Default |
| --- | --- |
| `PORT` | `8002` |
| `HOST` | `0.0.0.0` |

## Run

```bash
pnpm dev:mcp                                    # tsx watch
pnpm --filter mcp-server build && pnpm --filter mcp-server start
curl localhost:8002/health
```

## See also

- [flow.md](flow.md) · [decisions.md](decisions.md) · [tech-debt.md](tech-debt.md)
