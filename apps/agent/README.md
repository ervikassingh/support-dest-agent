# Agent orchestrator

Python FastAPI + LangGraph service. NestJS proxies chat and approvals here.

## Layout

```
src/agent/
  main.py                 # FastAPI /chat, /resume, /health
  settings.py
  clients.py              # RAG HTTP
  graph/                  # StateGraph build + nodes
  routing/                # Intent classifier (cheap model)
  models/                 # OpenRouter clients (cheap + main model ids)
  tools/
    local/                # send_email stub (confirmation_id required)
    mcp/                  # MCP read adapters; issue_refund gated
    registry.py           # Main-agent tools (reads only)
  memory/                 # PostgresSaver + PostgresStore
evals/                    # LangSmith-oriented minimal suite
```

## Endpoints

- `GET /health`
- `POST /chat` — run graph; email HITL confirms via next chat message (`yes`/`no`)
- `POST /threads/{id}/resume` — operator refund approve/edit/reject

## Requirements

- Postgres up (`docker compose up -d postgres`) — required for checkpointer + store
- `OPENROUTER_API_KEY` — cheap and main agents are OpenRouter model ids (`CHEAP_MODEL`, `MAIN_MODEL`)
- MCP on `:8002` for order tools (soft-fails if down)

## Run

```bash
cd apps/agent
cp -n .env.example .env   # fill keys
poetry run uvicorn agent.main:app --reload --port 8000
```

## Evals

```bash
poetry run python evals/run_evals.py
```
