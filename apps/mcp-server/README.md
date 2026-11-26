# mcp-server

TypeScript MCP service for order, customer, and refund tools. Long-lived **Streamable HTTP** on port **8002** so any agent can be a client — not only this repo’s orchestrator.

Nest does not speak MCP. The Python agent (and other agents) connect to:

```
http://localhost:8002/mcp
```

## Run

```bash
pnpm --filter mcp-server dev
# or from repo root:
pnpm dev:mcp
```

## Tools

| Tool | Scope | Notes |
| --- | --- | --- |
| `get_order` | read | |
| `get_shipping_status` | read | |
| `check_refund_eligibility` | read | |
| `get_customer` | read | |
| `issue_refund` | write, scoped | Refuses without `approval_id` |
| `escalate_to_human` | write | |

Stub orders live in `src/data.ts` (shared process memory).
