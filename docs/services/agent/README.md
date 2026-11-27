# agent

Python FastAPI service on `:8000` that runs the support conversation as one LangGraph `StateGraph`. It routes each message, answers with RAG context or MCP read tools, and pauses refunds and emails with `interrupt()` until a human decides. Checkpoints and operator memory are in Postgres.

## Endpoints

| Method | Path | Does |
| --- | --- | --- |
| GET | `/health` | `ok` when Postgres memory is ready and the graph compiled, else `degraded`. Reports model ids, RAG URL, MCP URL |
| POST | `/chat` | Body `{message, threadId?}`. Runs one turn, or resumes an open email interrupt. Returns `{reply, threadId, status: ok\|interrupted, interrupt?}` |
| POST | `/threads/{thread_id}/resume` | Body `{decision: approve\|edit\|reject, amount?, note?}`. Resumes a `refund_approval` interrupt only. 404 if nothing is paused, 400 if paused for something else |
| POST | `/evals/run` | Body `{n=5, k=5}`. Runs `evals/tool_tasks.json` through the live graph and returns tool-call accuracy, pass@1, pass@k, pass^k, latency, tokens, cost |

All endpoints except `/health` return 503 if the graph did not compile.

## Layout

```
src/agent/
  main.py                FastAPI app, lifespan (memory + graph), endpoints
  settings.py            pydantic-settings (reads apps/agent/.env)
  clients.py             RAG /retrieve client, MCP connection hint
  graph/
    build.py             Nodes and edges; compile with checkpointer + store
    state.py             AgentState TypedDict, Intent literal
    nodes/
      summarize.py       Context-window summarization
      router.py          route_intent, after_router
      cheap.py           Cheap model, no tools
      main_agent.py      prepare_main (RAG), main_agent, after_main (step limit 8)
      refund.py          load memory, draft, interrupt, issue + write memory
      email.py           draft, interrupt, stub send
  routing/intent.py      LLM classifier with keyword fallback, id extraction
  models/factory.py      ChatOpenAI clients pointed at OpenRouter (cheap, main)
  tools/
    registry.py          Tools bound to the main model (MCP reads only)
    mcp/client.py        One Streamable HTTP session per tool call
    mcp/adapters.py      LangChain StructuredTools for reads; issue_refund wrapper
    local/send_email.py  Stub send; refuses without confirmation_id
  memory/postgres.py     MemoryBundle (AsyncPostgresSaver + AsyncPostgresStore), refund notes
  evals_runner.py        /evals/run implementation
  evals_metrics.py       pass@k, pass^k
evals/
  dataset.json           Routing, refund_safety, email_safety cases
  tool_tasks.json        Tool-call tasks for /evals/run
  run_evals.py           CLI runner, optional LangSmith upload
tests/test_evals_metrics.py
```

## State

`AgentState` (`graph/state.py`):

| Field | Holds |
| --- | --- |
| `messages` | Conversation, merged with `add_messages` |
| `intent` | `chitchat`, `policy`, `order`, `refund`, `email`, `out_of_scope` |
| `order_id`, `customer_id` | Extracted by the router; carried across turns |
| `documents`, `citations` | RAG results for the current policy turn |
| `refund_draft`, `refund_memory`, `approval` | Refund branch data and the operator decision |
| `email_draft`, `email_confirmed` | Email branch data |
| `step_count` | Main-agent model calls this turn (limit 8) |
| `token_count`, `summary` | Estimated tokens and running summary |
| `interrupt_kind` | `none`, `refund`, `email`; summarization skips while not `none` |
| `final_reply` | Text returned to the caller |

## Dependencies

| Depends on | For | If down |
| --- | --- | --- |
| Postgres | Checkpoints and store | Graph not compiled; 503 until restart |
| OpenRouter | All model calls | Router falls back to keywords; other nodes raise |
| rag `POST /retrieve` | Policy context | Empty context; model says it has no policy |
| mcp-server `/mcp` | Order tools, `issue_refund` | Tool returns `{"error": ...}` to the model |
| LangSmith | Tracing (optional) | No traces |

## Config

| Variable | Default |
| --- | --- |
| `PORT` | `8000` |
| `RAG_URL` | `http://localhost:8001` |
| `MCP_URL` | `http://localhost:8002/mcp` |
| `DATABASE_URL` | `postgresql://support:support@localhost:5432/support_desk` |
| `OPENROUTER_API_KEY`, `OPENROUTER_BASE_URL` | —, `https://openrouter.ai/api/v1` |
| `CHEAP_MODEL`, `MAIN_MODEL` | `openai/gpt-4o-mini`, `anthropic/claude-haiku-4.5` |
| `CONTEXT_TOKEN_BUDGET`, `SUMMARIZE_THRESHOLD_RATIO`, `KEEP_RECENT_MESSAGES` | `128000`, `0.7`, `8` |
| `EMAIL_PROVIDER` | `stub` (only option wired) |
| `LANGSMITH_TRACING`, `LANGSMITH_API_KEY`, `LANGSMITH_PROJECT` | `false`, —, `support-desk-agent` |
| `CHAT_INPUT_USD_PER_MILLION`, `CHAT_OUTPUT_USD_PER_MILLION` | unset (eval cost is `null`) |

## Run

```bash
docker compose up -d postgres
pnpm dev:agent                    # uvicorn --reload on :8000
cd apps/agent && poetry run python evals/run_evals.py
curl -XPOST localhost:8000/evals/run -H 'content-type: application/json' -d '{"n":5,"k":5}'
```

## See also

- [flow.md](flow.md) · [decisions.md](decisions.md) · [tech-debt.md](tech-debt.md)
- [ADR 0007: write tools gated by interrupt](../../architecture/decisions/0007-write-tools-gated-by-interrupt.md)
- [ADR 0008: Postgres checkpointer and store](../../architecture/decisions/0008-postgres-checkpointer-and-store.md)
