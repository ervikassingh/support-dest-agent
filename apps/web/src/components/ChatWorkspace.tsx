'use client';

import Link from 'next/link';
import { FormEvent, KeyboardEvent, useCallback, useEffect, useRef, useState } from 'react';
import { when } from './evals/model';
import {
  ChatMessage,
  ThreadDetail,
  ThreadStatus,
  ThreadSummary,
  apiBase,
  api,
  setQuery,
  threadBadge,
} from './history/model';

const suggestions = [
  'Where is order ORD-1001?',
  'What is the return window?',
  'Can I get a refund for ORD-1001?',
] as const;

type ChatResponse = { reply: string; threadId: string; status?: string; interrupt?: { type?: string } };

export function ChatWorkspace() {
  const [threads, setThreads] = useState<ThreadSummary[] | null>(null);
  const [listError, setListError] = useState<string | null>(null);
  const [threadId, setThreadId] = useState<string | null>(null);
  const [threadStatus, setThreadStatus] = useState<ThreadStatus>('active');
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [loadingThread, setLoadingThread] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [input, setInput] = useState('');
  const [sending, setSending] = useState(false);
  const [copied, setCopied] = useState(false);
  const logRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  const loadThreads = useCallback(async () => {
    try {
      setThreads(await api<ThreadSummary[]>('/threads?limit=100'));
      setListError(null);
    } catch (err) {
      setThreads((rows) => rows ?? []);
      setListError(err instanceof Error ? err.message : 'Could not load chats');
    }
  }, []);

  const openThread = useCallback(async (id: string) => {
    setThreadId(id);
    setQuery('thread', id);
    setError(null);
    setLoadingThread(true);
    try {
      const detail = await api<ThreadDetail>(`/threads/${encodeURIComponent(id)}`);
      setMessages(detail.messages);
      setThreadStatus(detail.status);
    } catch (err) {
      setMessages([]);
      setThreadStatus('active');
      setError(err instanceof Error ? err.message : 'Could not load this chat');
    } finally {
      setLoadingThread(false);
    }
  }, []);

  useEffect(() => {
    void loadThreads();
    const fromUrl = new URLSearchParams(window.location.search).get('thread');
    if (fromUrl) void openThread(fromUrl);
  }, [loadThreads, openThread]);

  useEffect(() => {
    if (threadStatus !== 'awaiting_approval' || !threadId) return;
    const timer = setInterval(async () => {
      try {
        const detail = await api<ThreadDetail>(`/threads/${encodeURIComponent(threadId)}`);
        if (detail.status !== 'awaiting_approval') {
          setMessages(detail.messages);
          setThreadStatus(detail.status);
          void loadThreads();
        }
      } catch {
        // keep polling; the next tick may succeed
      }
    }, 4000);
    return () => clearInterval(timer);
  }, [threadStatus, threadId, loadThreads]);

  useEffect(() => {
    const node = logRef.current;
    if (node) node.scrollTop = node.scrollHeight;
  }, [messages, sending]);

  function newChat() {
    setThreadId(null);
    setThreadStatus('active');
    setMessages([]);
    setError(null);
    setInput('');
    setQuery('thread', null);
    inputRef.current?.focus();
  }

  async function sendMessage(text: string) {
    const trimmed = text.trim();
    if (!trimmed || sending) return;
    const before = messages;
    setMessages([...before, { role: 'user', content: trimmed }]);
    setInput('');
    setError(null);
    setSending(true);
    try {
      const data = await api<ChatResponse>('/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: trimmed, threadId }),
      });
      setThreadId(data.threadId);
      setQuery('thread', data.threadId);
      setMessages([...before, { role: 'user', content: trimmed }, { role: 'assistant', content: data.reply }]);
      const kind = data.interrupt?.type;
      setThreadStatus(
        data.status !== 'interrupted' ? 'active' : kind === 'email_confirm' ? 'awaiting_email' : 'awaiting_approval',
      );
      void loadThreads();
    } catch (err) {
      setMessages(before);
      setInput(trimmed);
      setError(`Could not reach the API at ${apiBase} (${err instanceof Error ? err.message : 'request failed'}).`);
    } finally {
      setSending(false);
    }
  }

  function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    void sendMessage(input);
  }

  function onKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      void sendMessage(input);
    }
  }

  async function copyThreadId() {
    if (!threadId) return;
    try {
      await navigator.clipboard.writeText(threadId);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1500);
    } catch {
      setCopied(false);
    }
  }

  const current = threads?.find((row) => row.id === threadId);
  const badge = threadBadge({ status: threadStatus, approval_status: current?.approval_status ?? null });

  return (
    <div className="evals-grid">
      <section className="panel chat-shell" aria-label="Conversation">
        <div className="meta-bar">
          {threadId ? (
            <>
              <span className="meta-chip">
                Thread {threadId}
                <button
                  type="button"
                  onClick={() => void copyThreadId()}
                  aria-label={copied ? 'Thread ID copied' : 'Copy thread ID'}
                  title={copied ? 'Copied' : 'Copy thread ID'}
                >
                  <CopyIcon />
                </button>
              </span>
              <span className={`pill pill-${badge.tone}`}>
                <span className="pill-dot" aria-hidden="true" />
                {badge.label}
              </span>
              {threadStatus === 'awaiting_approval' ? (
                <Link className="inline-link" href={`/approvals?threadId=${encodeURIComponent(threadId)}`}>
                  Review on Approvals
                </Link>
              ) : null}
            </>
          ) : (
            <span className="pill pill-neutral">
              <span className="pill-dot" aria-hidden="true" />
              New chat
            </span>
          )}
        </div>

        <div className="chat-log" ref={logRef} aria-live="polite" aria-busy={loadingThread}>
          {loadingThread ? (
            <div className="skeleton-panel" aria-label="Loading chat">
              <span className="skeleton w-40" />
              <span className="skeleton w-90" />
              <span className="skeleton w-70" />
            </div>
          ) : messages.length === 0 && !sending ? (
            <div className="empty-state">
              <div className="empty-icon" aria-hidden="true">
                <ChatIcon />
              </div>
              <h2>Start a conversation</h2>
              <p>Try an order lookup, a policy question, or a refund request to exercise the agent path.</p>
              <div className="suggestions">
                {suggestions.map((prompt) => (
                  <button
                    key={prompt}
                    type="button"
                    className="chip"
                    disabled={sending}
                    onClick={() => void sendMessage(prompt)}
                  >
                    {prompt}
                  </button>
                ))}
              </div>
            </div>
          ) : (
            <>
              {messages.map((m, i) => (
                <div key={m.id ?? `${m.role}-${i}`} className={`bubble-row ${m.role}`}>
                  <span className="bubble-label">{m.role === 'user' ? 'You' : 'Agent'}</span>
                  <div className={`bubble ${m.role}`}>{m.content}</div>
                </div>
              ))}
              {sending ? (
                <div className="bubble-row assistant">
                  <span className="bubble-label">Agent</span>
                  <div className="bubble assistant typing" aria-label="Agent is typing">
                    <span />
                    <span />
                    <span />
                  </div>
                </div>
              ) : null}
            </>
          )}
        </div>

        {error ? (
          <p className="status-banner error chat-error" role="alert">
            {error}
          </p>
        ) : null}

        <form className="composer" onSubmit={onSubmit}>
          <div className="composer-field">
            <label htmlFor="chat-message">Message</label>
            <textarea
              id="chat-message"
              ref={inputRef}
              rows={3}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={onKeyDown}
              placeholder="Ask about a policy, order, or refund…"
              disabled={sending || loadingThread}
            />
          </div>
          <div className="composer-footer">
            <p className="hint">
              <kbd>Enter</kbd> to send · <kbd>Shift</kbd>+<kbd>Enter</kbd> for a new line
            </p>
            <button type="submit" className="btn btn-accent" disabled={sending || loadingThread || !input.trim()}>
              <SendIcon />
              {sending ? 'Sending…' : 'Send'}
            </button>
          </div>
        </form>
      </section>

      <aside className="panel history" aria-labelledby="chats-title">
        <div className="eval-section-head">
          <h2 id="chats-title">Chats</h2>
          <button type="button" className="btn btn-secondary btn-sm" onClick={newChat} disabled={sending}>
            <PlusIcon />
            New chat
          </button>
        </div>
        {listError ? (
          <p className="status-banner error history-error" role="alert">
            {listError}
          </p>
        ) : null}
        {threads === null ? (
          <div className="skeleton-panel" aria-busy="true" aria-label="Loading chats">
            <span className="skeleton w-90" />
            <span className="skeleton w-70" />
            <span className="skeleton w-90" />
          </div>
        ) : threads.length > 0 ? (
          <ul className="history-list">
            {threads.map((row) => {
              const rowBadge = threadBadge(row);
              return (
                <li key={row.id}>
                  <button
                    type="button"
                    className="history-item"
                    aria-current={row.id === threadId ? 'true' : undefined}
                    disabled={sending}
                    onClick={() => void openThread(row.id)}
                  >
                    <span className="history-title">{row.title}</span>
                    <span className="history-bottom">
                      <span className="history-params">
                        {when(row.updated_at)} · {row.message_count} messages
                      </span>
                      <span className={`pill pill-${rowBadge.tone} pill-sm`}>{rowBadge.label}</span>
                    </span>
                  </button>
                </li>
              );
            })}
          </ul>
        ) : (
          <p className="eval-empty-line">Your chats appear here.</p>
        )}
      </aside>
    </div>
  );
}

function ChatIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none">
      <path
        d="M7.5 19.5 4 21l1.2-3.6A8.5 8.5 0 1 1 12 20.5a8.4 8.4 0 0 1-4.5-1"
        stroke="currentColor"
        strokeWidth="1.75"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

function CopyIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <rect x="9" y="9" width="10" height="10" rx="2" stroke="currentColor" strokeWidth="1.75" />
      <path
        d="M7 15H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h7a2 2 0 0 1 2 2v1"
        stroke="currentColor"
        strokeWidth="1.75"
        strokeLinecap="round"
      />
    </svg>
  );
}

function SendIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <path d="M5 12h14M13 6l6 6-6 6" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function PlusIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <path d="M12 5v14M5 12h14" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" />
    </svg>
  );
}
