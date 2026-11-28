'use client';

import Link from 'next/link';
import { FormEvent, useCallback, useEffect, useState } from 'react';
import { when } from './evals/model';
import { Approval, ThreadDetail, api, approvalBadge, money, setQuery } from './history/model';

type View = 'pending' | 'decided';
type Decision = 'approve' | 'edit' | 'reject';

const decisions: { value: Decision; label: string; help: string }[] = [
  { value: 'approve', label: 'Approve', help: 'Issue the refund as drafted' },
  { value: 'edit', label: 'Edit', help: 'Change the amount, then continue' },
  { value: 'reject', label: 'Reject', help: 'Stop the refund for this thread' },
];

export function ApprovalsWorkspace() {
  const [view, setView] = useState<View>('pending');
  const [pending, setPending] = useState<Approval[] | null>(null);
  const [decided, setDecided] = useState<Approval[] | null>(null);
  const [listError, setListError] = useState<string | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [thread, setThread] = useState<ThreadDetail | null>(null);
  const [detailError, setDetailError] = useState<string | null>(null);

  const loadList = useCallback(async (which: View) => {
    try {
      const rows = await api<Approval[]>(`/approvals?state=${which}&limit=100`);
      (which === 'pending' ? setPending : setDecided)(rows);
      setListError(null);
      return rows;
    } catch (error) {
      (which === 'pending' ? setPending : setDecided)((rows) => rows ?? []);
      setListError(error instanceof Error ? error.message : 'Could not load approvals');
      return [];
    }
  }, []);

  const select = useCallback((approval: Approval) => {
    setSelectedId(approval.id);
    setQuery('approval', approval.id);
    setQuery('threadId', null);
    setDetailError(null);
    setThread((current) => (current?.id === approval.thread_id ? current : null));
    api<ThreadDetail>(`/threads/${encodeURIComponent(approval.thread_id)}`)
      .then(setThread)
      .catch((error: unknown) => setDetailError(error instanceof Error ? error.message : 'Could not load the thread'));
  }, []);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const fromThread = params.get('threadId');
    const fromApproval = params.get('approval');
    void Promise.all([loadList('pending'), loadList('decided')]).then(([open, closed]) => {
      const match =
        (fromApproval && [...open, ...closed].find((row) => row.id === fromApproval)) ||
        (fromThread && open.find((row) => row.thread_id === fromThread)) ||
        (fromThread && closed.find((row) => row.thread_id === fromThread)) ||
        open[0];
      if (!match) return;
      setView(match.status === 'pending' ? 'pending' : 'decided');
      select(match);
    });
  }, [loadList, select]);

  useEffect(() => {
    const timer = setInterval(() => void loadList('pending'), 5000);
    return () => clearInterval(timer);
  }, [loadList]);

  async function onDecided(approval: Approval) {
    await Promise.all([loadList('pending'), loadList('decided')]);
    setView('decided');
    select(approval);
  }

  const rows = view === 'pending' ? pending : decided;
  const selected =
    thread?.approvals.find((row) => row.id === selectedId) ??
    [...(pending ?? []), ...(decided ?? [])].find((row) => row.id === selectedId) ??
    null;

  return (
    <div className="evals-grid">
      <div className="evals-main">
        {listError ? (
          <p className="status-banner error standalone" role="alert">
            {listError}
          </p>
        ) : null}
        {pending === null ? (
          <div className="panel skeleton-panel" aria-busy="true" aria-label="Loading approvals">
            <span className="skeleton w-40" />
            <span className="skeleton w-90" />
            <span className="skeleton w-70" />
          </div>
        ) : selected ? (
          <ApprovalView
            key={`${selected.id}-${selected.status}`}
            approval={selected}
            thread={thread?.id === selected.thread_id ? thread : null}
            detailError={detailError}
            onDecided={onDecided}
          />
        ) : (
          <section className="panel empty-runs">
            <div className="empty-icon" aria-hidden="true">
              <CheckCircleIcon />
            </div>
            <h2>{pending.length === 0 ? 'Nothing waiting for approval' : 'Pick an approval'}</h2>
            <p>
              When a customer asks for an eligible refund, the agent drafts it and pauses. The draft shows up in the
              list, and every decision stays there under Decided.
            </p>
          </section>
        )}
      </div>

      <aside className="panel history" aria-labelledby="approvals-title">
        <div className="eval-section-head">
          <h2 id="approvals-title">Approvals</h2>
          <div className="seg" role="group" aria-label="Filter approvals">
            <button type="button" aria-pressed={view === 'pending'} onClick={() => setView('pending')}>
              Pending
              {pending?.length ? <span className="seg-count">{pending.length}</span> : null}
            </button>
            <button type="button" aria-pressed={view === 'decided'} onClick={() => setView('decided')}>
              Decided
            </button>
          </div>
        </div>
        {rows && rows.length > 0 ? (
          <ul className="history-list">
            {rows.map((row) => {
              const badge = approvalBadge(row.status);
              return (
                <li key={row.id}>
                  <button
                    type="button"
                    className="history-item"
                    aria-current={row.id === selectedId ? 'true' : undefined}
                    onClick={() => select(row)}
                  >
                    <span className="history-top">
                      <span className="history-when">{row.order_id ?? 'Unknown order'}</span>
                      <span className="history-metric">
                        {money(row.status === 'pending' ? row.amount : row.final_amount ?? row.amount)}
                      </span>
                    </span>
                    <span className="history-bottom">
                      <span className="history-params">
                        {when(row.status === 'pending' ? row.requested_at : row.decided_at ?? row.requested_at)}
                      </span>
                      <span className={`pill pill-${badge.tone} pill-sm`}>{badge.label}</span>
                    </span>
                  </button>
                </li>
              );
            })}
          </ul>
        ) : (
          <p className="eval-empty-line">
            {rows === null ? 'Loading…' : view === 'pending' ? 'No refunds are waiting.' : 'No decisions yet.'}
          </p>
        )}
      </aside>
    </div>
  );
}

function ApprovalView({
  approval,
  thread,
  detailError,
  onDecided,
}: {
  approval: Approval;
  thread: ThreadDetail | null;
  detailError: string | null;
  onDecided: (approval: Approval) => Promise<void>;
}) {
  const badge = approvalBadge(approval.status);
  const draft = approval.draft ?? {};
  const notes = draft.prior_operator_notes ?? [];

  return (
    <>
      <section className="panel run-view" aria-labelledby="approval-title">
        <div className="run-view-head">
          <div>
            <h2 id="approval-title">Refund for {approval.order_id ?? 'unknown order'}</h2>
            <p className="run-view-meta">
              <span className="meta-chip">Requested {when(approval.requested_at)}</span>
              {approval.customer_id ? <span className="meta-chip">Customer {approval.customer_id}</span> : null}
              <Link className="meta-chip meta-link" href={`/?thread=${encodeURIComponent(approval.thread_id)}`}>
                Open chat
              </Link>
            </p>
          </div>
          <span className={`pill pill-${badge.tone}`}>
            <span className={`pill-dot${approval.status === 'pending' ? ' pulse' : ''}`} aria-hidden="true" />
            {badge.label}
          </span>
        </div>

        <div className="metric-grid approval-facts">
          <div className="metric">
            <span className="metric-label">Drafted amount</span>
            <span className="metric-value">{money(approval.amount)}</span>
            <span className="metric-hint">The most this order can be refunded</span>
          </div>
          <div className="metric">
            <span className="metric-label">Eligibility</span>
            <span className="metric-value metric-text">{draft.eligibility?.eligible === false ? 'Not eligible' : 'Eligible'}</span>
            <span className="metric-hint">{draft.eligibility?.reason ?? 'Checked when the draft was made'}</span>
          </div>
          <div className="metric">
            <span className="metric-label">Reason</span>
            <span className="metric-value metric-text">{draft.reason ?? '—'}</span>
            <span className="metric-hint">From the customer request</span>
          </div>
        </div>

        {notes.length > 0 ? (
          <div className="approval-notes">
            <h3 className="detail-title">Earlier operator decisions for this customer</h3>
            <ul>
              {notes.slice(-5).reverse().map((note, index) => (
                <li key={index}>{describeNote(note)}</li>
              ))}
            </ul>
          </div>
        ) : null}

        {approval.status === 'pending' ? (
          <DecisionForm approval={approval} onDecided={onDecided} />
        ) : (
          <DecisionRecord approval={approval} />
        )}
      </section>

      <section className="panel" aria-labelledby="transcript-title">
        <div className="eval-section-head">
          <h2 id="transcript-title">Conversation</h2>
          {thread ? <span className="seg-count">{thread.messages.length}</span> : null}
        </div>
        {detailError ? (
          <p className="status-banner error history-error" role="alert">
            {detailError}
          </p>
        ) : thread ? (
          <div className="chat-log transcript">
            {thread.messages.map((m) => (
              <div key={m.id} className={`bubble-row ${m.role}`}>
                <span className="bubble-label">
                  {m.role === 'user' ? 'Customer' : 'Agent'}
                  {m.created_at ? ` · ${when(m.created_at)}` : ''}
                </span>
                <div className={`bubble ${m.role}`}>{m.content}</div>
              </div>
            ))}
          </div>
        ) : (
          <div className="skeleton-panel" aria-busy="true" aria-label="Loading conversation">
            <span className="skeleton w-70" />
            <span className="skeleton w-90" />
          </div>
        )}
      </section>
    </>
  );
}

function DecisionForm({ approval, onDecided }: { approval: Approval; onDecided: (approval: Approval) => Promise<void> }) {
  const [decision, setDecision] = useState<Decision>('approve');
  const [amount, setAmount] = useState(approval.amount != null ? String(approval.amount) : '');
  const [note, setNote] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (busy) return;
    setBusy(true);
    setError(null);
    try {
      await api(`/approvals/${encodeURIComponent(approval.thread_id)}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          decision,
          amount: decision === 'edit' && amount ? Number(amount) : undefined,
          note: note || undefined,
        }),
      });
      await onDecided(approval);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not submit the decision');
      setBusy(false);
    }
  }

  const max = approval.draft?.eligibility?.max_amount ?? approval.amount ?? undefined;

  return (
    <form className="approval-form decision-panel" onSubmit={onSubmit}>
      <fieldset className="field field-fieldset">
        <legend className="field-legend">Decision</legend>
        <div className="decision-group" role="group" aria-label="Decision">
          {decisions.map((option) => (
            <button
              key={option.value}
              type="button"
              className={`decision-option ${option.value === 'reject' ? 'reject' : ''}`}
              aria-pressed={decision === option.value}
              disabled={busy}
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
          <label htmlFor="amount">Refund amount</label>
          <input
            id="amount"
            type="number"
            min="0.01"
            max={max}
            step="0.01"
            value={amount}
            onChange={(e) => setAmount(e.target.value)}
            required
            disabled={busy}
          />
          <p className="field-help">Must be more than $0 and no more than {money(max)}.</p>
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
          disabled={busy}
        />
      </div>

      {error ? (
        <p className="status-banner error" role="alert">
          {error}
        </p>
      ) : null}

      <div className="actions">
        <button
          type="submit"
          className={decision === 'reject' ? 'btn btn-danger' : decision === 'approve' ? 'btn btn-accent' : 'btn btn-primary'}
          disabled={busy || (decision === 'edit' && !amount.trim())}
        >
          {busy
            ? 'Submitting…'
            : decision === 'approve'
              ? `Approve ${money(approval.amount)} refund`
              : decision === 'edit'
                ? 'Submit edited amount'
                : 'Reject refund'}
        </button>
      </div>
    </form>
  );
}

function DecisionRecord({ approval }: { approval: Approval }) {
  const tone = approval.status === 'issued' ? 'ok' : approval.status === 'failed' ? 'error' : 'warn';
  const decisionLabel =
    approval.decision === 'edit' ? 'Edited and approved' : approval.decision === 'approve' ? 'Approved' : 'Rejected';
  return (
    <div className="decision-record">
      <h3 className="detail-title">Decision</h3>
      <dl className="record-list">
        <div>
          <dt>Decision</dt>
          <dd>{decisionLabel}</dd>
        </div>
        <div>
          <dt>Refunded amount</dt>
          <dd>{approval.status === 'issued' ? money(approval.final_amount) : '—'}</dd>
        </div>
        <div>
          <dt>Decided</dt>
          <dd>{approval.decided_at ? when(approval.decided_at) : '—'}</dd>
        </div>
        <div>
          <dt>Operator note</dt>
          <dd>{approval.note || '—'}</dd>
        </div>
      </dl>
      {approval.result_message ? <p className={`status-banner ${tone}`}>{approval.result_message}</p> : null}
    </div>
  );
}

function describeNote(note: Record<string, unknown>): string {
  const order = note.order_id ? String(note.order_id) : 'an order';
  const operatorNote = note.operator_note ? ` (“${String(note.operator_note)}”)` : '';
  if (note.event === 'refund_rejected') return `Rejected a refund for ${order}${operatorNote}`;
  if (note.event === 'refund_failed') return `Refund for ${order} failed${operatorNote}`;
  const amount = typeof note.amount === 'number' ? ` of ${money(note.amount)}` : '';
  return `Issued a refund${amount} for ${order}${operatorNote}`;
}

function CheckCircleIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none">
      <path d="M9 11.5 11 13.5 15.5 9" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round" />
      <path d="M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18Z" stroke="currentColor" strokeWidth="1.75" />
    </svg>
  );
}
