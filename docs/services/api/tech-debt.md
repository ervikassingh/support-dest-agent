# api tech debt

Severity levels are defined in [architecture/tech-debt.md](../../architecture/tech-debt.md). Auth is tracked as [X-TD-1](../../architecture/tech-debt.md#x-td-1-no-authentication-or-authorization-anywhere).

| ID | Item | Severity |
| --- | --- | --- |
| API-TD-1 | Upload path requires a filesystem shared with rag | Medium |
| API-TD-2 | Agent 4xx errors are reported as 503 | Medium |
| API-TD-3 | No DTO validation pipe | Medium |
| API-TD-4 | Failed file write leaves a document stuck in `queued` | Medium |
| API-TD-5 | No timeouts on downstream calls | Medium |
| API-TD-6 | `AgentClientService` is provided three times | Low |
| API-TD-7 | Config read from `process.env` and `ConfigService` inconsistently | Low |
| API-TD-8 | Redis URL credentials and TLS are ignored; queue never closed | Low |
| API-TD-9 | Health check does not check dependencies | Low |

### API-TD-1. Upload path requires a filesystem shared with rag

**Severity:** Medium.

`DocumentsService.uploadFile` writes to the absolute `storage_path` that rag returns. This works only when api and rag run on the same host or mount the same volume at the same path. It blocks containerizing them separately ([X-TD-9](../../architecture/tech-debt.md#x-td-9-app-services-are-not-containerized)).

**Fix:** object storage (S3 or MinIO) with a key in the job payload, or stream the bytes to a rag upload endpoint.

### API-TD-2. Agent 4xx errors are reported as 503

**Severity:** Medium.

`AgentClientService.postJson` throws `ServiceUnavailableException` for any non-2xx. A resume on a thread with no paused run (agent 404) or one paused for email (agent 400) reaches the operator as "API 503". `DocumentsService.rag()` does preserve the status.

**Fix:** forward 4xx status and detail; reserve 503 for network errors and agent 5xx.

### API-TD-3. No DTO validation pipe

**Severity:** Medium.

Bodies are typed with inline `type`s and checked by hand. `amount` is not coerced or range-checked (negative or string amounts pass to the agent). `note` and `message` have no length limit.

**Fix:** DTO classes with `class-validator` and a global `ValidationPipe({ whitelist: true, transform: true })`.

### API-TD-4. Failed file write leaves a document stuck in `queued`

**Severity:** Medium.

If `mkdir` or `writeFile` throws after `reserve`, the row stays `queued` forever and nothing is enqueued. Only enqueue failures mark the row `failed`.

**Fix:** wrap write and enqueue in one try/catch that sets `failed` on any error.

### API-TD-5. No timeouts on downstream calls

**Severity:** Medium.

`fetch` to agent and rag has no `AbortSignal.timeout`. A stuck model call holds the browser request indefinitely ([X-TD-10](../../architecture/tech-debt.md#x-td-10-no-consistent-timeout-and-retry-policy)).

**Fix:** per-route timeouts, for example 90 s for `/chat` and 10 s for document metadata.

### API-TD-6. `AgentClientService` is provided three times

**Severity:** Low.

It is listed in the `providers` of `AppModule`, `ChatModule`, and `ApprovalsModule`, so Nest creates separate instances. Harmless today because it is stateless.

**Fix:** an `AgentModule` that provides and exports it once, imported by the feature modules.

### API-TD-7. Config read from `process.env` and `ConfigService` inconsistently

**Severity:** Low.

`AgentClientService` uses `ConfigService`. `DocumentsService`, `HealthController`, and `main.ts` read `process.env` directly. Values only in `.env` files work in both cases because `ConfigModule` loads them into `process.env`, but there is no validation of required config.

**Fix:** use `ConfigService` everywhere with a validation schema.

### API-TD-8. Redis URL credentials and TLS are ignored; queue never closed

**Severity:** Low.

`ingestQueue()` passes only `hostname` and `port` from `REDIS_URL`. A password, username, db index, or `rediss://` is dropped. The `Queue` is never closed on shutdown.

**Fix:** pass the full URL to ioredis, and close the queue in `onModuleDestroy`.

### API-TD-9. Health check does not check dependencies

**Severity:** Low.

`GET /health` always returns `ok` and echoes `AGENT_URL`. It does not call agent, rag, or Redis.

**Fix:** a readiness endpoint that checks each dependency's `/health` and Redis `PING`.
