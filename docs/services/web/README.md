# web

Next.js 15 (App Router) UI on `:3000`. Three pages, all rendered as client components that call api directly from the browser.

| Route | File | Does |
| --- | --- | --- |
| `/` | `src/app/page.tsx` | Customer chat. Keeps the thread id, shows status, links to Approvals when a run is interrupted |
| `/documents` | `src/app/documents/page.tsx` → `src/components/DocumentsPanel.tsx` | Upload a file or URL for ingest; list documents with status and chunk count |
| `/approvals` | `src/app/approvals/page.tsx` → `src/components/ApprovalsForm.tsx` | Operator approve, edit, or reject for a paused refund. Reads `?threadId=` |

`src/app/layout.tsx` and `src/components/SiteHeader.tsx` provide the shell and navigation. Styling is hand-written CSS in `src/app/globals.css`.

## Dependencies

| Calls | Endpoint |
| --- | --- |
| api | `POST /chat`, `POST /approvals/:threadId`, `POST /documents`, `GET /documents` |

## Config

| Variable | Default | Notes |
| --- | --- | --- |
| `NEXT_PUBLIC_API_URL` | `http://localhost:3001` | Inlined at build time. Read separately in `page.tsx`, `ApprovalsForm.tsx`, and `DocumentsPanel.tsx` |

## Run

```bash
pnpm dev:web          # next dev --port 3000
pnpm --filter web build && pnpm --filter web start
```

## See also

- [flow.md](flow.md) · [decisions.md](decisions.md) · [tech-debt.md](tech-debt.md)
