# 0008. LangGraph PostgresSaver + PostgresStore for durable runs and operator memory

- Status: Accepted
- Services: agent

## Context

A refund approval can wait hours or days, across agent restarts. The agent also needs to remember what operators decided for a customer before, across threads.

## Decision

- `AsyncPostgresSaver` checkpoints every thread, keyed by `thread_id`. Interrupts are stored in the checkpoint, so `/threads/{id}/resume` works after a restart.
- `AsyncPostgresStore` holds operator refund notes under namespace `("refunds", "operator")`, key = customer id, value `{"notes": [...]}` capped at the last 50.
- Both are opened once in the FastAPI lifespan (`agent/memory/postgres.py`) and `setup()` creates their tables. If Postgres is down at startup, the graph is not compiled and `/chat` returns 503.

## Alternatives considered

- **In-memory saver.** No infra, but loses every paused approval on restart, which defeats the HITL design.
- **Redis checkpointer.** Already running for BullMQ, but persistence settings would matter, and the store and checkpoints are better kept with other durable data.
- **SQLite saver.** Fine for one process, but not shared if the agent scales out.

## Consequences

- Durable HITL works across restarts.
- No reconnect: if Postgres starts after the agent, the agent must be restarted ([AGENT-TD-9](../../services/agent/tech-debt.md)).
- Eval runs (`POST /evals/run`) write checkpoints into the same tables as real traffic, under `eval-*` thread ids.
- Threads are never pruned.
- Notes are not written when the customer id is unknown.
