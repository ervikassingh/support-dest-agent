# Architecture decision records

System-wide decisions that affect more than one service. Service-local decisions live in each service's `decisions.md`.

| # | Decision | Status |
| --- | --- | --- |
| [0001](0001-polyglot-monorepo.md) | Turborepo + Poetry monorepo; Python only for agent and rag | Accepted |
| [0002](0002-nest-as-thin-bff.md) | NestJS is a thin BFF; it does not host MCP or implement RAG | Accepted |
| [0003](0003-mcp-as-shared-http-service.md) | Tools live in a standalone MCP server over Streamable HTTP | Accepted |
| [0004](0004-openrouter-single-model-gateway.md) | OpenRouter is the only model gateway | Accepted |
| [0005](0005-paradedb-single-postgres.md) | One ParadeDB Postgres for vectors, BM25, and agent checkpoints | Accepted |
| [0006](0006-bullmq-ingest-queue.md) | Document ingest runs as BullMQ jobs on Redis | Accepted |
| [0007](0007-write-tools-gated-by-interrupt.md) | Write tools are never bound to the model; they run only after a LangGraph interrupt | Accepted |
| [0008](0008-postgres-checkpointer-and-store.md) | LangGraph `PostgresSaver` + `PostgresStore` for durable runs and operator memory | Accepted |

## Writing a new ADR

Copy the template to `NNNN-short-title.md` with the next number. Keep it to one page. Do not edit an accepted ADR to change the decision; write a new one that supersedes it and update the old one's status.

```markdown
# NNNN. Title

- Status: Proposed | Accepted | Superseded by NNNN
- Date: YYYY-MM-DD
- Services: web, api, agent, rag, mcp-server

## Context
What forces the decision. Constraints, requirements, what hurts today.

## Decision
What we chose, stated plainly.

## Alternatives considered
Each option and why it lost.

## Consequences
What gets easier, what gets harder, and what follow-up work this creates.
```
