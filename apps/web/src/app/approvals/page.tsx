'use client';

import { FormEvent, useState } from 'react';

type Decision = 'approve' | 'edit' | 'reject';

const apiBase = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:3001';

export default function ApprovalsPage() {
  const [threadId, setThreadId] = useState('');
  const [decision, setDecision] = useState<Decision>('approve');
  const [amount, setAmount] = useState('');
  const [note, setNote] = useState('');
  const [status, setStatus] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!threadId.trim() || busy) return;

    setBusy(true);
    setStatus('Submitting…');

    try {
      const res = await fetch(`${apiBase}/approvals/${encodeURIComponent(threadId.trim())}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          decision,
          amount: decision === 'edit' && amount ? Number(amount) : undefined,
          note: note || undefined,
        }),
      });

      if (!res.ok) {
        throw new Error(`API ${res.status}`);
      }

      const data = (await res.json()) as { status: string; message?: string };
      setStatus(data.message ?? data.status);
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Request failed';
      setStatus(`Failed: ${message}`);
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <h1>Human approvals</h1>
      <p className="lede">
        Stub HITL UI. Approve, edit, or reject a paused refund thread via Nest{' '}
        <code>/approvals/:threadId</code>.
      </p>

      <section className="panel">
        <form className="approval-form" onSubmit={onSubmit}>
          <div className="field">
            <label htmlFor="threadId">Thread ID</label>
            <input
              id="threadId"
              value={threadId}
              onChange={(e) => setThreadId(e.target.value)}
              placeholder="thread from chat response"
              required
            />
          </div>

          <div className="field">
            <label htmlFor="decision">Decision</label>
            <select
              id="decision"
              value={decision}
              onChange={(e) => setDecision(e.target.value as Decision)}
            >
              <option value="approve">Approve</option>
              <option value="edit">Edit amount</option>
              <option value="reject">Reject</option>
            </select>
          </div>

          {decision === 'edit' ? (
            <div className="field">
              <label htmlFor="amount">Edited amount</label>
              <input
                id="amount"
                type="number"
                min="0"
                step="0.01"
                value={amount}
                onChange={(e) => setAmount(e.target.value)}
                placeholder="e.g. 24.99"
                required
              />
            </div>
          ) : null}

          <div className="field">
            <label htmlFor="note">Note (optional)</label>
            <textarea
              id="note"
              rows={2}
              value={note}
              onChange={(e) => setNote(e.target.value)}
              placeholder="Reason for edit/reject"
            />
          </div>

          <div className="actions">
            <button type="submit" disabled={busy || !threadId.trim()}>
              Submit decision
            </button>
            <button
              type="button"
              className="secondary"
              disabled={busy}
              onClick={() => {
                setDecision('reject');
              }}
            >
              Prefill reject
            </button>
          </div>
        </form>

        {status ? <p className="status">{status}</p> : null}
      </section>
    </>
  );
}
