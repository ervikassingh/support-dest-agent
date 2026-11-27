# Documentation

Engineering docs for the support desk agent. Start with the system overview, then open the service you are changing.

## Layout

```
docs/
  README.md                      This index
  architecture/
    overview.md                  System map, request paths, data stores, ports
    tech-debt.md                 Cross-cutting debt (auth, CI, config, drift)
    decisions/                   System-wide architecture decision records (ADRs)
  services/
    web/        Next.js UI (:3000)
    api/        NestJS BFF (:3001)
    agent/      LangGraph orchestrator, FastAPI (:8000)
    rag/        Ingest, hybrid search, answers, evals (:8001)
    mcp-server/ MCP tool server, Streamable HTTP (:8002)
  seed/                          Policy corpus used by `rag-seed` and the golden eval set
  uploads/                       Ingest storage, written at runtime (not docs)
```

Every service folder has the same four files:

| File | Answers |
| --- | --- |
| `README.md` | What the service owns, its endpoints, config, and internal layout |
| `flow.md` | How requests and jobs move through it, with diagrams |
| `decisions.md` | Service-level decisions: context, choice, consequences |
| `tech-debt.md` | Known shortcuts and bugs, ranked by severity, with a suggested fix |

## Where to start

- New to the repo: [architecture/overview.md](architecture/overview.md)
- Why something is built the way it is: [architecture/decisions/](architecture/decisions/README.md), then the service's `decisions.md`
- Planning cleanup work: [architecture/tech-debt.md](architecture/tech-debt.md), then each service's `tech-debt.md`

| Service | Overview | Flow | Decisions | Tech debt |
| --- | --- | --- | --- | --- |
| web | [README](services/web/README.md) | [flow](services/web/flow.md) | [decisions](services/web/decisions.md) | [tech debt](services/web/tech-debt.md) |
| api | [README](services/api/README.md) | [flow](services/api/flow.md) | [decisions](services/api/decisions.md) | [tech debt](services/api/tech-debt.md) |
| agent | [README](services/agent/README.md) | [flow](services/agent/flow.md) | [decisions](services/agent/decisions.md) | [tech debt](services/agent/tech-debt.md) |
| rag | [README](services/rag/README.md) | [flow](services/rag/flow.md) | [decisions](services/rag/decisions.md) | [tech debt](services/rag/tech-debt.md) |
| mcp-server | [README](services/mcp-server/README.md) | [flow](services/mcp-server/flow.md) | [decisions](services/mcp-server/decisions.md) | [tech debt](services/mcp-server/tech-debt.md) |

## Keeping docs current

- A change that alters an endpoint, a graph edge, a table, or an env var updates that service's `README.md` or `flow.md` in the same PR.
- A change that picks between real alternatives adds a decision entry. Cross-service choices get a new ADR in `architecture/decisions/`.
- Paying down a debt item deletes it from `tech-debt.md`. Taking a new shortcut adds one.
- Tech-debt IDs (`AGENT-TD-3`, `X-TD-1`, ...) are stable. Do not renumber when items are removed.
