# web

Next.js 15 UI on `:3000`. Three pages, all client components that call api directly from the browser. Next is effectively a static host: no route handlers, server actions, or server-side fetching.

| Route | File | Does |
| --- | --- | --- |
| `/` | `src/app/page.tsx` | Customer chat. Keeps the thread id, shows status, links to Approvals when a run is interrupted |
| `/documents` | `src/components/DocumentsPanel.tsx` | Upload a file or URL; list documents, polling every 2 s while any is in progress |
| `/approvals` | `src/components/ApprovalsForm.tsx` | Operator approve, edit, or reject for a paused refund. Reads `?threadId=` |

The thread id is held in React state and shown with a copy button. Copying it into Approvals is the hand-off from customer to operator ([Human in the loop](../flows/human-in-the-loop.md)).

## Config

| Variable | Default | Notes |
| --- | --- | --- |
| `NEXT_PUBLIC_API_URL` | `http://localhost:3001` | In `apps/web/.env.local`. Inlined at build time |

## Known gaps

- **WEB-TD-1** — The Approvals page does not show the refund draft (order, amount, eligibility) the operator is approving.
- **WEB-TD-2** — Chat history and thread id are lost on reload.
- **WEB-TD-3** — No streaming replies.
- **WEB-TD-4** — No list of pending approvals; operators need the thread id from the chat.
- **WEB-TD-5** — API base URL and fetch handling duplicated across three files.
- **WEB-TD-6** — Status colors key off display strings.
- **WEB-TD-7** — Documents polling restarts on unrelated changes.

Decisions: [web](../decisions/service-decisions.md#web).
