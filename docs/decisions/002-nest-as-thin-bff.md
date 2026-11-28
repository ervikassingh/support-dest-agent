# 0002. NestJS is a thin BFF; it does not host MCP or implement RAG

- Status: Accepted
- Services: api, agent, rag, mcp-server

## Context

The browser needs one origin to call, with CORS, upload handling, and eventually sessions and auth. The agent and RAG services are Python and would otherwise be exposed directly to the browser.

## Decision

`apps/api` is a backend-for-frontend:

- `/chat` and `/approvals/:threadId` validate input and forward to the agent.
- `/documents` accepts uploads, asks rag to reserve a row and path, writes the bytes, and enqueues the ingest job.
- It holds no domain logic: no prompts, no retrieval, no tool calls, no order data.

MCP lives in its own service ([0003](0003-mcp-as-shared-http-service.md)). Retrieval lives in rag.

## Alternatives considered

- **Browser calls agent and rag directly.** One less hop, but puts CORS, auth, and upload limits into two Python services.
- **Nest hosts the MCP server.** Fewer processes, but couples tool availability to the UI's backend and blocks other agents from sharing tools without going through it.

## Consequences

- Auth and sessions have one place to land when they are built. They are not built yet ([X-TD-1](../../README.md#known-gaps)).
- Every chat turn pays an extra hop. Negligible next to model latency.
- Nest maps agent and rag failures to HTTP errors for the UI. Agent 4xx errors keep their status and detail; 5xx and unreachable become 503.
