'use client';

import { FormEvent, useState } from 'react';

type Message = {
  role: 'user' | 'assistant';
  content: string;
};

const apiBase = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:3001';

export default function ChatPage() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [threadId, setThreadId] = useState<string | null>(null);
  const [status, setStatus] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const text = input.trim();
    if (!text || busy) return;

    const nextMessages: Message[] = [...messages, { role: 'user', content: text }];
    setMessages(nextMessages);
    setInput('');
    setBusy(true);
    setStatus('Sending…');

    try {
      const res = await fetch(`${apiBase}/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message: text,
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

  return (
    <>
      <h1>Customer chat</h1>
      <p className="lede">
        Stub UI. Messages POST to Nest <code>/chat</code>, which proxies to the agent orchestrator.
      </p>

      <section className="panel">
        <div className="chat-log" aria-live="polite">
          {messages.length === 0 ? (
            <p className="lede">Ask about a policy, an order, or a refund.</p>
          ) : (
            messages.map((m, i) => (
              <div key={`${m.role}-${i}`} className={`bubble ${m.role}`}>
                {m.content}
              </div>
            ))
          )}
        </div>

        <form className="chat-form" onSubmit={onSubmit}>
          <textarea
            rows={3}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="e.g. Where is order ORD-1001?"
            disabled={busy}
          />
          <div className="actions">
            <button type="submit" disabled={busy || !input.trim()}>
              Send
            </button>
          </div>
        </form>

        {threadId ? <p className="status">Thread: {threadId}</p> : null}
        {status ? (
          <p className={`status ${status === 'ok' || status === 'interrupted' ? 'ok' : 'error'}`}>
            {status}
          </p>
        ) : null}
      </section>
    </>
  );
}
