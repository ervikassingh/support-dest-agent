# RAG service

Hybrid retrieval for policy documents.

- `POST /documents/reserve`, `GET /documents`, `GET /documents/:id` — used by the Nest upload API
- `POST /retrieve` — BM25 + vector search, fused
- `POST /answer` and `POST /answer/stream`
- `POST /evals/run` — hit@5, recall@5, precision@5, MRR@10, MAP@10, nDCG@10, plus answer quality

The ingest worker starts with the API. `poetry run rag-worker` runs it on its own (`WORKER_ENABLED=false` on the API in that case).

```bash
poetry run rag-seed            # write docs/seed and apps/rag/evals/golden.json
poetry run rag-seed --ingest  # also embed those files
poetry run rag-reindex        # after EMBEDDING_MODEL or EMBEDDING_DIM changes
poetry run rag-golden         # review copy at evals/golden.generated.json
```

See `docs/rag/pipeline.md`.
