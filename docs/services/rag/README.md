# rag

Python FastAPI service on `:8001`. Owns the policy corpus: document rows and versions, parsing, chunking, embeddings, hybrid search, grounded answers, and retrieval and answer evals. The BullMQ ingest worker runs in the same process by default.

## Endpoints

| Method | Path | Caller | Does |
| --- | --- | --- | --- |
| GET | `/health` | ops | DB ping, embedding model and dim, active chunk table, worker flag |
| POST | `/documents/reserve` | api | Body `{sourceKey, filename, sourceUri?}`. Creates the next version row (`queued`) and returns its absolute `storage_path` |
| GET | `/documents` | api | All rows, newest first, with `chunk_count` |
| GET | `/documents/{id}` | api | One row with `chunk_count`; 404 if missing |
| POST | `/documents/{id}/status` | api | Body `{status, error?}`. Used by api when enqueue fails |
| POST | `/retrieve` | agent | Body `{query, top_k=5 (1–20)}`. Hybrid search; returns `documents`, `citations`, `usage` |
| POST | `/answer` | — | Body `{question, top_k}`. Retrieve, then `MAIN_MODEL` answers with `[n]` citations |
| POST | `/answer/stream` | — | Same, as SSE: `token` events then one `done` event |
| POST | `/evals/run` | dev | Body `{answer=true, judge=true, limit?}`. Golden-set retrieval metrics, optional answer scoring, optional LangSmith experiment |

## CLI

```bash
poetry run rag                 # API on PORT
poetry run rag-worker          # worker alone (set WORKER_ENABLED=false on the API)
poetry run rag-seed            # write docs/seed/* and evals/golden.json
poetry run rag-seed --ingest   # also ingest those files
poetry run rag-reindex         # re-embed into the table for the current EMBEDDING_MODEL / EMBEDDING_DIM
poetry run rag-golden          # write evals/golden.generated.json for review
poetry run pytest
```

## Layout

```
src/rag/
  main.py        FastAPI app, lifespan (schema + worker), endpoints
  settings.py    pydantic-settings (root .env then apps/rag/.env)
  db.py          Pool, documents table, per-model chunk tables, BM25 + HNSW indexes
  ingest.py      reserve, status, list, URL download, ingest_document
  worker.py      BullMQ consumer for queue 'ingest'
  detect.py      Type detection (magic bytes, extension, content type); Google export URLs
  parse.py       PDF, DOCX, HTML, text → Markdown with <!-- page:N --> markers
  chunking.py    Heading-first sections, token packing with overlap, embed prefix
  embed.py       OpenRouter /embeddings with dimension check and cost
  retrieve.py    BM25 + vector, version canonicalization, reciprocal rank fusion
  answer.py      Context blocks, streaming chat completion, usage and cost
  reindex.py     Copy and re-embed chunks into the active table
  seed.py        Seed corpus (md, txt, html, pdf, docx) and golden cases
  evals/         golden.py, metrics.py, judge.py (Ragas + JSON judge), runner.py
evals/golden.json
tests/           chunking, detect, metrics, parse/seed
```

## Data

| Table | Key columns |
| --- | --- |
| `documents` | `id`, `source_key`, `version` (unique together), `filename`, `source_type`, `source_uri`, `title`, `content_hash`, `status`, `error`, `storage_path`, timestamps |
| `chunks_<model>_<dim>` | `id`, `document_id` (FK, cascade), `version`, `content_hash`, `source_type`, `source_uri`, `title`, `header_path`, `page_start`, `page_end`, `chunk_index`, `char_start`, `char_end`, `embedding_model`, `ingested_at`, `content`, `embed_text`, `embedding vector(dim)` |

Indexes per chunk table: HNSW on `embedding vector_cosine_ops`, BM25 on `(id, embed_text)`. Table names longer than 50 chars become `chunks_<sha1-8>_<dim>`.

Files live under `UPLOADS_DIR` (default `docs/uploads`) as `<slug>/v<version>/<filename>`.

## Config

| Variable | Default |
| --- | --- |
| `PORT` | `8001` |
| `DATABASE_URL` | `postgresql://support:support@localhost:5432/support_desk` |
| `REDIS_URL` | `redis://localhost:6379` |
| `UPLOADS_DIR` | `<repo>/docs/uploads` |
| `OPENROUTER_API_KEY`, `OPENROUTER_BASE_URL` | —, `https://openrouter.ai/api/v1` |
| `MAIN_MODEL`, `JUDGE_MODEL` | `anthropic/claude-haiku-4.5`, `openai/gpt-4.1` |
| `EMBEDDING_MODEL`, `EMBEDDING_DIM` | `openai/text-embedding-3-small`, `1536` |
| `CHUNK_TOKENS`, `CHUNK_OVERLAP` | `800`, `100` |
| `CANDIDATE_K`, `RRF_K` | `50`, `60` (not in `.env.example`) |
| `CHAT_INPUT_USD_PER_MILLION`, `CHAT_OUTPUT_USD_PER_MILLION`, `EMBEDDING_USD_PER_MILLION` | unset |
| `LANGSMITH_API_KEY`, `LANGSMITH_PROJECT` | —, `support-desk-rag` |
| `WORKER_ENABLED` | `true` |

## Dependencies

Postgres (ParadeDB) is required to boot. Redis is required for the worker. OpenRouter is required for ingest, retrieval (query embedding), and answers.

## See also

- [flow.md](flow.md) · [decisions.md](decisions.md) · [tech-debt.md](tech-debt.md)
- [ADR 0005: ParadeDB](../../architecture/decisions/0005-paradedb-single-postgres.md) · [ADR 0006: BullMQ ingest](../../architecture/decisions/0006-bullmq-ingest-queue.md)
