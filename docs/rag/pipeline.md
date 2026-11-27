# RAG pipeline

Locked design for ingest, hybrid search, and evals.

## Flow

1. `POST /documents` on the Nest API accepts a file or `{ "url" }`.
2. The RAG service reserves a row and a path `docs/uploads/<source>/<version>/<file>`.
3. Nest writes the file (URLs are fetched by the worker) and enqueues an `ingest` job on Redis (BullMQ, 3 attempts, exponential backoff).
4. The worker in `apps/rag` detects the type, parses to Markdown with page markers, chunks, embeds, and stores rows in ParadeDB.
5. `POST /retrieve` runs BM25 and vector search, fuses them, and returns chunks. `POST /answer` and `POST /answer/stream` answer from that context.

Same file name or the same URL uploaded again creates a new version. Every version stays in the index. At search time, identical chunk text is collapsed to the newest version.

## Types

PDF, DOCX, Markdown, plain text, HTML, and a public web URL. Public Google Docs, Sheets, and Slides links are rewritten to their export URLs and saved as a snapshot. Notion is out of scope. Fetching is a plain HTTP GET (no browser rendering, no crawling).

## Chunks

The parser preserves headings and page numbers (real pages for PDF, page breaks for DOCX, page 1 for the web). Chunking splits on headings first, then packs a section to about 800 tokens with 100 tokens of overlap. A chunk never crosses a heading.

Each chunk stores document id, version, content hash, source type, source URI, title, header path, page start and end, chunk index, character offsets, ingest time, and embedding model.

The text that is embedded, and the text placed in the prompt, is prefixed with `[Title] › header path (p. start-end)`. The prompt also gets a metadata line (version, pages, source).

## Search

ParadeDB (`pgvector` + `pg_search`) in one Postgres. BM25 uses `embed_text ||| query` and `pdb.score`. Vectors use cosine distance. Each side returns 50 candidates. Reciprocal rank fusion uses k = 60. There is no reranker.

Embeddings go through OpenRouter. `EMBEDDING_MODEL` and `EMBEDDING_DIM` select the table `chunks_<model>_<dim>`. Changing either means `poetry run rag-reindex` from `apps/rag`.

## Evals

Golden questions live in `apps/rag/evals/golden.json` (one per section of `docs/seed`). A retrieved chunk counts as relevant when its title and header path match the label. If nothing in the top 10 matches, the judge model can mark relevance for that case.

`POST /evals/run` on the RAG service (`:8001`) returns hit@5, recall@5, precision@5, MRR@10, MAP@10, and nDCG@10. With `answer: true` it also scores faithfulness, groundedness, answer relevance, and context relevance (Ragas, with a single JSON judge if Ragas cannot score a case), plus time to first token, end-to-end latency, token counts, and cost when the provider or the USD-per-million env rates supply it. A LangSmith experiment is written when `LANGSMITH_API_KEY` is set.

`POST /evals/run` on the agent service (`:8000`) runs each tool task 5 times and returns tool-call accuracy, pass@1, pass@5, pass^5, latency, and cost.

`JUDGE_MODEL` defaults to `openai/gpt-4.1`. Answers use `MAIN_MODEL`.

## Local infra

ParadeDB replaces the Postgres 16 image. Data lives in a new volume, `paradedb-data`. The old `postgres-data` volume is not mounted and is not deleted. Redis is `localhost:6379`.
