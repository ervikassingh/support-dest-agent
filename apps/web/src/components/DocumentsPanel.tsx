'use client';

import { FormEvent, useEffect, useState } from 'react';

type DocumentRow = {
  id: string;
  sourceKey: string;
  version: number;
  filename: string;
  sourceType: string | null;
  title: string | null;
  status: string;
  error: string | null;
  createdAt: string;
  chunkCount: number;
};

const apiBase = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:3001';
const active = new Set(['queued', 'parsing', 'embedding']);

function pillClass(status: string): string {
  if (status === 'done') return 'pill pill-ok';
  if (status === 'failed') return 'pill pill-error';
  if (active.has(status)) return 'pill pill-warn';
  return 'pill pill-neutral';
}

export function DocumentsPanel() {
  const [documents, setDocuments] = useState<DocumentRow[]>([]);
  const [url, setUrl] = useState('');
  const [file, setFile] = useState<File | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);

  async function refresh() {
    const response = await fetch(`${apiBase}/documents`);
    if (!response.ok) {
      throw new Error(await response.text());
    }
    setDocuments((await response.json()) as DocumentRow[]);
    setLoadError(null);
  }

  useEffect(() => {
    let timer: ReturnType<typeof setTimeout> | undefined;
    let cancelled = false;

    async function tick() {
      try {
        const response = await fetch(`${apiBase}/documents`);
        if (!response.ok) throw new Error(await response.text());
        const rows = (await response.json()) as DocumentRow[];
        if (cancelled) return;
        setDocuments(rows);
        setLoadError(null);
        if (rows.some((row) => active.has(row.status))) {
          timer = setTimeout(tick, 2000);
        }
      } catch (error) {
        if (!cancelled) {
          setLoadError(error instanceof Error ? error.message : 'Could not load documents');
        }
      }
    }

    void tick();
    return () => {
      cancelled = true;
      if (timer) clearTimeout(timer);
    };
  }, [documents.length, message]);

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (busy) return;
    if (!file && !url.trim()) {
      setMessage('Choose a file or paste a link.');
      return;
    }
    if (file && url.trim()) {
      setMessage('Use a file or a link, not both.');
      return;
    }
    setBusy(true);
    setMessage(null);
    try {
      const response = file
        ? await fetch(`${apiBase}/documents`, { method: 'POST', body: fileForm(file) })
        : await fetch(`${apiBase}/documents`, {
            method: 'POST',
            headers: { 'content-type': 'application/json' },
            body: JSON.stringify({ url: url.trim() }),
          });
      if (!response.ok) {
        throw new Error(await response.text());
      }
      setFile(null);
      setUrl('');
      const form = event.currentTarget;
      form.reset();
      setMessage('Queued for ingest.');
      await refresh();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'Upload failed');
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <section className="panel" aria-label="Add a document">
        <form className="doc-form" onSubmit={onSubmit}>
          <div className="field">
            <label htmlFor="doc-file">File</label>
            <input
              id="doc-file"
              type="file"
              accept=".pdf,.docx,.md,.txt,.html,.htm"
              onChange={(event) => setFile(event.target.files?.[0] ?? null)}
            />
            <p className="field-help">PDF, Word, Markdown, text, or HTML. Up to 20 MB.</p>
          </div>
          <div className="field">
            <label htmlFor="doc-url">Or a link</label>
            <input
              id="doc-url"
              type="url"
              placeholder="https://example.com/returns"
              value={url}
              onChange={(event) => setUrl(event.target.value)}
            />
            <p className="field-help">
              A public page, PDF, or Google Docs, Sheets, or Slides link.
            </p>
          </div>
          <div className="actions">
            <button className="btn btn-accent" type="submit" disabled={busy}>
              {busy ? 'Queuing…' : 'Add document'}
            </button>
          </div>
          {message ? <p className="field-help">{message}</p> : null}
        </form>
      </section>

      <section className="panel" aria-label="Documents" style={{ marginTop: '1rem' }}>
        {loadError ? (
          <p className="doc-error" style={{ padding: '1rem' }}>
            {loadError}
          </p>
        ) : null}
        {documents.length === 0 ? (
          <p className="field-help" style={{ padding: '1rem' }}>
            No documents yet.
          </p>
        ) : (
          <ul className="doc-list">
            {documents.map((row) => (
              <li key={row.id} className="doc-row">
                <div>
                  <h2>{row.title || row.filename}</h2>
                  <p className="doc-meta">
                    v{row.version}
                    {row.sourceType ? ` · ${row.sourceType}` : ''} · {row.chunkCount} chunks ·{' '}
                    {row.sourceKey}
                  </p>
                  {row.error ? <p className="doc-error">{row.error}</p> : null}
                </div>
                <span className={pillClass(row.status)}>
                  <span className="pill-dot" aria-hidden="true" />
                  {row.status}
                </span>
              </li>
            ))}
          </ul>
        )}
      </section>
    </>
  );
}

function fileForm(file: File): FormData {
  const body = new FormData();
  body.append('file', file);
  return body;
}
