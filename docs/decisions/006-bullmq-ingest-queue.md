# 0006. Document ingest runs as BullMQ jobs on Redis

- Status: Accepted
- Services: api, rag, web

## Context

Parsing, chunking, and embedding a document takes seconds to minutes and calls an external API that can fail. The upload request should return immediately, and failures should retry.

## Decision

- api is the producer. It adds a job named `ingest` with `{documentId}` to the `ingest` queue, using the document id as `jobId` so a duplicate enqueue is a no-op. Defaults: 3 attempts, exponential backoff from 2 s, keep the last 100 completed and 200 failed jobs.
- rag is the consumer, using the Python `bullmq` package. The worker starts inside the rag API process unless `WORKER_ENABLED=false`, in which case `poetry run rag-worker` runs it alone.
- Job status is not read from Redis. The worker writes `documents.status` and `documents.error` in Postgres, and the UI reads that via `GET /documents`.

## Alternatives considered

- **Ingest inline in the upload request.** Simple, but long requests and no retries.
- **Postgres-backed queue (e.g. a `jobs` table with `SKIP LOCKED`).** One fewer system, but BullMQ gives retries, backoff, and a cross-language client for free.
- **Celery / RQ.** Python-only producers; Nest could not enqueue directly.

## Consequences

- Redis is required for uploads. If enqueue fails, api marks the document `failed` and returns 503.
- Producer and consumer must agree on queue name and payload shape with no shared schema.
- Between retries the worker sets status back to `queued` with the attempt count in `error`, so the UI shows a retrying document as queued.
- api and rag must see the same filesystem, because api writes the bytes to the path rag reserved ([API-TD-1](../services/api.md#known-gaps)).
