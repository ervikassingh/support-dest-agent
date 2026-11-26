# Agent orchestrator

Python FastAPI service that will host the LangGraph graph. NestJS proxies chat and approvals here.

- `GET /health`
- `POST /chat` — stub router + optional RAG probe
- `POST /threads/{id}/resume` — HITL stub

MCP client and Postgres checkpointer are stubbed. See root README.
