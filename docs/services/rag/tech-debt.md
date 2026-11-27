# rag tech debt

Severity levels are defined in [architecture/tech-debt.md](../../architecture/tech-debt.md). The unauthenticated status endpoint is covered by [X-TD-1](../../architecture/tech-debt.md#x-td-1-no-authentication-or-authorization-anywhere).

| ID | Item | Severity |
| --- | --- | --- |
| RAG-TD-2 | URL ingest can fetch internal addresses (SSRF) | High |
| RAG-TD-3 | Upload filename is not sanitized before building the storage path | High |
| RAG-TD-1 | No reranker and no weak-retrieval refusal | Medium |
| RAG-TD-4 | Old versions with changed text stay searchable | Medium |
| RAG-TD-5 | Synchronous parsing blocks the event loop | Medium |
| RAG-TD-7 | Ingest embeds the whole document in one request and inserts row by row | Medium |
| RAG-TD-6 | No embedding or retrieval cache | Low |
| RAG-TD-8 | Reindex loads everything into memory and leaves old tables | Low |
| RAG-TD-9 | Service will not boot without Postgres | Low |
| RAG-TD-10 | Status and retry bookkeeping is loose | Low |
| RAG-TD-11 | Minor accuracy and efficiency gaps | Low |

### RAG-TD-1. No reranker and no weak-retrieval refusal

**Severity:** Medium.

Retrieval is RRF with no reranker. `/answer` refuses only when zero documents come back, which almost never happens because vector search always returns neighbors. Off-topic questions get loosely related context and rely on the prompt to say "I don't know". The root README lists reranking and a refusal threshold as features.

**Fix:** add a reranker (cross-encoder or an API reranker) over the fused top 20–50 and refuse below a calibrated rerank score. Measure with `/evals/run` plus unanswerable golden cases.

### RAG-TD-2. URL ingest can fetch internal addresses (SSRF)

**Severity:** High.

`_download` in `ingest.py` follows redirects to any host. A URL like `http://169.254.169.254/...` or `http://localhost:8000/...` is fetched from inside the network and its response is ingested and searchable.

**Fix:** allow only `http(s)`, resolve the host and reject private, loopback, and link-local ranges, and re-check on every redirect.

### RAG-TD-3. Upload filename is not sanitized before building the storage path

**Severity:** High.

`reserve_document` builds `uploads/<slug>/v<n>/<filename>` with the client-supplied `filename` (api passes Multer's `originalname`). A name containing `../` resolves outside `docs/uploads`, and api then writes the upload there.

**Fix:** reduce `filename` to a safe basename (strip separators and `..`, limit characters), and assert the resolved path is under `uploads_path`.

### RAG-TD-4. Old versions with changed text stay searchable

**Severity:** Medium.

Canonicalization only merges chunks with an identical `content_hash`. If v2 of a policy changes "30 days" to "14 days", both chunks are retrievable and the answer can cite the outdated one. There is no delete or archive endpoint.

**Fix:** search only the latest version of each `source_key` by default (keep history for audit), and add a delete or deactivate endpoint.

### RAG-TD-5. Synchronous parsing blocks the event loop

**Severity:** Medium.

`ingest_document` calls `parse_file`, `chunk_markdown`, and file hashing synchronously inside the async worker. With the worker in the API process (the default), a large PDF stalls `/retrieve` for the agent.

**Fix:** run CPU-bound steps with `asyncio.to_thread`, or run `rag-worker` as a separate process in any shared environment.

### RAG-TD-6. No embedding or retrieval cache

**Severity:** Low.

Every `/retrieve` embeds the query again. Repeated questions pay for the same embedding and search. The root README lists a retrieval cache as a cost control.

**Fix:** cache query embeddings by `(model, dim, normalized query)` in Redis, with a short TTL on full retrieval results invalidated on ingest.

### RAG-TD-7. Ingest embeds the whole document in one request and inserts row by row

**Severity:** Medium.

`ingest_document` sends every chunk to `/embeddings` in a single call, which fails for large documents once provider input limits are hit. Rows are inserted one `execute` at a time. `reindex` already batches embeddings by 64.

**Fix:** batch embeddings (64 like reindex) and use `executemany` or `COPY` for inserts.

### RAG-TD-8. Reindex loads everything into memory and leaves old tables

**Severity:** Low.

`reindex()` reads all chunks into a list, re-embeds, then rewrites the target in one transaction. If the active table does not exist it picks the alphabetically first other `chunks_*` table, which may not be the one in use. Old tables are never dropped.

**Fix:** stream in batches, take the source table as an argument, and add a `--drop-source` option.

### RAG-TD-9. Service will not boot without Postgres

**Severity:** Low.

`ensure_schema()` runs in the lifespan with no retry, so rag fails to start if Postgres is not up yet. `/health` cannot report `degraded` in that case.

**Fix:** retry schema setup with backoff, or start degraded and retry in the background.

### RAG-TD-10. Status and retry bookkeeping is loose

**Severity:** Low.

- `POST /documents/{id}/status` accepts any string and does not check the document exists.
- Between retries the worker sets status back to `queued`, so a document that is retrying looks new.
- A job whose document row was deleted fails all attempts.

**Fix:** an enum for status with a `retrying` state, and a 404 for unknown ids.

### RAG-TD-11. Minor accuracy and efficiency gaps

**Severity:** Low.

- `char_start` and `char_end` come from searching for the first 80 characters of the chunk, so they are approximate when text repeats.
- `get_document` computes chunk counts for every document to return one.
- `/answer/stream` does not stop the upstream model call when the client disconnects.
- Cost and usage code is separate from the agent's and uses raw `httpx` rather than LangChain, so tracing differs between services.
- `CANDIDATE_K` and `RRF_K` are configurable but missing from `.env.example`.

**Fix:** track offsets during chunking, add a single-document count query, and check `request.is_disconnected()` in the stream.
