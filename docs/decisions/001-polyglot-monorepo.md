# 0001. Turborepo + Poetry monorepo; Python only for agent and rag

- Status: Accepted
- Services: all

## Context

The product needs a web UI, a browser-facing API, an LLM orchestrator, a retrieval pipeline, and a tool server. The best LLM tooling (LangGraph, LangChain, LangSmith evaluators, Ragas) is Python-first. The UI and API are more naturally TypeScript.

## Decision

- One repo. pnpm workspaces and Turborepo run every app's `dev`, `build`, and `lint` script (`turbo.json`, `pnpm-workspace.yaml`).
- `apps/agent` and `apps/rag` are Poetry projects. Each also has a `package.json` whose scripts call `poetry run ...`, so Turbo can drive them like the TypeScript apps.
- Python is used only where LangChain, LangGraph, or LangSmith pay for themselves. web, api, and mcp-server are TypeScript.
- Shared TypeScript compiler settings live in `packages/typescript-config`.

## Alternatives considered

- **All TypeScript (LangGraph.js).** Smaller toolchain, but the JS LangGraph and eval ecosystem trails Python, and Ragas has no JS port.
- **All Python (FastAPI UI backend, no Nest).** Fewer languages, but loses Next.js and a typed BFF for the UI.
- **Separate repos.** Cleaner ownership, but cross-service changes (a new field on `/chat`) would need coordinated PRs.

## Consequences

- `pnpm setup` must install both toolchains. Python 3.11–3.13 and Poetry are prerequisites.
- No shared types across the language boundary. Request and response shapes for `/chat`, `/threads/:id/resume`, and `/documents/*` are duplicated between `apps/api` and the Python services and can drift. See [X-TD-4](../../README.md#known-gaps).
- `turbo build` for Python apps is only `poetry check`.
