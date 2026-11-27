# web tech debt

Severity levels are defined in [architecture/tech-debt.md](../../architecture/tech-debt.md).

| ID | Item | Severity |
| --- | --- | --- |
| WEB-TD-1 | Approvals page shows no draft | High |
| WEB-TD-2 | Chat history and thread are lost on reload | Medium |
| WEB-TD-3 | No streaming replies | Medium |
| WEB-TD-4 | No list of pending approvals | Medium |
| WEB-TD-5 | API base URL and fetch handling duplicated | Low |
| WEB-TD-6 | Status UI keys off display strings | Low |
| WEB-TD-7 | Documents polling effect re-subscribes on unrelated changes | Low |

### WEB-TD-1. Approvals page shows no draft

**Severity:** High.

`ApprovalsForm` asks the operator to approve a refund without showing the order id, drafted amount, eligibility result, max amount, or prior operator notes. The agent already has all of this in the interrupt payload. Edit amounts are not checked against the eligible max until MCP rejects them.

**Fix:** add a read endpoint (agent `GET /threads/{id}` → api `GET /approvals/:threadId`) that returns the interrupt payload. Render it, and bound the edit field to `max_amount`.

### WEB-TD-2. Chat history and thread are lost on reload

**Severity:** Medium.

Messages and `threadId` live in `useState` in `src/app/page.tsx`. A reload starts a new thread, and the old conversation is unreachable from the UI even though it is checkpointed.

**Fix:** persist the thread id in `sessionStorage` or the URL, and load history from a thread read endpoint.

### WEB-TD-3. No streaming replies

**Severity:** Medium.

Chat waits for the whole graph run before rendering anything. rag already has `POST /answer/stream`, but the agent and api do not stream.

**Fix:** stream graph events from the agent (LangGraph `astream_events`), relay as SSE through api, and render tokens incrementally.

### WEB-TD-4. No list of pending approvals

**Severity:** Medium.

Operators must get a thread id from the customer chat. There is no queue view.

**Fix:** an api endpoint listing threads paused on `refund_approval`, and a table on `/approvals`.

### WEB-TD-5. API base URL and fetch handling duplicated

**Severity:** Low.

`apiBase` is redeclared in `page.tsx`, `ApprovalsForm.tsx`, and `DocumentsPanel.tsx`, each with its own error handling. Response types are hand-written ([X-TD-4](../../architecture/tech-debt.md#x-td-4-no-shared-contracts-between-services)).

**Fix:** one `src/lib/api.ts` client with typed methods.

### WEB-TD-6. Status UI keys off display strings

**Severity:** Low.

`statusTone` compares against `'Sending…'`. `bannerTone` checks `status.startsWith('Failed')` and `status.includes('error')`, so an agent message containing the word "error" turns the banner red.

**Fix:** keep a typed state (`idle | sending | ok | interrupted | error`) separate from the message text.

### WEB-TD-7. Documents polling effect re-subscribes on unrelated changes

**Severity:** Low.

The polling `useEffect` in `DocumentsPanel.tsx` depends on `[documents.length, message]`, and `refresh()` duplicates the fetch logic in `tick()`. Changing the message restarts polling and can briefly run two loops.

**Fix:** one polling hook that restarts only after a submit.
