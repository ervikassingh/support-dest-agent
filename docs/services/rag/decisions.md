# rag decisions

System-wide decisions are in [architecture/decisions](../../architecture/decisions/README.md). The main ones for this service are [0005: ParadeDB](../../architecture/decisions/0005-paradedb-single-postgres.md) and [0006: BullMQ ingest](../../architecture/decisions/0006-bullmq-ingest-queue.md).

## RAG-1. Hybrid BM25 + vector search fused with RRF; no reranker

**Context.** Policy questions mix exact terms ("30 days", "store credit") with paraphrase. Either retriever alone misses cases.

**Decision.** Run BM25 and cosine-distance queries, 50 candidates each (`CANDIDATE_K`), and fuse with reciprocal rank fusion, `k = 60` (`RRF_K`). No cross-encoder reranker.

**Alternatives.** Vector only; weighted score blending (needs score normalization across two scales); a reranker (better precision, extra latency and cost).

**Consequences.** Rank-based fusion needs no tuning between score scales. RRF scores are not comparable across queries, so they cannot drive a refusal threshold ([RAG-TD-1](tech-debt.md)).

## RAG-2. Heading-first chunking at 800 tokens with 100 overlap

**Decision.** Never cross a heading. Pack paragraphs to `CHUNK_TOKENS` with `CHUNK_OVERLAP` token overlap using `tiktoken` cl100k.

**Consequences.** Each chunk has one header path, which makes citations precise and lets evals label relevance by title plus header path. Long flat documents with no headings become one big section split only by size.

## RAG-3. Markdown with page markers as the intermediate format

**Decision.** Every parser emits Markdown with `<!-- page:N -->` markers. Chunking and page tracking work only on that.

**Consequences.** One chunker for five formats. Page numbers survive for PDF and DOCX. Tables and layout are flattened.

## RAG-4. Contextual prefix on embedded text

**Decision.** Embed and prompt with `[Title] › header path (p. N-M)` before the chunk body. Store the raw `content` too.

**Consequences.** Short chunks keep their topic, and BM25 matches titles and headings. Changing the prefix format requires re-ingest, not just reindex, since reindex re-embeds the stored `embed_text`.

## RAG-5. One chunk table per embedding model and dimension

**Decision.** `chunks_<model-slug>_<dim>` is derived from `EMBEDDING_MODEL` and `EMBEDDING_DIM`. `embed.py` rejects vectors whose length differs from `EMBEDDING_DIM`.

**Alternatives.** One table with a model column (vector columns have a fixed dimension, so mixed dims need separate columns anyway).

**Consequences.** Switching models is safe and reversible; the old table stays until dropped by hand. `rag-reindex` is required after a switch or search returns nothing.

## RAG-6. Keep every version; dedupe identical text at query time

**Context.** Re-uploading a policy should not lose history, and identical sections across versions should not crowd results.

**Decision.** Each upload of a `source_key` is a new version with its own chunks. Retrieval maps each `content_hash` to its newest version before fusion.

**Consequences.** Full history and simple ingest. Text that changed between versions is returned from both old and new versions ([RAG-TD-4](tech-debt.md)).

## RAG-7. Ingest worker runs inside the API process by default

**Decision.** The FastAPI lifespan starts the BullMQ worker unless `WORKER_ENABLED=false`; `rag-worker` runs it alone.

**Consequences.** One process for local dev. Parsing is synchronous Python inside the async worker, so a large PDF blocks API requests in the same process ([RAG-TD-5](tech-debt.md)).

## RAG-8. Evals are a service endpoint with curated golden data

**Decision.** `golden.json` is generated from the same `seed.py` that writes the corpus, so each question maps to a known section. `/evals/run` runs against the live index. Answer scoring uses Ragas with a JSON-judge fallback.

**Consequences.** Retrieval changes can be measured with one call. Results depend on what is currently ingested, so run `rag-seed --ingest` first for comparable numbers.

## RAG-9. Plain HTTP fetch for URLs

**Decision.** `httpx` GET with redirects, 45 s timeout, 20 MB cap. Google Docs, Sheets, and Slides links are rewritten to PDF export.

**Alternatives.** Headless browser rendering; crawling.

**Consequences.** No browser dependency. JavaScript-rendered pages ingest as near-empty HTML. No restriction on target hosts ([RAG-TD-2](tech-debt.md)).
