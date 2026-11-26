'use client';

import Link from 'next/link';
import { FormEvent, useEffect, useState, useTransition } from 'react';
import { useSearchParams } from 'next/navigation';

type Decision = 'approve' | 'edit' | 'reject';

const apiBase = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:3001';

const decisions: {
  value: Decision;
  label: string;
  help: string;
}[] = [
  {
    value: 'approve',
    label: 'Approve',
    help: 'Issue the refund as drafted',
  },
  {
    value: 'edit',
    label: 'Edit',
    help: 'Change the amount, then continue',
  },
  {
    value: 'reject',
    label: 'Reject',
    help: 'Stop the refund for this thread',
  },
];

function submitLabel(decision: Decision): string {
  if (decision === 'approve') return 'Approve refund';
  if (decision === 'edit') return 'Submit edited amount';
  return 'Reject refund';
}

function submitClass(decision: Decision): string {
  if (decision === 'reject') return 'btn btn-danger';
  if (decision === 'approve') return 'btn btn-accent';
  return 'btn btn-primary';
}

function bannerTone(
  status: string | null,
): 'ok' | 'error' | 'warn' | undefined {
  if (!status) return undefined;
  if (status.startsWith('Failed') || status.includes('error')) return 'error';
  if (status === 'Submitting…') return 'warn';
  return 'ok';
}

export function ApprovalsForm() {
  const searchParams = useSearchParams();
  const [threadId, setThreadId] = useState('');
  const [decision, setDecision] = useState<Decision>('approve');
  const [amount, setAmount] = useState('');
  const [note, setNote] = useState('');
  const [status, setStatus] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [isPending, startTransition] = useTransition();
  const sending = busy || isPending;

  useEffect(() => {
    const fromQuery = searchParams.get('threadId');
    if (fromQuery) {
      setThreadId(fromQuery);
    }
  }, [searchParams]);

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!threadId.trim() || sending) return;

    startTransition(() => {
      setStatus('Submitting…');
    });
    setBusy(true);

    try {
      const res = await fetch(
        `${apiBase}/approvals/${encodeURIComponent(threadId.trim())}`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            decision,
            amount:
              decision === 'edit' && amount ? Number(amount) : undefined,
            note: note || undefined,
          }),
        },
      );

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

  const tone = bannerTone(status);

  return (
    <section className="panel" aria-label="Approval decision">
      <div className="meta-bar">
        <span className="pill pill-neutral">
          <span className="pill-dot" aria-hidden="true" />
          HITL checkpoint
        </span>
        <Link className="inline-link" href="/">
          Back to chat
        </Link>
      </div>

      <form className="approval-form" onSubmit={onSubmit}>
        <div className="field">
          <label htmlFor="threadId">Thread ID</label>
          <input
            id="threadId"
            value={threadId}
            onChange={(e) => setThreadId(e.target.value)}
            placeholder="Paste thread ID from chat"
            autoComplete="off"
            required
            disabled={sending}
          />
          <p className="field-help">
            Use the copy control on the chat thread chip, or open Approvals from
            an interrupted conversation.
          </p>
        </div>

        <fieldset className="field field-fieldset">
          <legend className="field-legend">Decision</legend>
          <div className="decision-group" role="group" aria-label="Decision">
            {decisions.map((option) => (
              <button
                key={option.value}
                type="button"
                className={`decision-option ${option.value === 'reject' ? 'reject' : ''}`}
                aria-pressed={decision === option.value}
                disabled={sending}
                onClick={() => setDecision(option.value)}
              >
                <strong>{option.label}</strong>
                <span>{option.help}</span>
              </button>
            ))}
          </div>
        </fieldset>

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
              disabled={sending}
            />
            <p className="field-help">
              Enter the refund amount that should replace the draft.
            </p>
          </div>
        ) : null}

        <div className="field">
          <label htmlFor="note">Note (optional)</label>
          <textarea
            id="note"
            rows={2}
            value={note}
            onChange={(e) => setNote(e.target.value)}
            placeholder="Reason for edit or reject"
            disabled={sending}
          />
        </div>

        <div className="actions">
          <button
            type="submit"
            className={submitClass(decision)}
            disabled={
              sending ||
              !threadId.trim() ||
              (decision === 'edit' && !amount.trim())
            }
          >
            {sending ? 'Submitting…' : submitLabel(decision)}
          </button>
          <button
            type="button"
            className="btn btn-secondary"
            disabled={sending}
            onClick={() => {
              setDecision('approve');
              setAmount('');
              setNote('');
              setStatus(null);
            }}
          >
            Reset form
          </button>
        </div>
      </form>

      {status ? (
        <div className={`status-banner ${tone ?? ''}`} role="status">
          {status}
        </div>
      ) : null}
    </section>
  );
}
