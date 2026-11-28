# 0004. OpenRouter is the only model gateway

- Status: Accepted
- Services: agent, rag

## Context

The design calls for model tiering (a cheap model for routing and small talk, a stronger model for tool use and answers, a separate judge for evals) and for embeddings. Using vendor SDKs directly means one key and one client per vendor.

## Decision

All chat and embedding calls go through OpenRouter's OpenAI-compatible API (`OPENROUTER_BASE_URL`, `OPENROUTER_API_KEY`). Models are chosen by slug in env:

| Variable | Default | Used for |
| --- | --- | --- |
| `CHEAP_MODEL` | `openai/gpt-4o-mini` | agent: intent router, cheap agent, summarizer |
| `MAIN_MODEL` | `anthropic/claude-haiku-4.5` | agent: main tool-using agent; rag: `/answer` |
| `JUDGE_MODEL` | `openai/gpt-4.1` | rag: eval judge |
| `EMBEDDING_MODEL` / `EMBEDDING_DIM` | `openai/text-embedding-3-small` / 1536 | rag: ingest and query embeddings |

The agent uses `langchain_openai.ChatOpenAI` pointed at OpenRouter. rag calls the HTTP API with `httpx`.

## Alternatives considered

- **Direct vendor SDKs.** Access to vendor-only features (Anthropic prompt caching headers, batch APIs), but more keys and more code paths.
- **Self-hosted models.** No per-token cost, but heavy ops for a demo-scale project.

## Consequences

- Swapping a model is an env change. Changing the embedding model or dimension needs `poetry run rag-reindex`.
- OpenRouter is a single point of failure for every LLM call. There is no fallback provider.
- Cost comes from OpenRouter's `usage.cost` when present, otherwise from the optional `*_USD_PER_MILLION` env rates.
- Provider-specific prompt caching, listed in the root README as a cost control, is not configured.
