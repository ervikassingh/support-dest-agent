# web

Next.js 15 UI on `:3000`. Four pages, all client components that call api directly from the browser. Next is effectively a static host: no route handlers, server actions, or server-side fetching.

| Route | File | Does |
| --- | --- | --- |
| `/` | `src/components/ChatWorkspace.tsx` | Customer chat with a saved-chats sidebar. Reads and writes `?thread=`. Polls the open thread every 4 s while it waits for approval, so the operator's result appears |
| `/documents` | `src/components/DocumentsPanel.tsx` | Upload a file or URL; list documents, polling every 2 s while any is in progress |
| `/approvals` | `src/components/ApprovalsWorkspace.tsx` | Approval queue with Pending and Decided lists. Shows the refund draft, earlier operator decisions for the customer, and the transcript. Pending: approve, edit, or reject. Decided: read-only record. Reads `?threadId=` or `?approval=`; polls pending every 5 s |
| `/evals` | `src/components/evals/EvalsDashboard.tsx` | Run eval suites and browse run history |

Chat and Approvals use the same layout as Evals: main panel plus a history sidebar (`evals-grid`, `history-item`). Shared types and the fetch helper are in `src/components/history/model.ts`. Every chat is visible to everyone; there is no login.

The chat's **Review on Approvals** link opens the pending approval for that thread ([Human in the loop](../flows/human-in-the-loop.md)).

## Config

| Variable | Default | Notes |
| --- | --- | --- |
| `NEXT_PUBLIC_API_URL` | `http://localhost:3001` | In `apps/web/.env.local`. Inlined at build time |

## Known gaps

- **WEB-TD-3** — No streaming replies.
- **WEB-TD-5** — API base URL and fetch handling duplicated across the documents, evals, and history modules.
- **WEB-TD-6** — Status colors key off display strings.
- **WEB-TD-7** — Documents polling restarts on unrelated changes.
- **WEB-TD-8** — Chats cannot be renamed, deleted, or searched.

Decisions: [web](../decisions/service-decisions.md#web).
