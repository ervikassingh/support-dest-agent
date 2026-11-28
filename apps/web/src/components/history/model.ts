export const apiBase = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:3001';

export async function api<T>(path: string, init?: RequestInit): Promise<T> {
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

export type ThreadStatus = 'active' | 'awaiting_approval' | 'awaiting_email';
export type ApprovalStatus = 'pending' | 'issued' | 'failed' | 'rejected';
export type Tone = 'ok' | 'warn' | 'error' | 'neutral';

export type ThreadSummary = {
  id: string;
  title: string;
  status: ThreadStatus;
  created_at: string;
  updated_at: string;
  message_count: number;
  approval_status: ApprovalStatus | null;
};

export type ChatMessage = {
  id?: number;
  role: 'user' | 'assistant';
  content: string;
  created_at?: string;
};

export type RefundDraft = {
  order_id?: string;
  amount?: number;
  reason?: string;
  customer_id?: string;
  eligibility?: { eligible?: boolean; reason?: string; max_amount?: number };
  prior_operator_notes?: Record<string, unknown>[];
};

export type Approval = {
  id: string;
  thread_id: string;
  thread_title?: string;
  status: ApprovalStatus;
  order_id: string | null;
  customer_id: string | null;
  amount: number | null;
  draft: RefundDraft;
  decision: 'approve' | 'edit' | 'reject' | null;
  final_amount: number | null;
  note: string | null;
  result_message: string | null;
  requested_at: string;
  decided_at: string | null;
};

export type ThreadDetail = Omit<ThreadSummary, 'message_count' | 'approval_status'> & {
  messages: ChatMessage[];
  approvals: Approval[];
};

export function threadBadge(thread: Pick<ThreadSummary, 'status' | 'approval_status'>): { label: string; tone: Tone } {
  if (thread.status === 'awaiting_approval') return { label: 'Awaiting approval', tone: 'warn' };
  if (thread.status === 'awaiting_email') return { label: 'Awaiting reply', tone: 'warn' };
  if (thread.approval_status && thread.approval_status !== 'pending') return approvalBadge(thread.approval_status);
  return { label: 'Active', tone: 'neutral' };
}

export function approvalBadge(status: ApprovalStatus): { label: string; tone: Tone } {
  if (status === 'pending') return { label: 'Pending', tone: 'warn' };
  if (status === 'issued') return { label: 'Refund issued', tone: 'ok' };
  if (status === 'failed') return { label: 'Refund failed', tone: 'error' };
  return { label: 'Rejected', tone: 'neutral' };
}

export function money(value: number | null | undefined): string {
  return value == null ? '—' : `$${value.toFixed(2)}`;
}

export function setQuery(key: string, value: string | null) {
  const url = new URL(window.location.href);
  if (value) url.searchParams.set(key, value);
  else url.searchParams.delete(key);
  window.history.replaceState(null, '', url);
}
