'use client';

import { FormEvent, KeyboardEvent, useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { CaseTable } from './CaseTable';
import {
  EvalRun,
  SUITES,
  Suite,
  delta,
  elapsed,
  formatValue,
  headline,
  metricGroups,
  paramsLabel,
  sameParams,
  suiteInfo,
  when,
} from './model';

const apiBase = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:3001';

async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${apiBase}${path}`, init);
  if (!response.ok) {
    const text = await response.text();
    let message = text;
    try {
      const parsed = JSON.parse(text) as { message?: unknown };
      if (parsed.message) message = Array.isArray(parsed.message) ? parsed.message.join(', ') : String(parsed.message);
    } catch {
      // plain-text error body
    }
    throw new Error(message || `Request failed (${response.status})`);
  }
  return (await response.json()) as T;
}

type RagSettings = { answer: boolean; judge: boolean; limit: number | null };
type ToolSettings = { n: number; k: number };

export function EvalsDashboard() {
  const [suite, setSuite] = useState<Suite>('rag');
  const [runs, setRuns] = useState<EvalRun[] | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [detail, setDetail] = useState<EvalRun | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [startError, setStartError] = useState<string | null>(null);
  const [starting, setStarting] = useState(false);
  const [now, setNow] = useState(() => Date.now());
  const [rag, setRag] = useState<RagSettings>({ answer: true, judge: true, limit: null });
  const [tools, setTools] = useState<ToolSettings>({ n: 5, k: 5 });
  const tabRefs = useRef<Record<Suite, HTMLButtonElement | null>>({ rag: null, agent_tools: null, agent_safety: null });

  useEffect(() => {
    const fromUrl = new URLSearchParams(window.location.search).get('suite');
    if (fromUrl && SUITES.some((item) => item.id === fromUrl)) setSuite(fromUrl as Suite);
  }, []);

  const loadRuns = useCallback(async (target: Suite) => {
    const rows = await api<EvalRun[]>(`/evals/${target}/runs?limit=30`);
    setRuns(rows);
    setLoadError(null);
    return rows;
  }, []);

  useEffect(() => {
    let cancelled = false;
    setRuns(null);
    setDetail(null);
    setSelectedId(null);
    setStartError(null);
    loadRuns(suite)
      .then((rows) => {
        if (!cancelled) setSelectedId(rows[0]?.id ?? null);
      })
      .catch((error: unknown) => {
        if (!cancelled) {
          setRuns([]);
          setLoadError(error instanceof Error ? error.message : 'Could not load runs');
        }
      });
    return () => {
      cancelled = true;
    };
  }, [suite, loadRuns]);

  useEffect(() => {
    if (!selectedId) return;
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout> | undefined;

    async function tick() {
      try {
        const run = await api<EvalRun>(`/evals/${suite}/runs/${selectedId}`);
        if (cancelled) return;
        setDetail(run);
        setRuns((rows) => rows?.map((row) => (row.id === run.id ? { ...row, ...run, result: undefined } : row)) ?? rows);
        if (run.status === 'running') timer = setTimeout(tick, 2000);
      } catch (error) {
        if (!cancelled) setLoadError(error instanceof Error ? error.message : 'Could not load the run');
      }
    }

    void tick();
    return () => {
      cancelled = true;
      if (timer) clearTimeout(timer);
    };
  }, [suite, selectedId]);

  const otherRunning = runs?.some((row) => row.status === 'running' && row.id !== selectedId) ?? false;
  useEffect(() => {
    if (!otherRunning) return;
    const timer = setInterval(() => {
      void loadRuns(suite).catch(() => undefined);
    }, 3000);
    return () => clearInterval(timer);
  }, [otherRunning, suite, loadRuns]);

  const anyRunning = runs?.some((row) => row.status === 'running') ?? false;
  useEffect(() => {
    if (!anyRunning) return;
    const timer = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(timer);
  }, [anyRunning]);

  function selectSuite(next: Suite) {
    setSuite(next);
    const url = new URL(window.location.href);
    url.searchParams.set('suite', next);
    window.history.replaceState(null, '', url);
  }

  function onTabKey(event: KeyboardEvent<HTMLButtonElement>) {
    if (event.key !== 'ArrowRight' && event.key !== 'ArrowLeft') return;
    const index = SUITES.findIndex((item) => item.id === suite);
    const step = event.key === 'ArrowRight' ? 1 : -1;
    const next = SUITES[(index + step + SUITES.length) % SUITES.length].id;
    selectSuite(next);
    tabRefs.current[next]?.focus();
  }

  async function onStart(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (starting) return;
    setStarting(true);
    setStartError(null);
    try {
      const body = suite === 'rag' ? rag : suite === 'agent_tools' ? tools : {};
      const run = await api<EvalRun>(`/evals/${suite}/runs`, {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify(body),
      });
      setRuns((rows) => [run, ...(rows ?? [])]);
      setSelectedId(run.id);
      setDetail(run);
      setNow(Date.now());
    } catch (error) {
      setStartError(error instanceof Error ? error.message : 'Could not start the run');
    } finally {
      setStarting(false);
    }
  }

  const info = suiteInfo(suite);
  const selected = detail && detail.id === selectedId ? detail : null;
  const previous = useMemo(() => {
    if (!selected || !runs) return null;
    const index = runs.findIndex((row) => row.id === selected.id);
    return runs.slice(index + 1).find((row) => row.status === 'done' && sameParams(row, selected)) ?? null;
  }, [runs, selected]);

  return (
    <div className="evals">
      <div className="suite-tabs" role="tablist" aria-label="Eval suites">
        {SUITES.map((item) => {
          const active = item.id === suite;
          return (
            <button
              key={item.id}
              ref={(node) => {
                tabRefs.current[item.id] = node;
              }}
              type="button"
              role="tab"
              id={`tab-${item.id}`}
              aria-selected={active}
              aria-controls="suite-panel"
              tabIndex={active ? 0 : -1}
              className="suite-tab"
              onClick={() => selectSuite(item.id)}
              onKeyDown={onTabKey}
            >
              <SuiteIcon suite={item.id} />
              <span>{item.name}</span>
            </button>
          );
        })}
      </div>

      <div className="evals-grid" role="tabpanel" id="suite-panel" aria-labelledby={`tab-${suite}`}>
        <div className="evals-main">
          <section className="panel run-panel" aria-labelledby="run-title">
            <div className="run-copy">
              <h2 id="run-title">{info.name}</h2>
              <p>{info.blurb}</p>
              <p className="field-help">{info.needs}</p>
            </div>
            <form className="run-form" onSubmit={onStart}>
              {suite === 'rag' ? (
                <>
                  <label className="toggle">
                    <input
                      type="checkbox"
                      checked={rag.answer}
                      onChange={(e) => setRag({ ...rag, answer: e.target.checked })}
                    />
                    <span>Generate answers</span>
                  </label>
                  <label className="toggle">
                    <input
                      type="checkbox"
                      checked={rag.answer && rag.judge}
                      disabled={!rag.answer}
                      onChange={(e) => setRag({ ...rag, judge: e.target.checked })}
                    />
                    <span>Score answers with the judge model</span>
                  </label>
                  <div className="field compact">
                    <label htmlFor="rag-limit">Questions</label>
                    <select
                      id="rag-limit"
                      value={rag.limit ?? ''}
                      onChange={(e) => setRag({ ...rag, limit: e.target.value ? Number(e.target.value) : null })}
                    >
                      <option value="">All golden questions</option>
                      <option value="5">First 5</option>
                      <option value="10">First 10</option>
                    </select>
                  </div>
                </>
              ) : null}
              {suite === 'agent_tools' ? (
                <div className="field-row">
                  <div className="field compact">
                    <label htmlFor="tools-n">Attempts per task (n)</label>
                    <select
                      id="tools-n"
                      value={tools.n}
                      onChange={(e) => {
                        const n = Number(e.target.value);
                        setTools({ n, k: Math.min(tools.k, n) });
                      }}
                    >
                      {range(10).map((value) => (
                        <option key={value} value={value}>{value}</option>
                      ))}
                    </select>
                  </div>
                  <div className="field compact">
                    <label htmlFor="tools-k">k for pass@k</label>
                    <select id="tools-k" value={tools.k} onChange={(e) => setTools({ ...tools, k: Number(e.target.value) })}>
                      {range(tools.n).map((value) => (
                        <option key={value} value={value}>{value}</option>
                      ))}
                    </select>
                  </div>
                </div>
              ) : null}
              {suite === 'agent_safety' ? (
                <p className="field-help">No settings. Every case in the dataset runs once.</p>
              ) : null}
              <div className="run-actions">
                <button className="btn btn-accent" type="submit" disabled={starting || anyRunning}>
                  <PlayIcon />
                  {starting ? 'Starting…' : anyRunning ? 'Run in progress' : 'Run evals'}
                </button>
              </div>
            </form>
            {startError ? (
              <p className="status-banner error" role="alert">{startError}</p>
            ) : null}
          </section>

          {loadError ? (
            <p className="status-banner error standalone" role="alert">{loadError}</p>
          ) : null}

          {runs === null ? (
            <div className="panel skeleton-panel" aria-busy="true" aria-label="Loading runs">
              <span className="skeleton w-40" />
              <span className="skeleton w-90" />
              <span className="skeleton w-70" />
            </div>
          ) : runs.length === 0 && !loadError ? (
            <section className="panel empty-runs">
              <div className="empty-icon" aria-hidden="true"><ChartIcon /></div>
              <h2>No runs yet</h2>
              <p>Choose settings above and run the suite. Every run is saved, so you can compare before and after a change.</p>
            </section>
          ) : selected ? (
            <RunView key={selected.id} run={selected} previous={previous} now={now} />
          ) : selectedId ? (
            <div className="panel skeleton-panel" aria-busy="true" aria-label="Loading run">
              <span className="skeleton w-40" />
              <span className="skeleton w-90" />
            </div>
          ) : null}
        </div>

        <aside className="panel history" aria-labelledby="history-title">
          <div className="eval-section-head">
            <h2 id="history-title">Run history</h2>
            {runs?.length ? <span className="seg-count">{runs.length}</span> : null}
          </div>
          {runs && runs.length > 0 ? (
            <ul className="history-list">
              {runs.map((row) => {
                const top = headline(row);
                return (
                  <li key={row.id}>
                    <button
                      type="button"
                      className="history-item"
                      aria-current={row.id === selectedId ? 'true' : undefined}
                      onClick={() => setSelectedId(row.id)}
                    >
                      <span className="history-top">
                        <span className="history-when">{when(row.started_at)}</span>
                        <StatusPill run={row} />
                      </span>
                      <span className="history-bottom">
                        <span className="history-params">{paramsLabel(row).join(' · ')}</span>
                        {row.status === 'running' ? (
                          <span className="history-metric">{row.done}/{row.total}</span>
                        ) : top ? (
                          <span className="history-metric">
                            {top.value} <span>{top.label}</span>
                          </span>
                        ) : null}
                      </span>
                    </button>
                  </li>
                );
              })}
            </ul>
          ) : (
            <p className="eval-empty-line">Runs appear here.</p>
          )}
        </aside>
      </div>
    </div>
  );
}

function RunView({ run, previous, now }: { run: EvalRun; previous: EvalRun | null; now: number }) {
  const groups = metricGroups(run.suite, run.params);
  const summary = run.summary ?? {};
  const langsmith = (run.result?.langsmith ?? null) as { uploaded?: boolean; project?: string; reason?: string } | null;
  const pct = run.total ? Math.min(100, Math.round((run.done / run.total) * 100)) : 0;

  return (
    <>
      <section className="panel run-view" aria-labelledby="run-view-title">
        <div className="run-view-head">
          <div>
            <h2 id="run-view-title">Run from {when(run.started_at)}</h2>
            <p className="run-view-meta">
              {paramsLabel(run).map((part) => (
                <span key={part} className="meta-chip">{part}</span>
              ))}
              <span className="meta-chip">
                <ClockIcon />
                {elapsed(run, now)}
              </span>
            </p>
          </div>
          <StatusPill run={run} />
        </div>

        {run.status === 'running' ? (
          <div className="progress-block" aria-live="polite">
            <div
              className="progress"
              role="progressbar"
              aria-valuemin={0}
              aria-valuemax={run.total}
              aria-valuenow={run.done}
              aria-label="Cases finished"
            >
              <span style={{ width: `${Math.max(pct, 2)}%` }} />
            </div>
            <p className="progress-text">
              <strong>{run.done} of {run.total}</strong> {run.suite === 'agent_tools' ? 'attempts' : 'cases'} finished.
              Results appear when the run completes. You can leave this page; the run keeps going.
            </p>
          </div>
        ) : null}

        {run.status === 'failed' ? (
          <p className="status-banner error" role="alert">
            {run.error ?? 'The run failed.'}
          </p>
        ) : null}

        {run.status === 'done' ? (
          <div className="metric-groups">
            {groups.map((group) => (
              <div key={group.title} className="metric-group">
                <h3 className="group-title">{group.title}</h3>
                <div className="metric-grid">
                  {group.metrics.map((metric) => {
                    const value = summary[metric.key];
                    const change = previous ? delta(value, previous.summary?.[metric.key], metric) : null;
                    const ratio = metric.format === 'pct' || metric.format === 'score';
                    return (
                      <div key={metric.key} className="metric">
                        <span className="metric-label">{metric.label}</span>
                        <span className="metric-value">{formatValue(value, metric.format)}</span>
                        {ratio && value != null ? (
                          <span className="metric-bar" aria-hidden="true">
                            <span style={{ width: `${Math.round(value * 100)}%` }} />
                          </span>
                        ) : null}
                        {change ? <span className={`delta delta-${change.tone}`}>{change.text}</span> : null}
                        <span className="metric-hint">{metric.hint}</span>
                      </div>
                    );
                  })}
                </div>
              </div>
            ))}
            <p className="compare-note">
              {previous
                ? `Changes are against the run from ${when(previous.started_at)}, which used the same settings.`
                : 'No earlier finished run with the same settings, so there is nothing to compare against yet.'}
              {langsmith?.uploaded ? ` Uploaded to LangSmith project ${langsmith.project}.` : ''}
            </p>
          </div>
        ) : null}
      </section>

      {run.status === 'done' ? <CaseTable run={run} /> : null}
    </>
  );
}

function StatusPill({ run }: { run: EvalRun }) {
  if (run.status === 'running') {
    return (
      <span className="pill pill-warn">
        <span className="pill-dot pulse" aria-hidden="true" />
        Running
      </span>
    );
  }
  if (run.status === 'failed') {
    return (
      <span className="pill pill-error">
        <span className="pill-dot" aria-hidden="true" />
        Failed
      </span>
    );
  }
  return (
    <span className="pill pill-ok">
      <span className="pill-dot" aria-hidden="true" />
      Done
    </span>
  );
}

function range(n: number): number[] {
  return Array.from({ length: n }, (_, index) => index + 1);
}

function SuiteIcon({ suite }: { suite: Suite }) {
  if (suite === 'rag') {
    return (
      <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
        <circle cx="11" cy="11" r="6.25" stroke="currentColor" strokeWidth="1.75" />
        <path d="m20 20-4.5-4.5" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" />
      </svg>
    );
  }
  if (suite === 'agent_tools') {
    return (
      <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
        <path
          d="M14.5 6.5a3.5 3.5 0 0 0 4.6 4.6l-7.6 7.6a2 2 0 0 1-2.8-2.8l7.6-7.6a3.5 3.5 0 0 0-1.8-1.8Z"
          stroke="currentColor"
          strokeWidth="1.75"
          strokeLinejoin="round"
        />
      </svg>
    );
  }
  return (
    <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <path
        d="M12 3.5 19 6v5.5c0 4.2-2.9 7.6-7 9-4.1-1.4-7-4.8-7-9V6l7-2.5Z"
        stroke="currentColor"
        strokeWidth="1.75"
        strokeLinejoin="round"
      />
      <path d="m9 12 2 2 4-4" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function PlayIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <path d="M8 5.5v13l10.5-6.5L8 5.5Z" fill="currentColor" />
    </svg>
  );
}

function ClockIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" aria-hidden="true" className="chip-icon">
      <circle cx="12" cy="12" r="8.25" stroke="currentColor" strokeWidth="1.75" />
      <path d="M12 7.5V12l3 2" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" />
    </svg>
  );
}

function ChartIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none">
      <path d="M4 20h16M7 16v-4M12 16V7M17 16v-6" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" />
    </svg>
  );
}
