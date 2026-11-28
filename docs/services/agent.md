# agent

Python FastAPI service on `:8000` that runs each conversation as one LangGraph `StateGraph`. It routes every message, answers from RAG context or MCP read tools, and pauses refunds and emails with `interrupt()` until a human decides. Thread checkpoints and operator notes live in Postgres, so a paused run survives restarts.

Code: `apps/agent/src/agent/`. Graph in `graph/build.py`, nodes in `graph/nodes/`, routing in `routing/intent.py`, MCP adapters in `tools/mcp/`.

## Endpoints

| Method | Path | Does |
| --- | --- | --- |
| GET | `/health` | `ok` when Postgres memory is ready and the graph compiled, else `degraded` |
| POST | `/chat` | `{message, threadId?}`. Runs one turn, or resumes an open email confirmation. Returns `{reply, threadId, status: ok\|interrupted, interrupt?}` |
| POST | `/threads/{id}/resume` | `{decision: approve\|edit\|reject, amount?, note?}`. Resumes a paused refund only. 404 if nothing is paused, 400 if paused for email |
| POST | `/evals/run` | `{n=5, k=5}`. Tool-call eval through the live graph |

Everything except `/health` returns 503 if the graph did not compile.

## LangGraph

```mermaid
flowchart TD
  startNode([POST /chat]) --> summarize["summarize<br/>if est. tokens ≥ 70% of budget<br/>skipped while an interrupt is open"]
  summarize --> router["router · CHEAP_MODEL<br/>keyword fallback on error"]

  router -->|chitchat, out_of_scope| cheap["cheap_agent · no tools"]
  router -->|policy, order| prepare["prepare_main<br/>RAG /retrieve if policy"]
  router -->|refund| loadMem["load_refund_memory<br/>PostgresStore"]
  router -->|email| draftEmail[draft_email]

  cheap --> respond[respond]
  prepare --> main["main_agent · MAIN_MODEL"]
  main -->|tool calls and step_count < 8| tools["tools (ToolNode)<br/>get_order, get_shipping_status,<br/>check_refund_eligibility, get_customer"]
  tools --> main
  main -->|step limit with tool calls still open| stop["stop_tool_loop<br/>close tool calls, ask for a person"]
  stop --> respond
  main -->|no tool calls| respond

  loadMem --> draftRefund["draft_refund<br/>MCP check_refund_eligibility"]
  draftRefund -->|no order, error, or ineligible| respond
  draftRefund -->|eligible| awaitRefund["await_refund_approval<br/>interrupt type=refund_approval"]
  awaitRefund --> issue["issue_refund<br/>MCP issue_refund or skip on reject<br/>append PostgresStore note"]
  issue --> respond

  draftEmail --> awaitEmail["await_email_confirm<br/>interrupt type=email_confirm"]
  awaitEmail --> send["send_email<br/>stub; needs confirmation_id"]
  send --> respond

  respond --> endNode([END])
```

- **Routing.** `CHEAP_MODEL` classifies the latest message into `chitchat`, `out_of_scope`, `policy`, `order`, `refund`, or `email`, and extracts `ORD-####` / `CUS-#` ids. On a model error it falls back to keyword matching, defaulting to `policy`.
- **Two model tiers.** `CHEAP_MODEL` routes, chats, and summarizes. `MAIN_MODEL` answers policy and order questions and is the only model with tools.
- **Read tools only.** The main model is bound to the four MCP read tools. `issue_refund` and `send_email` are called by graph nodes after an interrupt, never by the model ([ADR 0007](../decisions/0007-write-tools-gated-by-interrupt.md)). See [Human in the loop](../flows/human-in-the-loop.md).
- **Step limit.** At 8 main-model calls per turn, `stop_tool_loop` closes open tool calls and hands off to a person.
- **Summarization.** Near 70% of `CONTEXT_TOKEN_BUDGET`, older messages are replaced with a cheap-model summary. Never while an interrupt is open.
- **Operator memory.** Every refund decision is appended under `("refunds", "operator") / customer_id` (last 50 kept) and loaded into the next draft for that customer.

## State

`AgentState` in `graph/state.py`: `messages`, `intent`, `order_id`, `customer_id`, `documents`, `citations`, `refund_draft`, `refund_memory`, `approval`, `email_draft`, `email_confirmed`, `step_count`, `token_count`, `summary`, `interrupt_kind` (`none`, `refund`, `email`), `final_reply`.

## Config

Read from `apps/agent/.env` only (relative to the working directory).

| Variable | Default |
| --- | --- |
| `RAG_URL`, `MCP_URL` | `http://localhost:8001`, `http://localhost:8002/mcp` |
| `DATABASE_URL` | `postgresql://support:support@localhost:5432/support_desk` |
| `OPENROUTER_API_KEY` | required |
| `CHEAP_MODEL`, `MAIN_MODEL` | `openai/gpt-4o-mini`, `anthropic/claude-haiku-4.5` |
| `CONTEXT_TOKEN_BUDGET`, `SUMMARIZE_THRESHOLD_RATIO`, `KEEP_RECENT_MESSAGES` | `128000`, `0.7`, `8` |
| `APPROVAL_SECRET` | `dev-approval-secret`. Must match mcp-server |
| `LANGSMITH_TRACING`, `LANGSMITH_API_KEY`, `LANGSMITH_PROJECT` | `false` (`.env.example` sets `true`), —, `support-agent` |

Model clients are cached per process: restart after changing a model.

## Evals

- **Routing and write safety** (`evals/dataset.json`): `poetry run python evals/run_evals.py`. Checks intent routing, and that `issue_refund` / `send_email` refuse without an approval or confirmation id. Exits non-zero on failure.
- **Tool calls** (`evals/tool_tasks.json`): `POST /evals/run {n, k}`. Runs each task `n` times through the graph and reports tool-call accuracy, pass@k (at least one of `k` runs passes), and pass^k (all `k` pass, the reliability number).

## Known gaps

- **AGENT-TD-5** — `approval_id` is signed by the agent, not tied to an operator; there is no approval record.
- **AGENT-TD-6** — Email recipient and body are hard-coded; `EMAIL_PROVIDER` other than `stub` reports `sent` without sending.
- **AGENT-TD-7** — No weak-retrieval refusal; citations are kept in state but not returned by `/chat`.
- **AGENT-TD-8** — The router sees only the last message, so "yes please" loses context.
- **AGENT-TD-9** — If Postgres is down at startup, every request returns 503 until restart.
- **AGENT-TD-10** — The summary message is appended after the recent messages instead of before.
- **AGENT-TD-11** — No retry-then-escalate fallback, no enforced token cap, `escalate_to_human` never called; model errors return 500.
- **AGENT-TD-12** — Concurrent requests on one thread can race.
- **AGENT-TD-13** — Evals write to the production checkpoint tables and can call the live `issue_refund`.
- **AGENT-TD-14** — Tools re-bound every step, new MCP session per call, `/health` reports MCP connected without checking.

Decisions: [agent](../decisions/service-decisions.md#agent), [ADR 0007](../decisions/0007-write-tools-gated-by-interrupt.md), [ADR 0008](../decisions/0008-postgres-checkpointer-and-store.md).
