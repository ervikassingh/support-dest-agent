# web decisions

System-wide decisions are in [architecture/decisions](../../architecture/decisions/README.md).

## WEB-1. Client components call api directly from the browser

**Context.** The pages are interactive forms with no SEO or first-paint data needs.

**Decision.** Every page's interactive part is a `'use client'` component that calls `NEXT_PUBLIC_API_URL` with `fetch`. No Next route handlers, server actions, or server-side fetching.

**Consequences.** Simple and stateless; Next is effectively a static host. api must allow CORS from `WEB_ORIGIN`. The api URL is baked in at build time. When auth arrives, cookies must be cross-origin (`credentials: true` is already set on the api side), or the calls move behind Next route handlers.

## WEB-2. Thread id is held in client state

**Context.** The agent creates a thread id on the first message and returns it.

**Decision.** `page.tsx` stores it with `useState` and sends it on every later message. The chat shows it with a copy button so an operator can paste it into Approvals.

**Consequences.** No persistence across reloads and no thread list. Copying a thread id is the hand-off between customer and operator views ([WEB-TD-2](tech-debt.md)).

## WEB-3. Poll for ingest status

**Context.** Ingest takes seconds to minutes. The rag worker writes status to Postgres.

**Decision.** `DocumentsPanel` polls `GET /documents` every 2 s while any row is `queued`, `parsing`, or `embedding`, then stops.

**Alternatives.** Server-sent events or WebSockets from api, which would need api to subscribe to BullMQ events or poll rag itself.

**Consequences.** No push infrastructure. The list endpoint returns every document each time, which is fine at current scale.

## WEB-4. No UI framework

**Decision.** Plain React and one hand-written `globals.css` with inline SVG icons. No component library or Tailwind.

**Consequences.** Small bundle and no design-system dependency. `globals.css` is about 900 lines and will need splitting as pages grow.
