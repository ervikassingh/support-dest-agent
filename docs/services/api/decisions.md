# api decisions

System-wide decisions are in [architecture/decisions](../../architecture/decisions/README.md). The main one for this service is [0002: Nest is a thin BFF](../../architecture/decisions/0002-nest-as-thin-bff.md).

## API-1. Pass agent responses through unchanged

**Context.** The agent's `/chat` and resume responses are already shaped for the UI (`reply`, `threadId`, `status`, `interrupt`).

**Decision.** `AgentClientService` returns the agent's JSON as-is. api validates requests, not responses.

**Consequences.** New agent fields reach the browser without api changes. api's `ChatResponse` type is documentation only and has already drifted (it lacks `interrupt`).

## API-2. rag owns document metadata; api writes the bytes

**Context.** The upload arrives at api. rag owns the `documents` table, versioning, and the storage layout.

**Decision.** Reserve then write: api asks rag for a row and absolute `storage_path`, writes the file there, then enqueues. rag never receives the bytes over HTTP.

**Alternatives.** Stream the file to a rag upload endpoint; or put files in object storage and pass a key.

**Consequences.** No large bodies between services. api and rag must share a filesystem ([API-TD-1](tech-debt.md)).

## API-3. api is the BullMQ producer

**Context.** Ingest is asynchronous ([ADR 0006](../../architecture/decisions/0006-bullmq-ingest-queue.md)).

**Decision.** api creates the `Queue('ingest')` lazily on first upload and adds jobs with `jobId = documentId`. The job id makes a repeated enqueue for the same document a no-op.

**Consequences.** api needs Redis only for uploads. Chat works without Redis.

## API-4. Native fetch, manual validation

**Decision.** Downstream calls use Node's global `fetch`. Request bodies are checked by hand in services. No `class-validator`, `ValidationPipe`, or `HttpModule`.

**Consequences.** Few dependencies. Validation and error mapping are inconsistent between modules ([API-TD-3](tech-debt.md)).
