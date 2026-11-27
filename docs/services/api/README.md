# api

NestJS 11 backend-for-frontend on `:3001`. It is the only service the browser calls. It validates input, forwards chat and approvals to the agent, and runs the upload half of document ingest. It holds no domain logic ([ADR 0002](../../architecture/decisions/0002-nest-as-thin-bff.md)).

## Endpoints

| Method | Path | Forwards to | Notes |
| --- | --- | --- | --- |
| GET | `/health` | — | `{status, service, agentUrl}`. Does not check downstreams |
| POST | `/chat` | agent `POST /chat` | Body `{message, threadId?}`. 400 if `message` is blank |
| POST | `/approvals/:threadId` | agent `POST /threads/:id/resume` | Body `{decision: approve\|edit\|reject, amount?, note?}`. `amount` required for `edit` |
| POST | `/documents` | rag `POST /documents/reserve`, then Redis | Multipart `file` (≤ 20 MB) or JSON `{url}`; exactly one |
| GET | `/documents` | rag `GET /documents` | Mapped to camelCase `DocumentView` |
| GET | `/documents/:id` | rag `GET /documents/:id` | Same mapping |

## Layout

```
src/
  main.ts                     Bootstrap, CORS (WEB_ORIGIN, credentials), port
  app.module.ts               ConfigModule (global), feature modules
  health.controller.ts
  agent-client.service.ts     fetch wrapper for the agent; maps failures to 503
  chat/                       controller + service (validation, forward)
  approvals/                  controller + service (decision validation, forward)
  documents/                  controller (optional multipart interceptor) + service (rag client, BullMQ producer, file write)
```

`OptionalFileInterceptor` in `documents.controller.ts` runs Multer only when the request is `multipart/form-data`, so the same route accepts JSON `{url}`.

## Dependencies

| Depends on | For |
| --- | --- |
| agent | Chat and resume |
| rag | Document reserve, list, get, status |
| Redis | BullMQ `ingest` queue (producer) |
| Local disk | Writes upload bytes to the path rag reserved |

## Config

| Variable | Default | Read via |
| --- | --- | --- |
| `PORT` | `3001` | `process.env` |
| `WEB_ORIGIN` | `http://localhost:3000` | `process.env` (CORS) |
| `AGENT_URL` | `http://localhost:8000` | `ConfigService` |
| `RAG_URL` | `http://localhost:8001` | `process.env` |
| `REDIS_URL` | `redis://localhost:6379` | `process.env` (host and port only) |

Env files: `apps/api/.env`, then root `.env`.

## Run

```bash
pnpm dev:api        # nest start --watch
pnpm --filter api build && pnpm --filter api start
```

## See also

- [flow.md](flow.md) · [decisions.md](decisions.md) · [tech-debt.md](tech-debt.md)
