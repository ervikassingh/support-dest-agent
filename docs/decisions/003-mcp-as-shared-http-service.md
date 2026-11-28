# 0003. Tools live in a standalone MCP server over Streamable HTTP

- Status: Accepted
- Services: mcp-server, agent

## Context

The agent needs order, customer, and refund tools. Other agents should be able to use the same tools without importing this agent's code. The tool implementations will eventually own a real orders database.

## Decision

- `apps/mcp-server` is a long-lived TypeScript process serving MCP over Streamable HTTP at `:8002/mcp`, with `GET /health`.
- The agent is an MCP client. It never talks to the orders data directly.
- Read tools (`get_order`, `get_shipping_status`, `check_refund_eligibility`, `get_customer`) and write tools (`issue_refund`, `escalate_to_human`) are labeled in their descriptions. `issue_refund` refuses calls without an `approval_id`.

## Alternatives considered

- **stdio MCP spawned by the agent.** No network hop, but one server per client process, so no shared state and no sharing with other agents.
- **Plain REST tools.** Simpler, but every client would need custom adapters, and MCP-native clients could not discover the tools.
- **LangChain tools in the agent process.** Fastest to build, but ties tool code and data to Python and to this one agent.

## Consequences

- Tool data is shared across all clients because it lives at module scope in the server process.
- `issue_refund` checks an HMAC of the order id and amount (`APPROVAL_SECRET`), not an operator record. With the default secret, anyone who can read the repo and reach `/mcp` can still sign one ([MCP-TD-1](../services/mcp-server.md#known-gaps)).
- The agent duplicates each tool's name, description, and schema in `agent/tools/mcp/adapters.py` instead of discovering them via `list_tools`, so the two can drift.
