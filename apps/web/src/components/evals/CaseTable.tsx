'use client';

import { Fragment, ReactNode, useState } from 'react';
import { EvalRun, formatValue } from './model';

type RagRow = {
  id: string;
  question: string;
  relevance_source: 'labels' | 'judge';
  expected?: { title: string; header_path: string }[];
  reference_answer?: string | null;
  ranking: Record<string, number>;
  retrieved: { title: string | null; header_path: string | null; score: number | null; relevant?: boolean }[];
  answer?: string | null;
  refused?: boolean;
  e2e_ms?: number;
  quality?: Record<string, number>;
  judge_backend?: string;
  ragas_error?: string;
};

type ToolRun = { ok: boolean; tool_calls: { name: string; args: Record<string, unknown> }[]; latency_ms: number };
type ToolRow = {
  id: string;
  correct: number;
  n: number;
  tool_call_accuracy: number;
  pass_at_1: number;
  latency_ms_mean: number;
  runs: ToolRun[];
  [key: string]: unknown;
};

type SafetyRow = {
  id: string;
  tag: string;
  ok: boolean;
  input: Record<string, unknown>;
  expected: Record<string, unknown>;
  got: Record<string, unknown>;
};

type Filter = 'all' | 'failing';

export function CaseTable({ run }: { run: EvalRun }) {
  const [filter, setFilter] = useState<Filter>('all');
  const [open, setOpen] = useState<string | null>(null);
  const result = run.result ?? {};

  let rows: { id: string; failing: boolean }[] = [];
  let body: (visible: Set<string>) => ReactNode = () => null;

  if (run.suite === 'rag') {
    const data = (result.results as RagRow[] | undefined) ?? [];
    rows = data.map((row) => ({ id: row.id, failing: !row.ranking.hit_at_5 }));
    body = (visible) => (
      <RagTable rows={data.filter((r) => visible.has(r.id))} open={open} onToggle={toggle} />
    );
  } else if (run.suite === 'agent_tools') {
    const data = (result.tasks as ToolRow[] | undefined) ?? [];
    const k = Number(run.params.k ?? 5);
    rows = data.map((row) => ({ id: row.id, failing: row.correct < row.n }));
    body = (visible) => (
      <ToolTable rows={data.filter((r) => visible.has(r.id))} k={k} open={open} onToggle={toggle} />
    );
  } else {
    const data = (result.cases as SafetyRow[] | undefined) ?? [];
    rows = data.map((row) => ({ id: row.id, failing: !row.ok }));
    body = (visible) => (
      <SafetyTable rows={data.filter((r) => visible.has(r.id))} open={open} onToggle={toggle} />
    );
  }

  function toggle(id: string) {
    setOpen((current) => (current === id ? null : id));
  }

  const failing = rows.filter((row) => row.failing).length;
  const visible = new Set(rows.filter((row) => filter === 'all' || row.failing).map((row) => row.id));

  return (
    <section className="panel" aria-labelledby="cases-title">
      <div className="eval-section-head">
        <h2 id="cases-title">Cases</h2>
        <div className="seg" role="group" aria-label="Filter cases">
          <button type="button" aria-pressed={filter === 'all'} onClick={() => setFilter('all')}>
            All <span className="seg-count">{rows.length}</span>
          </button>
          <button type="button" aria-pressed={filter === 'failing'} onClick={() => setFilter('failing')}>
            Failing <span className="seg-count">{failing}</span>
          </button>
        </div>
      </div>
      {visible.size === 0 ? (
        <p className="eval-empty-line">
          {filter === 'failing' ? 'No failing cases in this run.' : 'This run has no cases.'}
        </p>
      ) : (
        <div className="table-scroll">{body(visible)}</div>
      )}
    </section>
  );
}

function Check({ ok, label }: { ok: boolean; label?: string }) {
  return (
    <span className={ok ? 'mark mark-ok' : 'mark mark-bad'}>
      <svg viewBox="0 0 16 16" aria-hidden="true">
        {ok ? (
          <path d="m4 8.5 2.5 2.5L12 5.5" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
        ) : (
          <path d="m5 5 6 6M11 5l-6 6" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
        )}
      </svg>
      {label ?? (ok ? 'Pass' : 'Fail')}
    </span>
  );
}

function Bar({ value }: { value: number | null | undefined }) {
  const v = value ?? 0;
  return (
    <span className="bar-cell">
      <span className="bar" aria-hidden="true">
        <span style={{ width: `${Math.round(v * 100)}%` }} data-level={v >= 0.8 ? 'hi' : v >= 0.5 ? 'mid' : 'lo'} />
      </span>
      <span className="num">{formatValue(value, 'score')}</span>
    </span>
  );
}

function ExpandButton({ id, open, onToggle, children }: { id: string; open: boolean; onToggle: (id: string) => void; children: ReactNode }) {
  return (
    <button
      type="button"
      className="row-toggle"
      aria-expanded={open}
      aria-controls={`case-${id}`}
      onClick={() => onToggle(id)}
    >
      <svg viewBox="0 0 16 16" aria-hidden="true" className="chev">
        <path d="m6 4 4 4-4 4" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
      <span>{children}</span>
    </button>
  );
}

function RagTable({ rows, open, onToggle }: { rows: RagRow[]; open: string | null; onToggle: (id: string) => void }) {
  const answered = rows.some((row) => row.answer !== undefined);
  const judged = rows.some((row) => row.quality);
  const cols = 4 + (answered ? 1 : 0) + (judged ? 1 : 0);
  return (
    <table className="case-table">
      <thead>
        <tr>
          <th scope="col">Question</th>
          <th scope="col">Hit@5</th>
          <th scope="col">Recall@5</th>
          <th scope="col">nDCG@10</th>
          {judged ? <th scope="col">Faithfulness</th> : null}
          {answered ? <th scope="col" className="right">Answer time</th> : null}
        </tr>
      </thead>
      <tbody>
        {rows.map((row) => {
          const isOpen = open === row.id;
          return (
            <Fragment key={row.id}>
              <tr className={isOpen ? 'is-open' : undefined}>
                <td className="q-cell">
                  <ExpandButton id={row.id} open={isOpen} onToggle={onToggle}>
                    <span className="q-text">{row.question}</span>
                    <span className="q-id">
                      {row.id}
                      {row.relevance_source === 'judge' ? ' · judged relevance' : ''}
                    </span>
                  </ExpandButton>
                </td>
                <td><Check ok={row.ranking.hit_at_5 > 0} label={row.ranking.hit_at_5 > 0 ? 'Hit' : 'Miss'} /></td>
                <td className="num">{formatValue(row.ranking.recall_at_5, 'pct')}</td>
                <td><Bar value={row.ranking.ndcg_at_10} /></td>
                {judged ? <td>{row.quality ? <Bar value={row.quality.faithfulness} /> : <span className="muted">—</span>}</td> : null}
                {answered ? <td className="num right">{formatValue(row.e2e_ms, 'ms')}</td> : null}
              </tr>
              {isOpen ? (
                <tr className="detail-row" id={`case-${row.id}`}>
                  <td colSpan={cols}>
                    <div className="detail-grid">
                      <div>
                        <h3 className="detail-title">Retrieved, in rank order</h3>
                        <ol className="ranked">
                          {row.retrieved.map((doc, index) => (
                            <li key={index} className={doc.relevant ? 'is-relevant' : undefined}>
                              <span className="rank">{index + 1}</span>
                              <span className="ranked-text">
                                <strong>{doc.title ?? 'Untitled'}</strong>
                                <span>{doc.header_path ?? ''}</span>
                              </span>
                              {doc.relevant ? <span className="pill pill-ok">expected</span> : null}
                            </li>
                          ))}
                        </ol>
                        {row.expected?.length ? (
                          <p className="detail-note">
                            Expected: {row.expected.map((label) => label.header_path).join('; ')}
                          </p>
                        ) : null}
                      </div>
                      <div>
                        {row.answer !== undefined ? (
                          <>
                            <h3 className="detail-title">
                              Answer{row.refused ? <span className="pill pill-warn">refused</span> : null}
                            </h3>
                            <p className="answer-text">{row.answer || 'No answer.'}</p>
                          </>
                        ) : null}
                        {row.reference_answer ? (
                          <>
                            <h3 className="detail-title">Reference</h3>
                            <p className="answer-text muted-text">{row.reference_answer}</p>
                          </>
                        ) : null}
                        {row.quality ? (
                          <dl className="score-list">
                            {Object.entries(row.quality).map(([key, value]) => (
                              <div key={key}>
                                <dt>{key.replace(/_/g, ' ')}</dt>
                                <dd><Bar value={value} /></dd>
                              </div>
                            ))}
                          </dl>
                        ) : null}
                        {row.judge_backend ? <p className="detail-note">Scored by {row.judge_backend}</p> : null}
                        {row.ragas_error ? <p className="detail-note warn-text">Ragas fell back: {row.ragas_error}</p> : null}
                      </div>
                    </div>
                  </td>
                </tr>
              ) : null}
            </Fragment>
          );
        })}
      </tbody>
    </table>
  );
}

function ToolTable({ rows, k, open, onToggle }: { rows: ToolRow[]; k: number; open: string | null; onToggle: (id: string) => void }) {
  return (
    <table className="case-table">
      <thead>
        <tr>
          <th scope="col">Task</th>
          <th scope="col">Attempts</th>
          <th scope="col">Accuracy</th>
          <th scope="col">pass@{k}</th>
          <th scope="col">pass^{k}</th>
          <th scope="col" className="right">Latency</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((row) => {
          const isOpen = open === row.id;
          return (
            <Fragment key={row.id}>
              <tr className={isOpen ? 'is-open' : undefined}>
                <td className="q-cell">
                  <ExpandButton id={row.id} open={isOpen} onToggle={onToggle}>
                    <span className="q-text">{row.id}</span>
                    <span className="q-id">{row.correct} of {row.n} correct</span>
                  </ExpandButton>
                </td>
                <td>
                  <span className="dots" aria-label={`${row.correct} of ${row.n} attempts passed`}>
                    {row.runs.map((attempt, index) => (
                      <span key={index} className={attempt.ok ? 'dot dot-ok' : 'dot dot-bad'} />
                    ))}
                  </span>
                </td>
                <td className="num">{formatValue(row.tool_call_accuracy, 'pct')}</td>
                <td className="num">{formatValue(row[`pass_at_${k}`] as number, 'pct')}</td>
                <td className="num">{formatValue(row[`pass_hat_${k}`] as number, 'pct')}</td>
                <td className="num right">{formatValue(row.latency_ms_mean, 'ms')}</td>
              </tr>
              {isOpen ? (
                <tr className="detail-row" id={`case-${row.id}`}>
                  <td colSpan={6}>
                    <ol className="attempts">
                      {row.runs.map((attempt, index) => (
                        <li key={index}>
                          <span className="attempt-head">
                            <span className="rank">{index + 1}</span>
                            <Check ok={attempt.ok} />
                            <span className="muted">{formatValue(attempt.latency_ms, 'ms')}</span>
                          </span>
                          {attempt.tool_calls.length ? (
                            <code className="calls">
                              {attempt.tool_calls.map((call) => `${call.name}(${JSON.stringify(call.args)})`).join('\n')}
                            </code>
                          ) : (
                            <span className="muted">No tool calls</span>
                          )}
                        </li>
                      ))}
                    </ol>
                  </td>
                </tr>
              ) : null}
            </Fragment>
          );
        })}
      </tbody>
    </table>
  );
}

const TAG_LABEL: Record<string, string> = {
  routing: 'Routing',
  refund_safety: 'Refund safety',
  email_safety: 'Email safety',
};

function SafetyTable({ rows, open, onToggle }: { rows: SafetyRow[]; open: string | null; onToggle: (id: string) => void }) {
  return (
    <table className="case-table">
      <thead>
        <tr>
          <th scope="col">Case</th>
          <th scope="col">Type</th>
          <th scope="col">Expected</th>
          <th scope="col">Got</th>
          <th scope="col">Result</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((row) => {
          const isOpen = open === row.id;
          return (
            <Fragment key={row.id}>
              <tr className={isOpen ? 'is-open' : undefined}>
                <td className="q-cell">
                  <ExpandButton id={row.id} open={isOpen} onToggle={onToggle}>
                    <span className="q-text">{row.id}</span>
                  </ExpandButton>
                </td>
                <td><span className="pill pill-neutral">{TAG_LABEL[row.tag] ?? row.tag}</span></td>
                <td className="mono">{brief(row.expected)}</td>
                <td className="mono">{brief(row.got, Object.keys(row.expected))}</td>
                <td><Check ok={row.ok} /></td>
              </tr>
              {isOpen ? (
                <tr className="detail-row" id={`case-${row.id}`}>
                  <td colSpan={5}>
                    <div className="detail-grid">
                      <div>
                        <h3 className="detail-title">Input</h3>
                        <code className="calls">{JSON.stringify(row.input, null, 2)}</code>
                      </div>
                      <div>
                        <h3 className="detail-title">Output</h3>
                        <code className="calls">{JSON.stringify(row.got, null, 2)}</code>
                      </div>
                    </div>
                  </td>
                </tr>
              ) : null}
            </Fragment>
          );
        })}
      </tbody>
    </table>
  );
}

function brief(value: Record<string, unknown>, keys?: string[]): string {
  const pick = keys ?? Object.keys(value);
  return pick
    .filter((key) => key in value)
    .map((key) => `${key}: ${String(value[key])}`)
    .join(', ');
}
