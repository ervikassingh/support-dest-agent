# 0005. One ParadeDB Postgres for vectors, BM25, and agent checkpoints

- Status: Accepted
- Services: rag, agent

## Context

Retrieval needs both keyword and vector search. The agent needs durable checkpoints. Running a separate vector DB, search engine, and relational DB is a lot of infrastructure for this scale.

## Decision

Use `paradedb/paradedb` (Postgres 17 with `pgvector` and `pg_search`) as the single database `support_desk`:

- rag creates `documents` and one `chunks_<model>_<dim>` table per embedding config, with an HNSW cosine index and a BM25 index on `embed_text`.
- agent lets LangGraph create its checkpoint and store tables via `setup()`.

The previous Postgres 16 volume (`postgres-data`) is left in Docker but not mounted. ParadeDB uses `paradedb-data`.

## Alternatives considered

- **pgvector only, Postgres full-text for keywords.** Available everywhere, but `ts_rank` is not BM25 and ranks policy text noticeably worse.
- **Dedicated vector DB (Qdrant, Pinecone) plus Elasticsearch.** Better at large scale, but three systems to run and keep consistent.

## Consequences

- Hybrid search is two SQL queries against one table, fused in Python ([RAG-1](service-decisions.md#rag-1-hybrid-bm25--vector-search-fused-with-rrf-no-reranker)).
- The BM25 query syntax (`|||`, `pdb.score`) and index DDL depend on the ParadeDB version. `db.py` tries the newer `USING paradedb` DDL and falls back to `USING bm25`. The image tag is `latest`, so an upstream change can break boot ([X-TD-6](../../README.md#known-gaps)).
- Agent and rag share a database and credentials. A noisy reindex can affect checkpoint latency.
