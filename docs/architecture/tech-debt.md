# Cross-cutting tech debt

Debt that spans services. Service-specific items live in each service's `tech-debt.md`.

Severity:

- **High**: a correctness, safety, or security problem that would block any real deployment.
- **Medium**: causes bugs, drift, or slow work today.
- **Low**: cleanup that pays off later.

## Summary

| ID | Item | Severity |
| --- | --- | --- |
| [X-TD-1](#x-td-1-no-authentication-or-authorization-anywhere) | No authentication or authorization anywhere | High |
| [X-TD-2](#x-td-2-customer-id-format-disagrees-between-agent-and-mcp-server) | Customer id format disagrees between agent and mcp-server | High |
| [X-TD-3](#x-td-3-no-ci-and-thin-test-coverage) | No CI and thin test coverage | Medium |
| [X-TD-4](#x-td-4-no-shared-contracts-between-services) | No shared contracts between services | Medium |
| [X-TD-5](#x-td-5-root-readme-has-drifted-from-the-code) | Root README has drifted from the code | Medium |
| [X-TD-6](#x-td-6-unpinned-infrastructure-images) | Unpinned infrastructure images | Medium |
| [X-TD-7](#x-td-7-inconsistent-env-loading) | Inconsistent env loading | Low |
| [X-TD-8](#x-td-8-no-cross-service-request-tracing) | No cross-service request tracing | Low |
| [X-TD-9](#x-td-9-app-services-are-not-containerized) | App services are not containerized | Low |
| [X-TD-10](#x-td-10-no-consistent-timeout-and-retry-policy) | No consistent timeout and retry policy | Low |

## Items

### X-TD-1. No authentication or authorization anywhere

**Severity:** High. **Services:** all.

No service checks who is calling. Concretely:

- api `POST /approvals/:threadId` lets anyone approve or edit a refund if they know or guess a thread id. Thread ids are `thread-` plus 10 hex chars.
- api `/chat` accepts any `threadId`, so one browser can read and continue another customer's thread.
- agent, rag, and mcp-server bind `0.0.0.0` with no auth. mcp-server only checks the `Host` header against an allowlist.
- rag `POST /documents/{id}/status` lets any caller set any status string.

The chat service comment mentions "auth/session stubs", but none exist.

**Fix:** sessions in api (cookie or JWT), with a customer role for `/chat` and an operator role for `/approvals` and `/documents`. Bind internal services to localhost or a private network and require a shared service token between api, agent, rag, and mcp-server. Bind each thread to the session that created it.

### X-TD-2. Customer id format disagrees between agent and mcp-server

**Severity:** High. **Services:** agent, mcp-server.

mcp-server ids are `CUS-1`, `CUS-2`, `CUS-GUEST` (`apps/mcp-server/src/data.ts`). The agent's router prompt and regex extract `CUST-\d+` (`agent/routing/intent.py`), and the tool schema example says `CUST-1`. So `customer_id` is almost never extracted from a message. Refund notes then fall into the shared `unknown` key ([AGENT-TD-3](../services/agent/tech-debt.md)).

**Fix:** pick one format, ideally derive `customer_id` from `get_order` instead of from free text, and add a routing eval case with a customer id.

### X-TD-3. No CI and thin test coverage

**Severity:** Medium. **Services:** all.

- No CI config in the repo.
- `lint` for web, api, and mcp-server is `tsc --noEmit`. No ESLint.
- TypeScript apps have no tests.
- agent has one unit test file (`tests/test_evals_metrics.py`). rag has unit tests for chunking, detection, metrics, and seed parsing, but none for retrieval, ingest, or the API.
- The agent eval runner (`evals/run_evals.py`) needs live model keys, and its refund-safety cases with an `approval_id` call the real MCP `issue_refund`, which mutates in-memory state.

**Fix:** a CI workflow that runs `pnpm lint`, `ruff`, and `pytest` for both Python apps on every PR. Add graph tests with a fake model and a fake MCP client. Make refund-safety evals run against a disposable MCP instance.

### X-TD-4. No shared contracts between services

**Severity:** Medium. **Services:** api, agent, rag, web.

Request and response shapes are redeclared in each language:

- `ChatResponse` and `ApprovalRequest` in `apps/api/src/agent-client.service.ts` versus pydantic models in `agent/main.py`.
- `Reserved` and `DocumentView` in `apps/api/src/documents/documents.service.ts` versus untyped dicts from `rag/ingest.py`.
- `DocumentRow` in `apps/web/src/components/DocumentsPanel.tsx` versus `DocumentView` in api.
- The BullMQ payload `{documentId}` is a convention between api and rag.

The agent's `/chat` response can include `interrupt`, which api's `ChatResponse` type omits; web ignores it.

**Fix:** generate TypeScript types from the FastAPI OpenAPI schemas (`openapi-typescript`) into a `packages/contracts` workspace, and share it between api and web.

### X-TD-5. Root README has drifted from the code

**Severity:** Medium. **Services:** docs.

Statements in `README.md` that are no longer true:

- "Full LangGraph routing, real RAG, durable HITL, and evals are not implemented yet." Routing, hybrid RAG, Postgres-backed HITL, and eval endpoints all exist.
- "Today the agent stub pauses in memory ... Not wired yet." The Postgres checkpointer is wired.
- "The router (planned)". The router exists.
- RAG section lists reranking, an embedding cache, and a refusal threshold. None are implemented ([RAG-TD-1](../services/rag/tech-debt.md), [RAG-TD-6](../services/rag/tech-debt.md)).
- "First files to look at" points to `apps/agent/src/agent/graph.py`, which does not exist. The graph is in `graph/build.py`.
- Graph state and node names in the README (`retrieve`, `answer_policy`, `order_agent`, `fallback`) do not match `graph/state.py` and `graph/build.py`. The intents now also include `chitchat` and `email`.

**Fix:** trim the root README to setup, run, and a link to `docs/`. Keep design detail here.

### X-TD-6. Unpinned infrastructure images

**Severity:** Medium. **Services:** infra, rag.

`docker-compose.yml` uses `paradedb/paradedb:latest`. rag depends on version-specific BM25 syntax and DDL, and already carries a fallback for an older form. A new `latest` can break boot or search without any code change.

**Fix:** pin the ParadeDB tag (and `redis:7-alpine` to a minor), and bump deliberately.

### X-TD-7. Inconsistent env loading

**Severity:** Low. **Services:** api, agent, rag, mcp-server.

api reads `apps/api/.env` then the root `.env`. rag reads the root then its own. agent reads only `apps/agent/.env`. mcp-server reads only the process env. The root `.env.example` suggests shared values like `OPENROUTER_API_KEY`, but setting it there does nothing for the agent.

**Fix:** one rule for all services, for example "app `.env` overrides root `.env`", and document it in each `.env.example`.

### X-TD-8. No cross-service request tracing

**Severity:** Low. **Services:** all.

LangSmith traces the agent's graph when enabled. Nothing propagates a request id from web through api to agent, rag, and mcp-server, so a slow chat turn cannot be followed across logs. api logs with Nest's logger, Python services with `logging`, mcp-server with `console.log`.

**Fix:** generate an `x-request-id` in api, forward it on every hop (including as MCP metadata), and log it. Consider OpenTelemetry later.

### X-TD-9. App services are not containerized

**Severity:** Low. **Services:** all.

`docker-compose.yml` runs only Postgres and Redis. The five apps run on the host. mcp-server's host allowlist already includes `mcp-server` and `mcp`, anticipating container names. Because api writes files that rag reads, containerizing needs a shared volume for `docs/uploads` ([API-TD-1](../services/api/tech-debt.md)).

**Fix:** Dockerfiles per app and a compose profile that runs the full stack.

### X-TD-10. No consistent timeout and retry policy

**Severity:** Low. **Services:** api, agent, rag.

- api's `fetch` to agent and rag has no timeout. A hung model call holds the browser request open.
- agent's RAG client uses a 60 s timeout. The MCP client has none of its own.
- rag uses 45 s for URL downloads and 120 s for model calls.
- No service retries model calls.

**Fix:** set timeouts per hop that fit inside the caller's budget, and add bounded retries with backoff on model calls.
