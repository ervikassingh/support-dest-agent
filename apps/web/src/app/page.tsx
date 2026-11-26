'use client';

import Link from 'next/link';
import {
  FormEvent,
  KeyboardEvent,
  useEffect,
  useRef,
  useState,
  useTransition,
} from 'react';

type Message = {
  role: 'user' | 'assistant';
  content: string;
};

const apiBase = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:3001';

const suggestions = [
  'Where is order ORD-1001?',
  'What is the return window?',
  'Can I get a refund for ORD-1001?',
] as const;

function statusTone(status: string | null): 'ok' | 'warn' | 'error' | 'neutral' {
  if (!status) return 'neutral';
  if (status === 'ok') return 'ok';
  if (status === 'interrupted') return 'warn';
  if (status === 'Sending…') return 'neutral';
  return 'error';
}

function CopyIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <rect
        x="9"
        y="9"
        width="10"
        height="10"
        rx="2"
        stroke="currentColor"
        strokeWidth="1.75"
      />
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
      <path
        d="M5 12h14M13 6l6 6-6 6"
        stroke="currentColor"
        strokeWidth="1.75"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

export default function ChatPage() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [threadId, setThreadId] = useState<string | null>(null);
  const [status, setStatus] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const [isPending, startTransition] = useTransition();
  const [busy, setBusy] = useState(false);
  const logRef = useRef<HTMLDivElement>(null);
  const sending = busy || isPending;

  useEffect(() => {
    const node = logRef.current;
    if (!node) return;
    node.scrollTop = node.scrollHeight;
  }, [messages, sending]);

  async function sendMessage(text: string) {
    const trimmed = text.trim();
    if (!trimmed || sending) return;

    const nextMessages: Message[] = [
      ...messages,
      { role: 'user', content: trimmed },
    ];

    startTransition(() => {
      setMessages(nextMessages);
      setInput('');
      setStatus('Sending…');
    });
    setBusy(true);

    try {
      const res = await fetch(`${apiBase}/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message: trimmed,
          threadId,
        }),
      });

      if (!res.ok) {
        throw new Error(`API ${res.status}`);
      }

      const data = (await res.json()) as {
        reply: string;
        threadId: string;
        status?: string;
      };

      setThreadId(data.threadId);
      setMessages([
        ...nextMessages,
        { role: 'assistant', content: data.reply ?? '(empty stub reply)' },
      ]);
      setStatus(data.status ?? 'ok');
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Request failed';
      setStatus(message);
      setMessages([
        ...nextMessages,
        {
          role: 'assistant',
          content: `Could not reach API at ${apiBase}/chat (${message}). Is Nest running on :3001?`,
        },
      ]);
    } finally {
      setBusy(false);
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

  const tone = statusTone(status);

  return (
    <>
      <header className="page-intro">
        <h1>Customer chat</h1>
        <p>
          Ask about policies, orders, or refunds. Refunds that spend money pause
          for a human decision on Approvals.
        </p>
      </header>

      <section className="panel chat-shell" aria-label="Conversation">
        {(threadId || status) && (
          <div className="meta-bar">
            {threadId ? (
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
            ) : null}
            {status ? (
              <span className={`pill pill-${tone}`}>
                <span className="pill-dot" aria-hidden="true" />
                {status}
              </span>
            ) : null}
            {status === 'interrupted' && threadId ? (
              <Link
                className="inline-link"
                href={`/approvals?threadId=${encodeURIComponent(threadId)}`}
              >
                Review on Approvals
              </Link>
            ) : null}
          </div>
        )}

        <div className="chat-log" ref={logRef} aria-live="polite">
          {messages.length === 0 && !sending ? (
            <div className="empty-state">
              <div className="empty-icon" aria-hidden="true">
                <svg viewBox="0 0 24 24" fill="none">
                  <path
                    d="M7.5 19.5 4 21l1.2-3.6A8.5 8.5 0 1 1 12 20.5a8.4 8.4 0 0 1-4.5-1"
                    stroke="currentColor"
                    strokeWidth="1.75"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  />
                </svg>
              </div>
              <h2>Start a conversation</h2>
              <p>
                Try an order lookup, a policy question, or a refund request to
                exercise the agent path.
              </p>
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
                <div key={`${m.role}-${i}`} className={`bubble-row ${m.role}`}>
                  <span className="bubble-label">
                    {m.role === 'user' ? 'You' : 'Agent'}
                  </span>
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

        <form className="composer" onSubmit={onSubmit}>
          <div className="composer-field">
            <label htmlFor="chat-message">Message</label>
            <textarea
              id="chat-message"
              rows={3}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={onKeyDown}
              placeholder="Ask about a policy, order, or refund…"
              disabled={sending}
            />
          </div>
          <div className="composer-footer">
            <p className="hint">
              <kbd>Enter</kbd> to send · <kbd>Shift</kbd>+<kbd>Enter</kbd> for a
              new line
            </p>
            <button
              type="submit"
              className="btn btn-accent"
              disabled={sending || !input.trim()}
            >
              <SendIcon />
              {sending ? 'Sending…' : 'Send'}
            </button>
          </div>
        </form>
      </section>
    </>
  );
}
