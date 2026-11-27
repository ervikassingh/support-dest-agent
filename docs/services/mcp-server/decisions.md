# mcp-server decisions

System-wide decisions are in [architecture/decisions](../../architecture/decisions/README.md). The main one for this service is [0003: MCP as a shared HTTP service](../../architecture/decisions/0003-mcp-as-shared-http-service.md).

## MCP-1. Server instance per handler call, data at module scope

**Decision.** `index.ts` passes a factory to `createMcpHandler`, so server instances are built by the SDK on demand. Orders, customers, and refunds are module-level objects in `data.ts`.

**Consequences.** No session state to manage in the server. All clients see the same data, including refunds posted by another client. Scaling to more than one process requires moving data to a database first.

## MCP-2. Tool errors are JSON text, not protocol errors

**Context.** The model should be able to read and repeat a failure to the customer.

**Decision.** Tools return `{"error": "..."}` as normal text content. They do not throw and do not set the MCP `isError` flag.

**Consequences.** Errors look like data to the model, which is the intent. Clients cannot distinguish failure from success without parsing the JSON ([MCP-TD-4](tech-debt.md)).

## MCP-3. `approval_id` presence and server-side eligibility as the write guard

**Context.** The agent already gates refunds behind a human ([ADR 0007](../../architecture/decisions/0007-write-tools-gated-by-interrupt.md)). The server should not trust any single client.

**Decision.** `issue_refund` accepts `approval_id` only when it is the HMAC of the order id and the amount in cents, and it re-runs `check_refund_eligibility` and the `0 < amount ≤ max_amount` bound itself.

**Consequences.** A buggy client cannot over-refund, refund an ineligible order, or pass an invented `approval_id`. MCP recomputes the HMAC of the order id and the amount. The default secret is still in source ([MCP-TD-1](tech-debt.md)).

## MCP-4. Strict zod input schemas

**Decision.** Each tool declares a `zod/v4` object schema. Only `approval_id` and `reason` on `issue_refund` are optional.

**Consequences.** Malformed calls fail before tool code runs, and schemas are advertised to clients. The agent still hand-copies the schemas in its LangChain adapters.

## MCP-5. Host header allowlist instead of auth

**Decision.** `createMcpExpressApp` with `allowedHosts: localhost, 127.0.0.1, mcp-server, mcp`, which protects against DNS rebinding from a browser.

**Consequences.** Fine on a developer machine. It is not authentication: any process that can reach the port with an allowed `Host` header can call every tool ([X-TD-1](../../architecture/tech-debt.md#x-td-1-no-authentication-or-authorization-anywhere)).
